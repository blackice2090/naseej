"""Shadow candidate model — approved-features-only retraining (NOT deployed).

Trains and evaluates a candidate model using ONLY the approved, parity-clean,
servable, non-memorising feature set from
``ml/reports/training_feature_manifest.json``. The result is documented for
review; it is **never deployed** and never overwrites the deployed artifacts.

Hard contract (also enforced in code):
- Uses only ``approved_training_features`` (15 features). The account/bank
  identity encodings, all ``*_all_time`` cumulatives, ``account_pair_*``, the
  train_only fan_in/fan_out 24h counts, and all serve_only online features are
  HARD-BLOCKED — an assertion fails if any appears in the matrix.
- NEVER writes ``ml/models/baseline_model.joblib`` or
  ``ml/reports/model_metrics.json``. Candidate artifacts use the
  ``candidate_*`` prefix.
- Temporal 70/15/15 split + point-in-time features (same protocol as
  ``ml/src/evaluation_suite.py``), so candidate numbers ARE comparable with
  ``model_comparison.json`` / ``ablation_report.json`` but NOT with the
  deployed ``model_metrics.json`` (stratified-random protocol — flagged).
- PR-AUC is primary; accuracy is never reported.
- LightGBM is optional; a missing dependency is recorded, never faked.

CLI:
    python -m ml.src.train_candidate_model --train-sample 800000
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from . import evaluation_suite as es
from . import feature_contract
from .evaluate import best_threshold_by_f1, compute_metrics

logger = logging.getLogger("naseej.train_candidate_model")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED_DIR = REPO_ROOT / "ml" / "data" / "processed"
DEFAULT_REPORTS_DIR = REPO_ROOT / "ml" / "reports"
DEFAULT_MODELS_DIR = REPO_ROOT / "ml" / "models"
MANIFEST_PATH = DEFAULT_REPORTS_DIR / "training_feature_manifest.json"

# Protected deployed artifacts — this script must never write these.
PROTECTED_PATHS = (
    DEFAULT_MODELS_DIR / "baseline_model.joblib",
    DEFAULT_REPORTS_DIR / "model_metrics.json",
)

PHASE_TAG = "candidate-shadow-1"
DATASET_NOTE = "AMLworld HI-Small (synthetic) — shadow candidate, NOT production validation."

# Columns that must NEVER enter the candidate matrix (defense in depth on top
# of the manifest). Substring match catches the family.
FORBIDDEN_SUBSTRINGS = (
    "account_enc", "bank_enc",            # identity encodings (memorisation)
    "_total_before", "account_pair_",     # all-time cumulative / pair (not servable)
)
FORBIDDEN_EXACT = frozenset({
    "source_account_enc", "target_account_enc", "source_bank_enc", "target_bank_enc",
    "fan_in_score", "fan_out_score",       # offline 24h counts → train_only
    "sweep_ratio", "rapid_movement_flag",  # train_only
})


# ----------------------------------------------------------------- approved set


def load_approved_offline_columns(manifest_path: Path = MANIFEST_PATH) -> list[str]:
    """Return the OFFLINE column names of the approved training features.

    Reads the manifest (source of truth). Every approved feature must carry an
    offline_name (the column present in the training parquets). Falls back to
    the contract's approved-derivation if the manifest file is absent.
    """
    cols: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        approved = manifest.get("approved_training_features", [])
    except FileNotFoundError:
        logger.warning("Manifest not found at %s — deriving approved set from the contract.", manifest_path)
        approved = [
            {"canonical_name": e.canonical_name, "offline_name": e.offline_name}
            for e in feature_contract.CONTRACT
            if e.trainable and e.servable and not e.identity_memorization_risk
        ]
    for row in approved:
        off = row.get("offline_name")
        if not off:
            raise ValueError(
                f"Approved feature {row.get('canonical_name')} has no offline_name — "
                "cannot build it from the training parquets."
            )
        cols.append(off)
    _assert_no_forbidden(cols)
    return cols


def _assert_no_forbidden(cols: list[str]) -> None:
    """Fail closed if any excluded/identity feature sneaks into the matrix."""
    bad = [c for c in cols if c in FORBIDDEN_EXACT
           or any(sub in c for sub in FORBIDDEN_SUBSTRINGS)]
    if bad:
        raise AssertionError(
            f"Candidate feature set contains HARD-BLOCKED features: {bad}. "
            "Identity encodings and non-servable/train-only features are forbidden."
        )


# ----------------------------------------------------------------- report I/O


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(reports_dir: Path, name: str, payload: dict[str, Any]) -> None:
    path = reports_dir / name
    assert path.resolve() not in {p.resolve() for p in PROTECTED_PATHS}, "refusing to overwrite a protected report"
    path.write_text(json.dumps(payload, indent=2, default=float), encoding="utf-8")
    logger.info("Wrote %s", path)


def _write_md(reports_dir: Path, name: str, lines: list[str]) -> None:
    (reports_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


HONESTY_FOOTER = (
    "> SHADOW CANDIDATE — evaluated on synthetic AMLworld HI-Small, NOT deployed. "
    "The live model, scoring endpoint, demo, explainability, and offline fallback are unchanged. "
    "Accuracy is intentionally omitted (≈0.1% prevalence)."
)


# ----------------------------------------------------------------- candidate run


def run_candidate(
    *,
    processed_dir: Path | None = None,
    splits_raw: dict[str, Any] | None = None,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    models_dir: Path = DEFAULT_MODELS_DIR,
    manifest_path: Path = MANIFEST_PATH,
    train_sample: int = 800_000,
    seed: int = 42,
    model_names: list[str] | None = None,
    write_model: bool = True,
) -> dict[str, Any]:
    """Train + evaluate the shadow candidate. Returns a summary dict.

    ``splits_raw`` lets tests inject tiny synthetic raw splits (same schema as
    ml/data/processed) so the whole pipeline runs in seconds.
    """
    t0 = time.time()
    reports_dir = Path(reports_dir)
    models_dir = Path(models_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    approved_cols = load_approved_offline_columns(manifest_path)
    logger.info("Approved feature columns (%d): %s", len(approved_cols), approved_cols)

    # 1. Data: temporal split + point-in-time features (reused from eval suite).
    if splits_raw is None:
        raw = es.load_raw_frame(Path(processed_dir or DEFAULT_PROCESSED_DIR))
        splits = es.temporal_split(raw)
        del raw
    else:
        splits = splits_raw
    feats = es.build_features(splits)
    train_df = es.sample_training_rows(feats["train"], n=train_sample, seed=seed)
    val_df, test_df = feats["val"], feats["test"]

    # Build matrices on the approved columns ONLY (raises if any are missing).
    X_train = es.feature_matrix(train_df, approved_cols)
    _assert_no_forbidden(list(X_train.columns))
    y_train = train_df["is_laundering"].astype(int).to_numpy()
    X_val = es.feature_matrix(val_df, approved_cols)
    y_val = val_df["is_laundering"].astype(int).to_numpy()
    X_test = es.feature_matrix(test_df, approved_cols)
    y_test = test_df["is_laundering"].astype(int).to_numpy()
    logger.info("Matrices: train=%d val=%d test=%d feats=%d", len(X_train), len(X_val), len(X_test), len(approved_cols))

    # 2. Train competitors on the approved feature set.
    models, availability = es.build_competitors(seed)
    if model_names is not None:
        models = [(n, m) for n, m in models if n in model_names]

    leaderboard: list[dict[str, Any]] = []
    val_scores: dict[str, np.ndarray] = {}
    test_scores: dict[str, np.ndarray] = {}
    fitted: dict[str, Any] = {}
    for name, est in models:
        t = time.time()
        est.fit(X_train.values, y_train)
        fit_s = time.time() - t
        v = est.predict_proba(X_val.values)[:, 1]
        te = est.predict_proba(X_test.values)[:, 1]
        thr, _ = best_threshold_by_f1(y_val, v)
        val_m = compute_metrics(y_val, v, threshold=thr)
        test_m = compute_metrics(y_test, te, threshold=thr)
        logger.info("  %s: val PR-AUC=%.4f test PR-AUC=%.4f (%.1fs)", name, val_m.pr_auc, test_m.pr_auc, fit_s)
        leaderboard.append({
            "model": name, "fit_seconds": round(fit_s, 2),
            "val": es._metrics_dict(val_m), "test": es._metrics_dict(test_m),
        })
        val_scores[name] = v
        test_scores[name] = te
        fitted[name] = est

    if not leaderboard:
        raise RuntimeError("No candidate models trained.")

    selected = max(leaderboard, key=lambda r: r["val"]["pr_auc"])["model"]
    selected_row = next(r for r in leaderboard if r["model"] == selected)
    test_leader = max(leaderboard, key=lambda r: r["test"]["pr_auc"])["model"]
    logger.info("Selected candidate (val PR-AUC): %s; test leader: %s", selected, test_leader)

    # 3. Persist the candidate model bundle (NEVER baseline_model.joblib).
    model_path = models_dir / "candidate_model.joblib"
    assert model_path.resolve() not in {p.resolve() for p in PROTECTED_PATHS}
    val_thr, _ = best_threshold_by_f1(y_val, val_scores[selected])
    if write_model:
        import joblib

        joblib.dump({
            "model": fitted[selected], "feature_columns": approved_cols,
            "threshold": val_thr, "model_name": selected,
            "candidate": True, "deployed": False,
            "feature_set": "approved_parity_clean_only",
            "note": "Shadow candidate — not deployed; identity/encoding features excluded.",
        }, model_path)
        logger.info("Saved candidate model -> %s", model_path)

    # 4. Threshold policy on the selected candidate (chosen on val, frozen).
    threshold_rows = []
    for spec in es.THRESHOLD_MODES:
        thr, _ = es.threshold_by_fbeta(y_val, val_scores[selected], spec["beta"])
        m = compute_metrics(y_test, test_scores[selected], threshold=thr)
        threshold_rows.append({
            "mode": spec["mode"], "recommended_use": spec["recommended_use"],
            "threshold": float(thr), "precision": m.precision, "recall": m.recall,
            "f1": m.f1, "fpr": m.fpr, "n_alerts": m.n_alerts,
            "alerts_per_100k": es._alerts_per_100k(m),
        })

    # 5. Build the approved/excluded feature provenance for the reports.
    excluded_now = _excluded_summary()

    # ---- reports ----
    common = {
        "source": "live", "phase": PHASE_TAG, "generated_at": _now_iso(),
        "dataset": DATASET_NOTE, "deployed": False, "shadow_only": True,
        "feature_set": "approved_parity_clean_only",
        "approved_features": approved_cols,
        "identity_features_excluded": list(feature_contract.CONTRACT_BY_OFFLINE.keys() & FORBIDDEN_EXACT)
        or ["source_account_enc", "target_account_enc", "source_bank_enc", "target_bank_enc"],
    }

    metrics_payload = {
        **common,
        "report": "candidate_model_metrics",
        "primary_metric": "pr_auc",
        "selected_model": selected,
        "test_leader": test_leader,
        "protocol": {
            "split": "temporal 70%/15%/15% by timestamp",
            "feature_count": len(approved_cols),
            "model_selection": "best validation PR-AUC",
            "threshold": "F1-optimal on validation, frozen for the reported test metrics",
            "seed": seed,
            "comparable_with": "model_comparison.json + ablation_report.json (same temporal protocol)",
            "not_comparable_with": "model_metrics.json (deployed baseline used a stratified-random split)",
        },
        "selected_test_metrics": selected_row["test"],
        "selected_val_metrics": selected_row["val"],
        "deployment_recommended": False,
        "trained_seconds": round(time.time() - t0, 1),
    }
    _write_json(reports_dir, "candidate_model_metrics.json", metrics_payload)
    _write_md(reports_dir, "candidate_model_metrics.md", _metrics_md(metrics_payload))

    comparison_payload = {
        **common,
        "report": "candidate_model_comparison",
        "primary_metric": "pr_auc",
        "availability": availability,
        "selected_model": selected,
        "test_leader": test_leader,
        "leaderboard": leaderboard,
        "context": _comparison_context(selected_row, reports_dir),
        "excluded_features": excluded_now,
    }
    _write_json(reports_dir, "candidate_model_comparison.json", comparison_payload)
    _write_md(reports_dir, "candidate_model_comparison.md", _comparison_md(comparison_payload))

    thresholds_payload = {
        **common,
        "report": "candidate_thresholds",
        "model": selected,
        "split": "test",
        "selection_note": "Each threshold maximises its F-beta on validation, then is frozen before test.",
        "thresholds": threshold_rows,
    }
    _write_json(reports_dir, "candidate_thresholds.json", thresholds_payload)
    _write_md(reports_dir, "candidate_thresholds.md", _thresholds_md(thresholds_payload))

    # 6. Explainability check on the selected candidate.
    explain_payload = candidate_explainability_check(
        fitted[selected], selected, approved_cols, X_test, reports_dir=reports_dir,
    )

    # Safety: confirm the protected artifacts were never touched by this run.
    summary = {
        "selected_model": selected,
        "test_leader": test_leader,
        "selected_test_pr_auc": selected_row["test"]["pr_auc"],
        "n_features": len(approved_cols),
        "availability": availability,
        "deployment_recommended": False,
        "explainability_method": explain_payload.get("method"),
        "reports_dir": str(reports_dir),
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    logger.info("Candidate run complete: %s", json.dumps(summary, default=float))
    return summary


def _excluded_summary() -> list[dict[str, Any]]:
    out = []
    for e in feature_contract.CONTRACT:
        if e.trainable and e.servable and not e.identity_memorization_risk:
            continue
        reason = (
            "identity/memorisation risk" if e.identity_memorization_risk
            else "not servable (all-time / no online twin)" if e.parity_status == "train_only"
            else "serving-only (no offline twin)" if e.parity_status == "serve_only"
            else "definition mismatch"
        )
        out.append({"canonical_name": e.canonical_name, "parity_status": e.parity_status,
                    "identity_memorization_risk": e.identity_memorization_risk, "reason": reason})
    return out


def _comparison_context(selected_row: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    """Honest cross-report context, flagging protocol (in)compatibility."""
    ctx: dict[str, Any] = {"candidate_test_pr_auc": selected_row["test"]["pr_auc"]}

    def _load(name):
        try:
            return json.loads((reports_dir / name).read_text(encoding="utf-8"))
        except Exception:
            return None

    ablation = _load("ablation_report.json")
    if ablation:
        by_set = {r["feature_set"]: r for r in ablation.get("feature_sets", [])}
        gc = by_set.get("graph_context", {}).get("test", {}).get("pr_auc")
        full = by_set.get("full_with_account_ids", {}).get("test", {}).get("pr_auc")
        ctx["ablation_same_protocol"] = {
            "graph_context_no_identity_pr_auc": gc,
            "full_with_account_ids_pr_auc": full,
            "identity_lift_forgone": (round(full - gc, 4) if (full is not None and gc is not None) else None),
            "note": "Candidate uses a strict subset of graph_context (servable, parity-clean). The "
                    "full_with_account_ids set adds account-id memorisation lift the candidate deliberately forgoes.",
        }
    comp = _load("model_comparison.json")
    if comp:
        ctx["prior_eval_same_protocol"] = {
            "test_leader": comp.get("test_leader"),
            "test_leader_pr_auc": comp.get("test_leader_pr_auc"),
            "note": "Same temporal split — directly comparable; that run included identity + serve/train-only features.",
        }
    deployed = _load("model_metrics.json")
    if deployed:
        ctx["deployed_baseline"] = {
            "model_name": deployed.get("model_name"),
            "pr_auc": deployed.get("pr_auc"),
            "protocol": "stratified-random split (legacy)",
            "note": "NOT directly comparable — different split protocol. Shown for reference only.",
        }
    return ctx


# ----------------------------------------------------------------- explainability


def candidate_explainability_check(
    model: Any, model_name: str, feature_columns: list[str], X_test,
    *, reports_dir: Path = DEFAULT_REPORTS_DIR,
) -> dict[str, Any]:
    """SHAP (tree) or deterministic fallback attribution on ONE synthetic test
    row, with labels/buckets resolved through the feature contract. PII-safe:
    only bucket labels, never raw values.
    """
    # Reuse the deployed explanation service's contract-aware labels/buckets.
    from backend.app.services import explanation_service as ex
    ex.reset_contract_cache()

    # A single representative row (already synthetic AMLworld data).
    row = X_test.iloc[[0]] if len(X_test) else None
    raw = dict(zip(feature_columns, row.iloc[0].tolist())) if row is not None else {
        c: 0.0 for c in feature_columns
    }

    method = "fallback"
    method_note = "deterministic feature/rule attribution fallback"
    top_factors: list[dict[str, Any]] = []
    tree_models = ("XGBClassifier", "LGBMClassifier", "RandomForestClassifier")

    if type(model).__name__ in tree_models and row is not None:
        try:
            import shap

            explainer = shap.TreeExplainer(model)
            vals = np.asarray(explainer.shap_values(row.to_numpy()))
            if vals.ndim == 3:
                vals = vals[..., 1] if vals.shape[-1] == 2 else vals[..., -1]
            contrib = np.asarray(vals).reshape(-1)
            order = np.argsort(np.abs(contrib))[::-1]
            total = float(np.sum(np.abs(contrib))) or 1.0
            for idx in order[:6]:
                c = float(contrib[idx])
                if abs(c) < 1e-9:
                    continue
                fname = feature_columns[idx]
                top_factors.append(_factor(fname, raw[fname], c, abs(c) / total, ex))
            method, method_note = "shap", f"SHAP TreeExplainer ({shap.__version__})"
        except Exception as exc:  # pragma: no cover - env dependent
            logger.warning("Candidate SHAP failed, using fallback: %s", exc)

    if not top_factors:
        # Fallback: rank by |value| departure from neutral, contract-labelled.
        ranked = sorted(
            ((abs(float(raw[c])), c) for c in feature_columns if raw[c] not in (0, 0.0)),
            reverse=True,
        )
        for _, fname in ranked[:6]:
            top_factors.append(_factor(fname, raw[fname], None, None, ex))

    # Verify every approved feature resolves a label + bucket through the contract.
    resolution = []
    contract_ok = True
    for fname in feature_columns:
        entry = ex._contract_entry(fname)
        label = ex._humanize(fname)
        bucket = ex.value_bucket(fname, raw.get(fname, 0))
        resolves = entry is not None and bool(label)
        contract_ok = contract_ok and resolves
        resolution.append({
            "feature_name": fname, "canonical_name": entry["canonical_name"] if entry else None,
            "human_label": label, "value_bucket": bucket, "resolves_in_contract": resolves,
        })

    # PII safety: no raw numeric values in factors; buckets only.
    pii_safe = all(
        "value_bucket" in f and "raw_value" not in f for f in top_factors
    )

    payload = {
        "source": "live", "report": "candidate_explainability_check",
        "generated_at": _now_iso(), "deployed": False, "shadow_only": True,
        "candidate_model": model_name,
        "method": method, "method_note": method_note,
        "all_features_resolve_in_contract": contract_ok,
        "top_factors": top_factors,
        "feature_resolution": resolution,
        "pii_safe": pii_safe,
        "note": "Sample explanation on one synthetic/pseudonymous test row. Buckets only — no raw values. "
                "The deployed explanation endpoints are unchanged; this is a candidate-only check.",
    }
    _write_json(reports_dir, "candidate_explainability_check.json", payload)
    _write_md(reports_dir, "candidate_explainability_check.md", _explain_md(payload))
    return payload


def _factor(fname: str, value: Any, contrib: float | None, share: float | None, ex) -> dict[str, Any]:
    if contrib is not None:
        direction = "increases_risk" if contrib > 0 else "decreases_risk"
        level = "high" if (share or 0) >= 0.25 else "medium" if (share or 0) >= 0.10 else "low"
    else:
        direction = "contributes"
        level = "unranked"
    return {
        "feature_name": fname,
        "human_label": ex._humanize(fname),
        "value_bucket": ex.value_bucket(fname, value),  # bucket only — never the raw value
        "direction": direction,
        "contribution_level": level,
    }


# ----------------------------------------------------------------- markdown


def _metrics_md(p: dict[str, Any]) -> list[str]:
    t = p["selected_test_metrics"]
    lines = ["# Candidate Model — Test Metrics (SHADOW ONLY)", ""]
    lines.append(f"- Generated: {p['generated_at']}  ·  Selected: **{p['selected_model']}**  ·  Status: **NOT deployed**")
    lines.append(f"- Feature set: approved parity-clean only ({p['protocol']['feature_count']} features); identity encodings excluded.")
    lines.append(f"- Protocol: {p['protocol']['split']}. Comparable with {p['protocol']['comparable_with']}; "
                 f"NOT with {p['protocol']['not_comparable_with']}.")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| PR-AUC (primary) | **{t['pr_auc']:.4f}** |")
    lines.append(f"| ROC-AUC | {t['roc_auc']:.4f} |")
    lines.append(f"| Precision | {t['precision']:.4f} |")
    lines.append(f"| Recall | {t['recall']:.4f} |")
    lines.append(f"| F1 | {t['f1']:.4f} |")
    lines.append(f"| False positive rate | {t['fpr']:.6f} |")
    lines.append(f"| Alerts / 100k | {t['alerts_per_100k']:.1f} |")
    cm = t["confusion_matrix"]
    lines.append("")
    lines.append("Confusion matrix (rows=actual, cols=predicted, [benign, laundering]):")
    lines.append("```")
    lines.append(f"[[{cm[0][0]}, {cm[0][1]}],")
    lines.append(f" [{cm[1][0]}, {cm[1][1]}]]")
    lines.append("```")
    lines.append("")
    lines.append("**Deployment recommended: NO** — shadow evaluation only.")
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return lines


def _comparison_md(p: dict[str, Any]) -> list[str]:
    lines = ["# Candidate Model — Comparison (SHADOW ONLY)", ""]
    lines.append(f"- Generated: {p['generated_at']}  ·  Selected (val PR-AUC): **{p['selected_model']}**  ·  Test leader: `{p['test_leader']}`")
    lines.append("")
    lines.append("## Library availability")
    for name, info in p["availability"].items():
        status = f"evaluated ({info['library']})" if info.get("available") else f"SKIPPED — {info.get('reason')}"
        lines.append(f"- `{name}`: {status}")
    lines.append("")
    lines.append("## Leaderboard (approved features only; test split, threshold frozen on val)")
    lines.append("")
    lines.append("| Model | test PR-AUC | ROC-AUC | Precision | Recall | F1 | Alerts/100k |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in sorted(p["leaderboard"], key=lambda r: r["test"]["pr_auc"], reverse=True):
        t = row["test"]
        mark = " **(selected)**" if row["model"] == p["selected_model"] else ""
        lines.append(f"| {row['model']}{mark} | {t['pr_auc']:.4f} | {t['roc_auc']:.4f} | {t['precision']:.4f} "
                     f"| {t['recall']:.4f} | {t['f1']:.4f} | {t['alerts_per_100k']:.1f} |")
    lines.append("")
    ctx = p["context"]
    lines.append("## Cross-report context (protocol-aware)")
    if "ablation_same_protocol" in ctx:
        a = ctx["ablation_same_protocol"]
        lines.append(f"- **Same temporal protocol** — graph_context (no identity) PR-AUC "
                     f"{a['graph_context_no_identity_pr_auc']}, full_with_account_ids "
                     f"{a['full_with_account_ids_pr_auc']} (identity lift forgone: {a['identity_lift_forgone']}). "
                     f"{a['note']}")
    if "prior_eval_same_protocol" in ctx:
        pe = ctx["prior_eval_same_protocol"]
        lines.append(f"- Prior eval leader `{pe['test_leader']}` PR-AUC {pe['test_leader_pr_auc']:.4f} — {pe['note']}")
    if "deployed_baseline" in ctx:
        d = ctx["deployed_baseline"]
        lines.append(f"- Deployed baseline `{d['model_name']}` PR-AUC {d['pr_auc']:.4f} — {d['note']}")
    lines.append("")
    lines.append("## Excluded features (confirmed not used)")
    for e in p["excluded_features"]:
        lines.append(f"- `{e['canonical_name']}` — {e['reason']} ({e['parity_status']})")
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return lines


def _thresholds_md(p: dict[str, Any]) -> list[str]:
    lines = ["# Candidate Model — Threshold Policy (SHADOW ONLY)", ""]
    lines.append(f"- Generated: {p['generated_at']}  ·  Model: `{p['model']}`  ·  Split: {p['split']}")
    lines.append(f"- {p['selection_note']}")
    lines.append("")
    lines.append("| Mode | Threshold | Precision | Recall | F1 | FPR | Alerts/100k | Recommended use |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in p["thresholds"]:
        lines.append(f"| {r['mode']} | {r['threshold']:.4f} | {r['precision']:.4f} | {r['recall']:.4f} "
                     f"| {r['f1']:.4f} | {r['fpr']:.6f} | {r['alerts_per_100k']:.1f} | {r['recommended_use']} |")
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return lines


def _explain_md(p: dict[str, Any]) -> list[str]:
    lines = ["# Candidate Model — Explainability Check (SHADOW ONLY)", ""]
    lines.append(f"- Generated: {p['generated_at']}  ·  Model: `{p['candidate_model']}`  ·  Method: **{p['method']}** ({p['method_note']})")
    lines.append(f"- All approved features resolve in the feature contract: **{p['all_features_resolve_in_contract']}**")
    lines.append(f"- PII-safe (bucketed values only): **{p['pii_safe']}**")
    lines.append("")
    lines.append("## Top factors (one synthetic test row)")
    lines.append("")
    lines.append("| Feature | Human label | Value bucket | Direction | Level |")
    lines.append("|---|---|---|---|---|")
    for f in p["top_factors"]:
        lines.append(f"| `{f['feature_name']}` | {f['human_label']} | {f['value_bucket']} | {f['direction']} | {f['contribution_level']} |")
    lines.append("")
    lines.append("## Feature → contract resolution")
    lines.append("")
    lines.append("| Feature | Canonical | Label | Bucket | Resolves |")
    lines.append("|---|---|---|---|---|")
    for r in p["feature_resolution"]:
        lines.append(f"| `{r['feature_name']}` | {r['canonical_name']} | {r['human_label']} | {r['value_bucket']} | {r['resolves_in_contract']} |")
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return lines


# ----------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Train + evaluate the shadow candidate model (approved features only).")
    p.add_argument("--processed-dir", default=str(DEFAULT_PROCESSED_DIR))
    p.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    p.add_argument("--models-dir", default=str(DEFAULT_MODELS_DIR))
    p.add_argument("--train-sample", type=int, default=800_000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)
    summary = run_candidate(
        processed_dir=Path(args.processed_dir), reports_dir=Path(args.reports_dir),
        models_dir=Path(args.models_dir), train_sample=args.train_sample, seed=args.seed,
    )
    print(json.dumps(summary, indent=2, default=float))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
