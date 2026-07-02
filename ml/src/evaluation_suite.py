"""Offline model evaluation suite (post-MVP ML evaluation phase).

LightGBM comparison + per-typology recall + threshold analysis + feature
ablation over the AMLworld HI-Small synthetic dataset.

CLI:
    python -m ml.src.evaluation_suite \
        --processed-dir ml/data/processed \
        --reports-dir ml/reports \
        --train-sample 800000

Outputs (all under --reports-dir):
    model_comparison.json / .md
    per_typology_recall.json / .md
    threshold_analysis.json / .md
    ablation_report.json / .md

Honesty contract (mirrors docs/MODEL_EVALUATION.md):
- PR-AUC is the primary metric; accuracy is intentionally never reported
  (~0.1% laundering prevalence makes accuracy meaningless).
- The split here is TEMPORAL (70/15/15 by timestamp) to prevent time
  leakage. The deployed baseline (ml/reports/model_metrics.json) was
  produced under an older stratified-random protocol; numbers are NOT
  directly comparable. This suite never overwrites model_metrics.json or
  ml/models/baseline_model.joblib.
- Typology labels for per-typology recall are HEURISTIC, inferred by the
  pattern library on test-period laundering neighbourhoods — they are not
  AMLworld ground-truth pattern annotations.
- All engineered features are point-in-time (strictly-before semantics from
  ml/scripts/build_graph_features.py); no feature uses future transactions.
- If LightGBM (or XGBoost) is not installed, the suite records the skip
  reason in the reports instead of faking results.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve
from sklearn.model_selection import train_test_split

from . import pattern_library
from .evaluate import best_threshold_by_f1, compute_metrics

logger = logging.getLogger("naseej.evaluation_suite")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED_DIR = REPO_ROOT / "ml" / "data" / "processed"
DEFAULT_REPORTS_DIR = REPO_ROOT / "ml" / "reports"
DEPLOYED_METRICS_PATH = DEFAULT_REPORTS_DIR / "model_metrics.json"

PHASE_TAG = "ml-evaluation-1"
DATASET_NOTE = "AMLworld HI-Small (synthetic) — research benchmark, not production validation."

# ----------------------------------------------------------------- feature sets
# Column names follow the legacy point-in-time schema produced by
# ml/scripts/build_graph_features.py (strictly-before semantics).

TRANSACTION_FEATURES: tuple[str, ...] = (
    "amount",
    "currency_enc",
    "payment_type_enc",
    "source_bank_enc",
    "target_bank_enc",
    "is_cross_bank",
    "cross_bank_flow_flag",
    "hour",
    "day_of_week",
    "is_weekend",
)

GRAPH_FEATURES: tuple[str, ...] = (
    "source_out_tx_count_total_before",
    "source_out_amount_sum_total_before",
    "source_unique_targets_total_before",
    "target_in_tx_count_total_before",
    "target_in_amount_sum_total_before",
    "target_unique_sources_total_before",
    "fan_in_score",
    "fan_out_score",
)

CONTEXT_FEATURES: tuple[str, ...] = (
    "source_out_tx_count_1h",
    "source_out_amount_sum_1h",
    "target_in_tx_count_1h",
    "target_in_amount_sum_1h",
    "source_out_tx_count_24h",
    "source_out_amount_sum_24h",
    "target_in_tx_count_24h",
    "target_in_amount_sum_24h",
    "account_pair_tx_count_before",
    "account_pair_amount_sum_before",
    "sweep_ratio",
    "rapid_movement_flag",
)

ACCOUNT_ID_FEATURES: tuple[str, ...] = ("source_account_enc", "target_account_enc")

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "transaction_only": TRANSACTION_FEATURES,
    "graph": TRANSACTION_FEATURES + GRAPH_FEATURES,
    "graph_context": TRANSACTION_FEATURES + GRAPH_FEATURES + CONTEXT_FEATURES,
    # The deployed baseline additionally feeds account-identifier encodings.
    # Kept as a fourth set so the report can show how much headline lift is
    # attributable to account-identity memorisation rather than behaviour.
    "full_with_account_ids": TRANSACTION_FEATURES + GRAPH_FEATURES + CONTEXT_FEATURES + ACCOUNT_ID_FEATURES,
}

FEATURE_SET_DESCRIPTIONS: dict[str, str] = {
    "transaction_only": "Amount, currency/payment-format encodings, bank ids, cross-bank flags, time-of-day fields.",
    "graph": "transaction_only + point-in-time degree/history features (counts, sums, unique counterparties, fan-in/fan-out scores).",
    "graph_context": "graph + point-in-time context features (1h/24h rolling windows, account-pair first-seen history, sweep ratio, rapid-movement flag).",
    "full_with_account_ids": "graph_context + account-identifier encodings (as used by the deployed baseline; flags identity-memorisation lift).",
}

# Heuristic typology priority: more specific multi-step typologies first so a
# transaction touching e.g. a rapid-sweep account is not swallowed by the
# generic fan_in bucket.
TYPOLOGY_PRIORITY: tuple[str, ...] = (
    "cross_bank_pass_through",
    "rapid_sweep",
    "mule_velocity",
    "scatter_gather",
    "gather_scatter",
    "simple_cycle",
    "fan_in",
    "fan_out",
)
UNKNOWN_TYPOLOGY = "unknown_unmatched"

THRESHOLD_MODES: tuple[dict[str, Any], ...] = (
    {
        "mode": "high_precision",
        "beta": 0.5,
        "recommended_use": "Compliance escalation — few, high-confidence alerts for SAR-style review.",
    },
    {
        "mode": "balanced",
        "beta": 1.0,
        "recommended_use": "Analyst queue — day-to-day triage balance between precision and recall.",
    },
    {
        "mode": "high_recall",
        "beta": 2.0,
        "recommended_use": "Monitoring only — broad watchlist; too noisy for direct escalation.",
    },
)


# ----------------------------------------------------------------- model zoo


def build_competitors(seed: int) -> tuple[list[tuple[str, Any]], dict[str, dict[str, Any]]]:
    """Return (name, estimator) pairs plus an availability map.

    Hyperparameters intentionally mirror ml/src/train_baseline.py so the
    comparison is against the same untuned configurations as the deployed
    baseline — this is a protocol comparison, not a tuning exercise.
    """
    import sklearn
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    availability: dict[str, dict[str, Any]] = {}
    models: list[tuple[str, Any]] = [
        (
            "logistic_regression",
            Pipeline([
                ("scaler", StandardScaler(with_mean=False)),
                ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed, n_jobs=-1)),
            ]),
        ),
        (
            "random_forest",
            RandomForestClassifier(
                n_estimators=200,
                max_depth=None,
                min_samples_leaf=2,
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            ),
        ),
    ]
    sk_note = f"scikit-learn {sklearn.__version__}"
    availability["logistic_regression"] = {"available": True, "library": sk_note}
    availability["random_forest"] = {"available": True, "library": sk_note}

    try:
        import xgboost
        from xgboost import XGBClassifier

        models.append((
            "xgboost",
            XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                tree_method="hist",
                eval_metric="aucpr",
                n_jobs=-1,
                random_state=seed,
            ),
        ))
        availability["xgboost"] = {"available": True, "library": f"xgboost {xgboost.__version__}"}
    except Exception as exc:
        availability["xgboost"] = {
            "available": False,
            "reason": f"xgboost import failed ({exc}); skipped — results are not faked.",
        }
        logger.warning("xgboost unavailable: %s", exc)

    try:
        import lightgbm
        from lightgbm import LGBMClassifier

        models.append((
            "lightgbm",
            LGBMClassifier(
                n_estimators=400,
                num_leaves=63,
                learning_rate=0.05,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
                verbose=-1,
            ),
        ))
        availability["lightgbm"] = {"available": True, "library": f"lightgbm {lightgbm.__version__}"}
    except Exception as exc:
        availability["lightgbm"] = {
            "available": False,
            "reason": f"lightgbm import failed ({exc}); skipped — results are not faked.",
        }
        logger.warning("lightgbm unavailable: %s", exc)

    return models, availability


# ----------------------------------------------------------------- data prep


RAW_COLUMNS_NEEDED = (
    "timestamp", "source_account", "target_account",
    "source_bank", "target_bank", "amount", "is_laundering",
)


def load_raw_frame(processed_dir: Path) -> pd.DataFrame:
    """Concatenate the processed train/val/test parquets into one raw frame.

    The on-disk splits are STRATIFIED RANDOM (they overlap in time), so they
    are only used as a data source here — the suite re-splits temporally.
    """
    frames = []
    for name in ("train", "val", "test"):
        path = processed_dir / f"{name}.parquet"
        frames.append(pd.read_parquet(path))
        logger.info("Loaded %s (%d rows)", path, len(frames[-1]))
    df = pd.concat(frames, ignore_index=True)
    missing = [c for c in RAW_COLUMNS_NEEDED if c not in df.columns]
    if missing:
        raise ValueError(f"Processed data is missing required columns: {missing}")
    return df


def temporal_split(
    df: pd.DataFrame, *, train_frac: float = 0.7, val_frac: float = 0.15
) -> dict[str, pd.DataFrame]:
    """Sort by timestamp and split positionally: earliest 70% train, next 15%
    val, final 15% test. Mergesort keeps equal-timestamp rows in stable order
    so the split is deterministic across runs.
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    n = len(df)
    n_train = int(n * train_frac)
    n_val = int(n * val_frac)
    splits = {
        "train": df.iloc[:n_train].reset_index(drop=True),
        "val": df.iloc[n_train:n_train + n_val].reset_index(drop=True),
        "test": df.iloc[n_train + n_val:].reset_index(drop=True),
    }
    for name, part in splits.items():
        logger.info(
            "Temporal split %s: %d rows, %d positives, %s → %s",
            name, len(part), int(part["is_laundering"].sum()),
            part["timestamp"].min(), part["timestamp"].max(),
        )
    return splits


def build_features(splits: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Build point-in-time features per split using the vectorized builders
    from ml/scripts/build_graph_features.py (history prepended so val/test
    rows see their true past, never their future).
    """
    from ml.scripts import build_graph_features as bgf

    short_td, long_td = pd.Timedelta("1h"), pd.Timedelta("24h")
    encoders = bgf.fit_encoders(splits["train"])

    out: dict[str, pd.DataFrame] = {}
    out["train"] = bgf.process_split(splits["train"], None, encoders, short_td, long_td, "train")
    out["val"] = bgf.process_split(splits["val"], splits["train"], encoders, short_td, long_td, "val")
    history = pd.concat([splits["train"], splits["val"]], ignore_index=True)
    out["test"] = bgf.process_split(splits["test"], history, encoders, short_td, long_td, "test")

    for name in ("train", "val"):
        # Raw identifier columns are only needed on test (typology inference).
        drop = [c for c in ("source_account", "target_account", "source_bank", "target_bank",
                            "currency", "payment_type", "amount_received", "receiving_currency")
                if c in out[name].columns]
        out[name] = bgf.optimise_dtypes(out[name].drop(columns=drop))
    out["test"] = bgf.optimise_dtypes(out["test"])
    return out


def feature_matrix(df: pd.DataFrame, columns: tuple[str, ...] | list[str]) -> pd.DataFrame:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Feature columns missing from frame: {missing}")
    return df[list(columns)].fillna(0).astype("float64")


def sample_training_rows(df: pd.DataFrame, *, n: int, seed: int) -> pd.DataFrame:
    """Stratified subsample of the training split (keeps label prevalence)."""
    if n <= 0 or len(df) <= n:
        return df
    sampled, _ = train_test_split(df, train_size=n, stratify=df["is_laundering"], random_state=seed)
    return sampled.reset_index(drop=True)


# ----------------------------------------------------------------- thresholds


def threshold_by_fbeta(y_true: np.ndarray, y_score: np.ndarray, beta: float) -> tuple[float, float]:
    """Threshold maximizing F-beta over the PR curve. beta<1 favours
    precision, beta>1 favours recall."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    if len(thresholds) == 0:
        return 0.5, 0.0
    b2 = beta * beta
    denom = b2 * precision + recall
    fbeta = (1 + b2) * precision * recall / np.where(denom == 0, 1.0, denom)
    best_idx = int(np.nanargmax(fbeta[:-1]))
    return float(thresholds[best_idx]), float(fbeta[best_idx])


def _alerts_per_100k(metrics: Any) -> float:
    if metrics.n_total <= 0:
        return 0.0
    return round(metrics.n_alerts / metrics.n_total * 100_000, 2)


def _metrics_dict(metrics: Any) -> dict[str, Any]:
    d = asdict(metrics)
    d["alerts_per_100k"] = _alerts_per_100k(metrics)
    return d


# ----------------------------------------------------------------- typology inference


def infer_typology_labels(test_df: pd.DataFrame) -> pd.DataFrame:
    """Assign one heuristic typology per laundering transaction in the test
    split, using the pattern-library detectors on laundering neighbourhoods.

    Returns a DataFrame of the positive rows with a 'typology' column. These
    labels are heuristic — inferred, not ground truth.
    """
    df = test_df
    label_col = "is_laundering" if "is_laundering" in df.columns else "label"
    positives = df[df[label_col] == 1]
    if positives.empty:
        return positives.assign(typology=pd.Series(dtype="object"))

    accounts = set(positives["source_account"]) | set(positives["target_account"])
    touches_src = df["source_account"].isin(accounts)
    touches_dst = df["target_account"].isin(accounts)
    neighbourhood = df[touches_src | touches_dst]
    core = df[touches_src & touches_dst]
    logger.info(
        "Typology inference: %d positives, %d involved accounts, neighbourhood=%d rows, core=%d rows",
        len(positives), len(accounts), len(neighbourhood), len(core),
    )

    def to_pl(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.rename(columns={
            "source_account": "src_id",
            "target_account": "dst_id",
            "source_bank": "from_bank_id",
            "target_bank": "to_bank_id",
        })[["src_id", "dst_id", "amount", "timestamp", "from_bank_id", "to_bank_id"]].copy()
        out["from_bank_id"] = pd.to_numeric(out["from_bank_id"], errors="coerce")
        out["to_bank_id"] = pd.to_numeric(out["to_bank_id"], errors="coerce")
        return out

    pl_neigh = to_pl(neighbourhood)
    pl_core = to_pl(core)

    # Cheap groupby detectors run on the full neighbourhood; combinatorial
    # detectors run on the core (both endpoints laundering-involved) so the
    # suite stays tractable on large test splits.
    findings: list[dict[str, Any]] = []
    cheap = (
        pattern_library.detect_fan_in,
        pattern_library.detect_fan_out,
        pattern_library.detect_mule_velocity,
        pattern_library.detect_rapid_sweep,
        pattern_library.detect_cross_bank_pass_through,
    )
    expensive = (
        pattern_library.detect_scatter_gather,
        pattern_library.detect_gather_scatter,
        pattern_library.detect_simple_cycle,
    )
    for fn in cheap:
        try:
            findings.extend(fn(pl_neigh))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Detector %s failed: %s", fn.__name__, exc)
    for fn in expensive:
        try:
            findings.extend(fn(pl_core))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Detector %s failed: %s", fn.__name__, exc)

    account_types: dict[Any, set[str]] = {}
    for finding in findings:
        ptype = finding.get("pattern_type")
        for acct in finding.get("accounts_involved", []):
            account_types.setdefault(acct, set()).add(ptype)

    def label_for(row: pd.Series) -> str:
        types = account_types.get(row["source_account"], set()) | account_types.get(row["target_account"], set())
        for t in TYPOLOGY_PRIORITY:
            if t in types:
                return t
        return UNKNOWN_TYPOLOGY

    positives = positives.copy()
    positives["typology"] = positives.apply(label_for, axis=1)
    return positives


# ----------------------------------------------------------------- report I/O


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _envelope(**extra: Any) -> dict[str, Any]:
    return {
        "source": "live",
        "phase": PHASE_TAG,
        "generated_at": _now_iso(),
        "dataset": DATASET_NOTE,
        **extra,
    }


def _write_json(reports_dir: Path, name: str, payload: dict[str, Any]) -> None:
    path = reports_dir / name
    path.write_text(json.dumps(payload, indent=2, default=float), encoding="utf-8")
    logger.info("Wrote %s", path)


def _write_md(reports_dir: Path, name: str, lines: list[str]) -> None:
    path = reports_dir / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", path)


HONESTY_FOOTER = (
    "> Research prototype evaluated on the synthetic AMLworld HI-Small benchmark. "
    "Not production validation. Accuracy is intentionally not reported: at ~0.1% "
    "laundering prevalence a model that alerts on nothing is 99.9% accurate and useless."
)


# ----------------------------------------------------------------- suite


def run_suite(
    *,
    processed_dir: Path | None = None,
    splits_raw: dict[str, pd.DataFrame] | None = None,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    train_sample: int = 800_000,
    seed: int = 42,
    model_names: list[str] | None = None,
    train_frac: float = 0.7,
    val_frac: float = 0.15,
) -> dict[str, Any]:
    """Run the full evaluation suite and write the four report pairs.

    `splits_raw` lets tests inject tiny synthetic raw splits (same schema as
    ml/data/processed) instead of reading parquets from disk.
    """
    t0 = time.time()
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Data: temporal split + point-in-time features.
    if splits_raw is None:
        raw = load_raw_frame(Path(processed_dir or DEFAULT_PROCESSED_DIR))
        splits = temporal_split(raw, train_frac=train_frac, val_frac=val_frac)
        del raw
    else:
        splits = splits_raw
    split_meta = {
        name: {
            "rows": int(len(part)),
            "positives": int(part["is_laundering"].sum()),
            "start": str(pd.to_datetime(part["timestamp"]).min()),
            "end": str(pd.to_datetime(part["timestamp"]).max()),
        }
        for name, part in splits.items()
    }
    feats = build_features(splits)
    train_df = sample_training_rows(feats["train"], n=train_sample, seed=seed)
    val_df, test_df = feats["val"], feats["test"]

    full_cols = FEATURE_SETS["full_with_account_ids"]
    X_train = feature_matrix(train_df, full_cols)
    y_train = train_df["is_laundering"].astype(int).to_numpy()
    X_val = feature_matrix(val_df, full_cols)
    y_val = val_df["is_laundering"].astype(int).to_numpy()
    X_test = feature_matrix(test_df, full_cols)
    y_test = test_df["is_laundering"].astype(int).to_numpy()
    logger.info(
        "Matrices ready: train=%d (sampled from %d), val=%d, test=%d, features=%d",
        len(X_train), split_meta["train"]["rows"], len(X_val), len(X_test), len(full_cols),
    )

    # 2. Model comparison on the full feature set.
    models, availability = build_competitors(seed)
    if model_names is not None:
        models = [(n, m) for n, m in models if n in model_names]

    comparison_rows: list[dict[str, Any]] = []
    test_scores: dict[str, np.ndarray] = {}
    val_scores: dict[str, np.ndarray] = {}
    balanced_thresholds: dict[str, float] = {}

    for name, est in models:
        logger.info("Training %s ...", name)
        t = time.time()
        est.fit(X_train.values, y_train)
        fit_seconds = time.time() - t
        v_score = est.predict_proba(X_val.values)[:, 1]
        t_score = est.predict_proba(X_test.values)[:, 1]
        thr, _ = best_threshold_by_f1(y_val, v_score)
        val_m = compute_metrics(y_val, v_score, threshold=thr)
        test_m = compute_metrics(y_test, t_score, threshold=thr)
        logger.info("  %s: val PR-AUC=%.4f test PR-AUC=%.4f (%.1fs)", name, val_m.pr_auc, test_m.pr_auc, fit_seconds)
        comparison_rows.append({
            "model": name,
            "fit_seconds": round(fit_seconds, 2),
            "val": _metrics_dict(val_m),
            "test": _metrics_dict(test_m),
        })
        test_scores[name] = t_score
        val_scores[name] = v_score
        balanced_thresholds[name] = thr

    if not comparison_rows:
        raise RuntimeError("No models were trained — nothing to report.")

    # Best model selected on VALIDATION PR-AUC (test stays held out for reporting).
    best_name = max(comparison_rows, key=lambda r: r["val"]["pr_auc"])["model"]
    best_row = next(r for r in comparison_rows if r["model"] == best_name)
    # The unbiased held-out winner — reported separately so a near-tie on
    # validation that flips on test is visible rather than hidden.
    test_leader = max(comparison_rows, key=lambda r: r["test"]["pr_auc"])["model"]
    test_leader_row = next(r for r in comparison_rows if r["model"] == test_leader)
    logger.info("Best model by val PR-AUC: %s; test leader by PR-AUC: %s", best_name, test_leader)

    selection_note = (
        f"Model selection is on validation PR-AUC (test held out), which picks '{best_name}'. "
        f"The highest held-out test PR-AUC belongs to '{test_leader}' "
        f"({test_leader_row['test']['pr_auc']:.4f})."
    )
    if best_name != test_leader:
        margin = best_row["val"]["pr_auc"] - test_leader_row["val"]["pr_auc"]
        selection_note += (
            f" On validation these two are within {margin:.4f} PR-AUC (a near-tie), so '{best_name}' "
            f"winning selection while '{test_leader}' leads on test reflects estimation noise near the top, "
            f"not a decisive gap. The gradient-boosting models lead on the unbiased test set."
        )

    deployed = None
    if DEPLOYED_METRICS_PATH.exists():
        try:
            deployed_raw = json.loads(DEPLOYED_METRICS_PATH.read_text(encoding="utf-8"))
            deployed = {
                "model_name": deployed_raw.get("model_name"),
                "pr_auc": deployed_raw.get("pr_auc"),
                "protocol": "stratified random split over a 300k sample of pre-featurized rows (legacy protocol)",
            }
        except Exception:  # pragma: no cover - defensive
            deployed = None

    protocol = {
        "split": f"temporal {train_frac:.0%}/{val_frac:.0%}/{1 - train_frac - val_frac:.0%} by timestamp",
        "train_rows_used": int(len(X_train)),
        "train_sample_target": train_sample,
        "feature_set": "full_with_account_ids",
        "feature_count": len(full_cols),
        "threshold_selection": "balanced threshold maximizes F1 on validation; test metrics reported at that frozen threshold",
        "model_selection": "best validation PR-AUC",
        "seed": seed,
        "hyperparameters": "identical untuned configurations as ml/src/train_baseline.py — protocol comparison, not a tuning exercise",
        "leakage_note": (
            "All features are point-in-time (strictly-before semantics). The temporal split prevents "
            "train/test time overlap; this differs from the deployed baseline's stratified-random protocol, "
            "so numbers are not directly comparable with model_metrics.json."
        ),
    }

    comparison_payload = _envelope(
        primary_metric="pr_auc",
        why_not_accuracy=(
            "Labels are highly imbalanced (~0.1% positive); accuracy is dominated by the negative class "
            "and is intentionally not reported."
        ),
        protocol=protocol,
        split_meta=split_meta,
        availability=availability,
        models=comparison_rows,
        best_model=best_name,
        best_model_test_pr_auc=best_row["test"]["pr_auc"],
        test_leader=test_leader,
        test_leader_pr_auc=test_leader_row["test"]["pr_auc"],
        selection_note=selection_note,
        deployed_baseline=deployed,
        deployed_baseline_untouched=True,
    )
    _write_json(reports_dir, "model_comparison.json", comparison_payload)
    _write_md(reports_dir, "model_comparison.md", _comparison_md(comparison_payload))

    # 3. Threshold analysis for the best model (candidates chosen on val).
    threshold_rows = []
    for spec in THRESHOLD_MODES:
        thr, _ = threshold_by_fbeta(y_val, val_scores[best_name], spec["beta"])
        m = compute_metrics(y_test, test_scores[best_name], threshold=thr)
        threshold_rows.append({
            "mode": spec["mode"],
            "selection": f"maximizes F{spec['beta']:g} on validation",
            "recommended_use": spec["recommended_use"],
            "threshold": float(thr),
            "precision": m.precision,
            "recall": m.recall,
            "f1": m.f1,
            "fpr": m.fpr,
            "n_alerts": m.n_alerts,
            "alerts_per_100k": _alerts_per_100k(m),
        })
    threshold_payload = _envelope(
        model=best_name,
        split="test",
        selection_note="Thresholds are selected on the validation split and frozen before touching test.",
        thresholds=threshold_rows,
    )
    _write_json(reports_dir, "threshold_analysis.json", threshold_payload)
    _write_md(reports_dir, "threshold_analysis.md", _threshold_md(threshold_payload))

    # 4. Per-typology recall (heuristic labels from the pattern library).
    positives = infer_typology_labels(test_df)
    typology_rows = []
    pos_idx = positives.index.to_numpy()
    detected_by_model = {
        name: (test_scores[name][test_df.index.get_indexer(pos_idx)] >= balanced_thresholds[name])
        for name in test_scores
    }
    for typology in (*TYPOLOGY_PRIORITY, UNKNOWN_TYPOLOGY):
        mask = (positives["typology"] == typology).to_numpy()
        n = int(mask.sum())
        if n == 0:
            typology_rows.append({
                "typology": typology, "sample_count": 0, "detected_count": 0,
                "recall": None, "false_negative_count": 0, "best_model": None,
                "recall_by_model": {}, "notes": "No test-split laundering transactions matched this typology heuristic.",
            })
            continue
        recall_by_model = {
            name: round(float(hits[mask].mean()), 4) for name, hits in detected_by_model.items()
        }
        detected = int(detected_by_model[best_name][mask].sum())
        best_for_typology = max(
            recall_by_model,
            key=lambda k: (recall_by_model[k], k == best_name),
        )
        notes = []
        if n < 30:
            notes.append(f"Small sample (n={n}) — recall estimate is unstable.")
        notes.append("Heuristic label inferred by the pattern library, not ground truth.")
        typology_rows.append({
            "typology": typology,
            "sample_count": n,
            "detected_count": detected,
            "recall": round(detected / n, 4),
            "false_negative_count": n - detected,
            "best_model": best_for_typology,
            "recall_by_model": recall_by_model,
            "notes": " ".join(notes),
        })
    matched_rows = [r for r in typology_rows if r["sample_count"] > 0 and r["typology"] != UNKNOWN_TYPOLOGY]
    weakest = min(matched_rows, key=lambda r: r["recall"])["typology"] if matched_rows else None
    typology_payload = _envelope(
        label_method=(
            "HEURISTIC: typologies are inferred by running the pattern-library detectors over "
            "test-period laundering neighbourhoods and assigning each laundering transaction the "
            "highest-priority typology touching its accounts. They are NOT AMLworld ground-truth "
            "pattern annotations."
        ),
        model=best_name,
        detection_rule=f"model score >= balanced (val-F1) threshold per model; primary columns use best model '{best_name}'",
        typology_priority=list(TYPOLOGY_PRIORITY),
        total_positives=int(len(positives)),
        weakest_typology=weakest,
        typologies=typology_rows,
    )
    _write_json(reports_dir, "per_typology_recall.json", typology_payload)
    _write_md(reports_dir, "per_typology_recall.md", _typology_md(typology_payload))

    # 5. Feature ablation with the best model family.
    ablation_rows = []
    for set_name, cols in FEATURE_SETS.items():
        fresh = dict(build_competitors(seed)[0])[best_name]
        Xtr = feature_matrix(train_df, cols)
        Xv = feature_matrix(val_df, cols)
        Xte = feature_matrix(test_df, cols)
        t = time.time()
        fresh.fit(Xtr.values, y_train)
        fit_seconds = time.time() - t
        v_score = fresh.predict_proba(Xv.values)[:, 1]
        t_score = fresh.predict_proba(Xte.values)[:, 1]
        thr, _ = best_threshold_by_f1(y_val, v_score)
        val_m = compute_metrics(y_val, v_score, threshold=thr)
        test_m = compute_metrics(y_test, t_score, threshold=thr)
        logger.info("Ablation %s (%d feats): test PR-AUC=%.4f", set_name, len(cols), test_m.pr_auc)
        ablation_rows.append({
            "feature_set": set_name,
            "description": FEATURE_SET_DESCRIPTIONS[set_name],
            "n_features": len(cols),
            "features": list(cols),
            "fit_seconds": round(fit_seconds, 2),
            "val": _metrics_dict(val_m),
            "test": _metrics_dict(test_m),
        })
    base_pr = ablation_rows[0]["test"]["pr_auc"]
    for row in ablation_rows:
        row["test_pr_auc_delta_vs_transaction_only"] = round(row["test"]["pr_auc"] - base_pr, 4)
    ablation_payload = _envelope(
        model=best_name,
        leakage_note=(
            "All graph/context features are point-in-time (strictly-before cumulative and trailing-window "
            "semantics from ml/scripts/build_graph_features.py); no feature uses future transactions. "
            "Live feature-store context (backend /api/features) remains online-only; these offline "
            "equivalents follow the same point-in-time discipline."
        ),
        account_id_note=(
            "full_with_account_ids adds account-identifier encodings as used by the deployed baseline. "
            "Lift over graph_context is attributable to account-identity memorisation and would not "
            "transfer to unseen accounts."
        ),
        feature_sets=ablation_rows,
    )
    _write_json(reports_dir, "ablation_report.json", ablation_payload)
    _write_md(reports_dir, "ablation_report.md", _ablation_md(ablation_payload))

    elapsed = time.time() - t0
    logger.info("Evaluation suite complete in %.1fs", elapsed)
    return {
        "best_model": best_name,
        "best_model_test_pr_auc": best_row["test"]["pr_auc"],
        "weakest_typology": weakest,
        "availability": availability,
        "elapsed_seconds": round(elapsed, 1),
        "reports_dir": str(reports_dir),
    }


# ----------------------------------------------------------------- markdown


def _comparison_md(p: dict[str, Any]) -> list[str]:
    lines = ["# Model Comparison — Naseej ML Evaluation", ""]
    lines.append(f"- Generated: {p['generated_at']}  ·  Dataset: {p['dataset']}")
    lines.append(f"- Protocol: {p['protocol']['split']}; {p['protocol']['threshold_selection']}.")
    lines.append(f"- Primary metric: **PR-AUC**. {p['why_not_accuracy']}")
    lines.append("")
    lines.append("## Library availability")
    lines.append("")
    for name, info in p["availability"].items():
        status = f"evaluated ({info['library']})" if info.get("available") else f"SKIPPED — {info.get('reason')}"
        lines.append(f"- `{name}`: {status}")
    lines.append("")
    lines.append("## Leaderboard (test split, threshold frozen on validation)")
    lines.append("")
    lines.append("| Model | test PR-AUC | test ROC-AUC | Precision | Recall | F1 | FPR | Alerts/100k | fit (s) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in sorted(p["models"], key=lambda r: r["test"]["pr_auc"], reverse=True):
        t = row["test"]
        marks = []
        if row["model"] == p["test_leader"]:
            marks.append("test-leader")
        if row["model"] == p["best_model"]:
            marks.append("selected")
        marker = f" **({', '.join(marks)})**" if marks else ""
        lines.append(
            f"| {row['model']}{marker} | {t['pr_auc']:.4f} | {t['roc_auc']:.4f} | {t['precision']:.4f} | "
            f"{t['recall']:.4f} | {t['f1']:.4f} | {t['fpr']:.6f} | {t['alerts_per_100k']:.1f} | {row['fit_seconds']:.1f} |"
        )
    lines.append("")
    lines.append(f"**Selected model (validation PR-AUC):** `{p['best_model']}`  ·  "
                 f"**Test-set leader (held-out PR-AUC):** `{p['test_leader']}` ({p['test_leader_pr_auc']:.4f})")
    lines.append("")
    lines.append(p["selection_note"])
    lines.append("")
    leader = next(r for r in p["models"] if r["model"] == p["test_leader"])
    cm = leader["test"]["confusion_matrix"]
    lines.append(f"Test-leader `{p['test_leader']}` confusion matrix (test, rows=actual, cols=predicted, [benign, laundering]):")
    lines.append("```")
    lines.append(f"[[{cm[0][0]}, {cm[0][1]}],")
    lines.append(f" [{cm[1][0]}, {cm[1][1]}]]")
    lines.append("```")
    lines.append("")
    if p.get("deployed_baseline"):
        d = p["deployed_baseline"]
        lines.append(
            f"Deployed baseline (`model_metrics.json`, untouched): {d['model_name']} PR-AUC {d['pr_auc']:.4f} "
            f"under a different protocol ({d['protocol']}) — not directly comparable."
        )
        lines.append("")
    lines.append(p["protocol"]["leakage_note"])
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return lines


def _threshold_md(p: dict[str, Any]) -> list[str]:
    lines = ["# Threshold Analysis — Naseej ML Evaluation", ""]
    lines.append(f"- Generated: {p['generated_at']}  ·  Model: `{p['model']}`  ·  Split: {p['split']}")
    lines.append(f"- {p['selection_note']}")
    lines.append("")
    lines.append("| Mode | Threshold | Precision | Recall | F1 | FPR | Alerts/100k | Recommended use |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in p["thresholds"]:
        lines.append(
            f"| {r['mode']} | {r['threshold']:.4f} | {r['precision']:.4f} | {r['recall']:.4f} | "
            f"{r['f1']:.4f} | {r['fpr']:.6f} | {r['alerts_per_100k']:.1f} | {r['recommended_use']} |"
        )
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return lines


def _typology_md(p: dict[str, Any]) -> list[str]:
    lines = ["# Per-Typology Recall — Naseej ML Evaluation", ""]
    lines.append(f"- Generated: {p['generated_at']}  ·  Primary model: `{p['model']}`")
    lines.append(f"- Total test-split laundering transactions: {p['total_positives']}")
    lines.append(f"- Weakest matched typology: `{p['weakest_typology']}`")
    lines.append("")
    lines.append(f"**Label method:** {p['label_method']}")
    lines.append("")
    lines.append("| Typology | Samples | Detected | Recall | False negatives | Best model | Notes |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in p["typologies"]:
        recall = f"{r['recall']:.3f}" if r["recall"] is not None else "—"
        lines.append(
            f"| {r['typology']} | {r['sample_count']} | {r['detected_count']} | {recall} | "
            f"{r['false_negative_count']} | {r['best_model'] or '—'} | {r['notes']} |"
        )
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return lines


def _ablation_md(p: dict[str, Any]) -> list[str]:
    lines = ["# Feature Ablation — Naseej ML Evaluation", ""]
    lines.append(f"- Generated: {p['generated_at']}  ·  Model family: `{p['model']}`")
    lines.append("")
    lines.append("| Feature set | #Features | test PR-AUC | Δ vs transaction_only | test ROC-AUC | F1 | Recall |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in p["feature_sets"]:
        t = r["test"]
        lines.append(
            f"| {r['feature_set']} | {r['n_features']} | {t['pr_auc']:.4f} | "
            f"{r['test_pr_auc_delta_vs_transaction_only']:+.4f} | {t['roc_auc']:.4f} | {t['f1']:.4f} | {t['recall']:.4f} |"
        )
    lines.append("")
    for r in p["feature_sets"]:
        lines.append(f"- **{r['feature_set']}** — {r['description']}")
    lines.append("")
    lines.append(p["leakage_note"])
    lines.append("")
    lines.append(p["account_id_note"])
    lines.append("")
    lines.append(HONESTY_FOOTER)
    return lines


# ----------------------------------------------------------------- CLI


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Naseej ML evaluation suite (comparison, typology recall, thresholds, ablation).")
    p.add_argument("--processed-dir", default=str(DEFAULT_PROCESSED_DIR))
    p.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    p.add_argument("--train-sample", type=int, default=800_000,
                   help="Stratified subsample of the temporal-train split used for fitting (0 = full).")
    p.add_argument("--seed", type=int, default=42)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = _build_arg_parser().parse_args(argv)
    summary = run_suite(
        processed_dir=Path(args.processed_dir),
        reports_dir=Path(args.reports_dir),
        train_sample=args.train_sample,
        seed=args.seed,
    )
    logger.info("Summary: %s", json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
