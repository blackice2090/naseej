"""Baseline AML model trainer (Phase 4).

CLI:
    python -m ml.src.train_baseline \
        --input ml/data/samples/transactions_demo_5k.parquet \
        --output ml/models/baseline_model.joblib \
        --sample 100000

Inputs accepted:
- Processed Phase-2 parquet/CSV (src_id, dst_id, timestamp, amount, …, label).
  Graph features will be built inline by `ml.src.graph_features`.
- A pre-featurized parquet that already contains `label` plus columns from
  `graph_features.FEATURE_COLUMNS` (e.g. the existing ml/data/features/*.parquet).

Outputs (paths configurable but defaults set below):
- ml/models/baseline_model.joblib                (best model by val PR-AUC)
- ml/reports/model_metrics.json                  (full metric bundle on test)
- ml/reports/confusion_matrix.json
- ml/reports/feature_importance.json
- ml/reports/training_summary.md

NEVER overwrites ml/models/baseline_model.pkl (legacy artefact).
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import data_loader, graph_features, preprocessing
from .evaluate import compute_metrics, best_threshold_by_f1

logger = logging.getLogger("naseej.train_baseline")


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_OUT = REPO_ROOT / "ml" / "models" / "baseline_model.joblib"
DEFAULT_REPORTS_DIR = REPO_ROOT / "ml" / "reports"


# ----------------------------------------------------------------- loaders


NON_FEATURE_COLUMNS: frozenset[str] = frozenset({
    "label", "is_laundering", "timestamp", "src_id", "dst_id",
    "from_account", "to_account",
})


def _looks_featurized(df: pd.DataFrame) -> bool:
    cols = set(df.columns)
    if "label" in cols and len(set(graph_features.FEATURE_COLUMNS) & cols) >= 5:
        return True
    # Legacy schema: ml/data/features/*_features.parquet has is_laundering + many numerics.
    if "is_laundering" in cols and len(cols) >= 10:
        return True
    return False


def _select_feature_columns(df: pd.DataFrame) -> list[str]:
    """Use the canonical FEATURE_COLUMNS where they overlap; otherwise fall
    back to "every numeric column that isn't the label/ID/time."
    """
    cols = list(df.columns)
    canonical = [c for c in graph_features.FEATURE_COLUMNS if c in cols]
    if len(canonical) >= 5:
        return canonical
    return [
        c for c in cols
        if c not in NON_FEATURE_COLUMNS and pd.api.types.is_numeric_dtype(df[c])
    ]


def _load_and_prepare(
    input_path: Path, *, sample: int, seed: int, with_velocity: bool
) -> pd.DataFrame:
    raw = data_loader.load_transactions(input_path)
    raw = data_loader.normalize_columns(raw)

    if _looks_featurized(raw):
        logger.info("Input appears already featurized — skipping preprocessing.")
        df = raw
        if sample and sample > 0 and len(df) > sample:
            label_col = "label" if "label" in df.columns else ("is_laundering" if "is_laundering" in df.columns else None)
            df = data_loader.sample_transactions(df, n=sample, seed=seed, stratify_label=label_col)
            logger.info("Sampled featurized input down to %d rows.", len(df))
    else:
        report = data_loader.validate_schema(raw, strict=True)
        logger.info("Schema OK. rows_in=%d", report["row_count"])
        if sample and sample > 0 and len(raw) > sample:
            raw = data_loader.sample_transactions(raw, n=sample, seed=seed)
            logger.info("Sampled down to %d rows.", len(raw))
        proc = preprocessing.build_processed_table(raw)
        proc = preprocessing.select_default_columns(proc)
        df = graph_features.build_features(proc, with_velocity=with_velocity)

    # Canonicalize the label column name to `label` (some legacy parquets use is_laundering).
    if "label" not in df.columns and "is_laundering" in df.columns:
        df = df.copy()
        df["label"] = df["is_laundering"].astype("int8")
    if "label" not in df.columns:
        raise ValueError("No 'label' / 'is_laundering' column after preparation — cannot train.")
    return df


def _temporal_split(
    df: pd.DataFrame, *, train: float, val: float, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "timestamp" in df.columns and df["timestamp"].notna().any():
        df = df.sort_values("timestamp").reset_index(drop=True)
        n = len(df)
        n_train = int(n * train)
        n_val = int(n * val)
        return df.iloc[:n_train], df.iloc[n_train:n_train + n_val], df.iloc[n_train + n_val:]
    # Fallback: stratified shuffle.
    from sklearn.model_selection import train_test_split

    train_df, temp = train_test_split(df, train_size=train, stratify=df["label"], random_state=seed)
    rel_val = val / (1.0 - train)
    val_df, test_df = train_test_split(temp, train_size=rel_val, stratify=temp["label"], random_state=seed)
    return train_df, val_df, test_df


# ----------------------------------------------------------------- model zoo


def _build_models(seed: int) -> list[tuple[str, Any]]:
    """Return (name, estimator) pairs. xgboost optional; lightgbm optional."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

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
    try:
        from xgboost import XGBClassifier  # type: ignore

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
    except Exception as exc:
        logger.warning("xgboost not available, skipping: %s", exc)

    try:
        from lightgbm import LGBMClassifier  # type: ignore

        models.append((
            "lightgbm",
            LGBMClassifier(
                n_estimators=400,
                num_leaves=63,
                learning_rate=0.05,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
            ),
        ))
    except Exception as exc:
        logger.info("lightgbm not available, skipping: %s", exc)

    return models


# ----------------------------------------------------------------- importances


def _feature_importances(model: Any, feature_names: list[str]) -> list[dict[str, float]]:
    """Best-effort extraction; returns top-25 features sorted by importance."""
    importances: np.ndarray | None = None
    est = model
    # Unwrap sklearn Pipeline.
    if hasattr(est, "named_steps") and "clf" in getattr(est, "named_steps", {}):
        est = est.named_steps["clf"]
    if hasattr(est, "feature_importances_"):
        importances = np.asarray(est.feature_importances_, dtype=float)
    elif hasattr(est, "coef_"):
        importances = np.abs(np.asarray(est.coef_, dtype=float)).ravel()
    if importances is None or importances.size != len(feature_names):
        return []
    order = np.argsort(importances)[::-1]
    return [
        {"feature": feature_names[i], "importance": float(importances[i])}
        for i in order[:25]
    ]


# ----------------------------------------------------------------- main


def run(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = _build_arg_parser().parse_args(argv)

    in_path = Path(args.input)
    out_path = Path(args.output)
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    df = _load_and_prepare(in_path, sample=args.sample, seed=args.seed, with_velocity=not args.no_velocity)
    train_df, val_df, test_df = _temporal_split(df, train=args.train, val=args.val, seed=args.seed)
    logger.info("Splits: train=%d val=%d test=%d (label prevalence=%.5f)",
                len(train_df), len(val_df), len(test_df), float(df["label"].mean()))

    feat_cols = _select_feature_columns(df)
    if len(feat_cols) < 3:
        raise ValueError(f"Not enough usable feature columns: {feat_cols}")
    logger.info("Using %d feature columns.", len(feat_cols))

    def _X(d: pd.DataFrame) -> pd.DataFrame:
        return d[feat_cols].fillna(0).astype("float64")

    X_train, y_train = _X(train_df), train_df["label"].astype(int).to_numpy()
    X_val, y_val = _X(val_df), val_df["label"].astype(int).to_numpy()
    X_test, y_test = _X(test_df), test_df["label"].astype(int).to_numpy()

    if y_train.sum() == 0 or y_val.sum() == 0:
        logger.warning("Splits contain no positives — metrics will be degenerate.")

    leaderboard: list[dict[str, Any]] = []
    best_name: str | None = None
    best_pr_auc = -1.0
    best_model: Any = None

    for name, est in _build_models(args.seed):
        logger.info("Training %s ...", name)
        t = time.time()
        est.fit(X_train.values, y_train)
        if hasattr(est, "predict_proba"):
            val_score = est.predict_proba(X_val.values)[:, 1]
        else:
            val_score = est.decision_function(X_val.values)
        val_thr, val_f1 = best_threshold_by_f1(y_val, val_score)
        val_metrics = compute_metrics(y_val, val_score, threshold=val_thr)
        elapsed = time.time() - t
        logger.info("  %s: val PR-AUC=%.4f F1=%.4f (%.1fs)", name, val_metrics.pr_auc, val_metrics.f1, elapsed)
        leaderboard.append({
            "model": name,
            "val_pr_auc": val_metrics.pr_auc,
            "val_roc_auc": val_metrics.roc_auc,
            "val_f1": val_metrics.f1,
            "val_threshold": val_metrics.threshold,
            "fit_seconds": elapsed,
        })
        if val_metrics.pr_auc > best_pr_auc:
            best_pr_auc = val_metrics.pr_auc
            best_name = name
            best_model = est

    assert best_model is not None, "No model trained."
    logger.info("Best model: %s (val PR-AUC=%.4f)", best_name, best_pr_auc)

    # Final test-set evaluation at best-on-val threshold.
    if hasattr(best_model, "predict_proba"):
        test_score = best_model.predict_proba(X_test.values)[:, 1]
    else:
        test_score = best_model.decision_function(X_test.values)
    val_thr, _ = best_threshold_by_f1(y_val, best_model.predict_proba(X_val.values)[:, 1])
    test_metrics = compute_metrics(y_test, test_score, threshold=val_thr)

    # Persist artefacts.
    import joblib

    joblib.dump({"model": best_model, "feature_columns": feat_cols, "threshold": val_thr, "model_name": best_name}, out_path)
    logger.info("Saved model -> %s", out_path)

    metrics_payload = {
        "source": "live",
        "model_name": best_name,
        "leaderboard": leaderboard,
        "split": "test",
        "threshold": val_thr,
        **{k: v for k, v in asdict(test_metrics).items() if k != "confusion_matrix"},
        "trained_seconds": time.time() - t0,
        "sample": args.sample,
        "input": str(in_path),
        "n_train": len(train_df),
        "n_val": len(val_df),
        "n_test": len(test_df),
    }
    (reports_dir / "model_metrics.json").write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    cm = test_metrics.confusion_matrix
    (reports_dir / "confusion_matrix.json").write_text(json.dumps({
        "source": "live",
        "model_name": best_name,
        "split": "test",
        "threshold": val_thr,
        "matrix": cm,
        "rows": "actual",
        "cols": "predicted",
        "labels": ["benign", "laundering"],
    }, indent=2), encoding="utf-8")

    fi = _feature_importances(best_model, feat_cols)
    (reports_dir / "feature_importance.json").write_text(json.dumps({
        "source": "live",
        "model_name": best_name,
        "features": fi,
    }, indent=2), encoding="utf-8")

    summary = _markdown_summary(
        best_name, leaderboard, test_metrics, feat_cols, fi,
        n_train=len(train_df), n_val=len(val_df), n_test=len(test_df),
        input_path=in_path, out_path=out_path,
    )
    (reports_dir / "training_summary.md").write_text(summary, encoding="utf-8")
    logger.info("Wrote reports under %s", reports_dir)
    return 0


def _markdown_summary(
    best_name: str,
    leaderboard: list[dict[str, Any]],
    test_metrics: Any,
    feat_cols: list[str],
    fi: list[dict[str, float]],
    *,
    n_train: int,
    n_val: int,
    n_test: int,
    input_path: Path,
    out_path: Path,
) -> str:
    lines: list[str] = []
    lines.append(f"# Training Summary — Naseej Baseline ({best_name})\n")
    lines.append(f"- Input: `{input_path}`")
    lines.append(f"- Model artefact: `{out_path}`")
    lines.append(f"- Split sizes: train={n_train}, val={n_val}, test={n_test}")
    lines.append(f"- Feature columns ({len(feat_cols)}): {feat_cols}\n")
    lines.append("## Leaderboard (val)\n")
    lines.append("| Model | val PR-AUC | val ROC-AUC | val F1 | val threshold | fit (s) |")
    lines.append("|---|---|---|---|---|---|")
    for row in sorted(leaderboard, key=lambda r: r["val_pr_auc"], reverse=True):
        lines.append(
            f"| {row['model']} | {row['val_pr_auc']:.4f} | {row['val_roc_auc']:.4f} | "
            f"{row['val_f1']:.4f} | {row['val_threshold']:.4f} | {row['fit_seconds']:.1f} |"
        )
    lines.append("\n## Test metrics (best model at val-optimal threshold)\n")
    m = test_metrics
    lines.append(f"- PR-AUC: **{m.pr_auc:.4f}**")
    lines.append(f"- ROC-AUC: **{m.roc_auc:.4f}**")
    lines.append(f"- Precision: **{m.precision:.4f}**  ·  Recall: **{m.recall:.4f}**  ·  F1: **{m.f1:.4f}**")
    lines.append(f"- False Positive Rate: {m.fpr:.6f}")
    lines.append(f"- Alerts: {m.n_alerts}  ·  Confirmed laundering caught: {m.n_confirmed_laundering}  ·  Total positives: {m.n_positive}")
    lines.append(f"- Prevalence: {m.prevalence:.5f}")
    cm = m.confusion_matrix
    lines.append(f"\nConfusion matrix (rows=actual, cols=predicted, [benign, laundering]):")
    lines.append("```")
    lines.append(f"[[{cm[0][0]}, {cm[0][1]}],")
    lines.append(f" [{cm[1][0]}, {cm[1][1]}]]")
    lines.append("```")
    if fi:
        lines.append("\n## Top features\n")
        for f in fi[:10]:
            lines.append(f"- `{f['feature']}` — {f['importance']:.5f}")
    lines.append("\n> Research prototype. AMLworld synthetic data — not a production banking system.")
    return "\n".join(lines) + "\n"


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train Naseej baseline AML model (Phase 4).")
    p.add_argument("--input", required=True, help="Processed parquet/CSV (Phase 2 output) or a pre-featurized parquet.")
    p.add_argument("--output", default=str(DEFAULT_MODEL_OUT), help="Path for the model joblib.")
    p.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Where to write JSON / Markdown reports.")
    p.add_argument("--sample", type=int, default=0, help="If >0, sample N rows from the raw input before feature build.")
    p.add_argument("--train", type=float, default=0.7)
    p.add_argument("--val", type=float, default=0.15)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-velocity", action="store_true", help="Skip velocity features (faster).")
    return p


def main() -> int:
    return run()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
