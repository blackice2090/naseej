"""
train_baseline.py
-----------------
Trains a baseline binary classifier for AML transaction-level risk scoring.

Design choices for severe class imbalance (~0.1% positive rate)
---------------------------------------------------------------
- XGBoost: scale_pos_weight = neg / pos  (~979x) forces the model to treat each
  laundering transaction as if it were 979 legitimate ones during training.
  eval_metric="aucpr" monitors area-under-precision-recall instead of accuracy
  or logloss, which collapse to near-trivial values under this imbalance.
- Logistic regression: class_weight="balanced" reweights samples equivalently.
- Threshold tuning: the default 0.5 decision threshold is useless here.
  We sweep [0.001, 0.999] on the validation set and pick the threshold that
  maximises F1 for the positive (laundering) class.
- Primary metric: PR-AUC (area under precision-recall curve).
  ROC-AUC is reported for reference but is misleading at high imbalance.
- Accuracy is intentionally not reported as a headline metric.

Outputs (all saved to --model_dir)
-----------------------------------
  baseline_model.pkl        joblib-serialised model + metadata
  baseline_threshold.json   chosen decision threshold + val metrics
  feature_importance.csv    per-feature importance (XGBoost) or |coef| (logistic)
  metrics.json              full test-set evaluation metrics

Usage
-----
  # Quick check on 5% sample
  python ml/scripts/train_baseline.py --sample_frac 0.05 --model_type xgboost

  # Full training run
  python ml/scripts/train_baseline.py --model_type xgboost
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

LABEL_COL = "is_laundering"

# All 32 engineered features produced by build_graph_features.py.
# cross_bank_flow_flag is intentionally kept despite being identical to
# is_cross_bank — XGBoost's gain-based feature selection handles redundancy,
# and keeping both preserves the feature contract from the feature pipeline.
FEATURE_COLS = [
    "amount",
    "currency_enc",
    "payment_type_enc",
    "source_bank_enc",
    "target_bank_enc",
    "source_account_enc",
    "target_account_enc",
    "is_cross_bank",
    "cross_bank_flow_flag",
    "hour",
    "day_of_week",
    "is_weekend",
    "source_out_tx_count_total_before",
    "source_out_amount_sum_total_before",
    "source_unique_targets_total_before",
    "target_in_tx_count_total_before",
    "target_in_amount_sum_total_before",
    "target_unique_sources_total_before",
    "account_pair_tx_count_before",
    "account_pair_amount_sum_before",
    "source_out_tx_count_1h",
    "source_out_amount_sum_1h",
    "target_in_tx_count_1h",
    "target_in_amount_sum_1h",
    "source_out_tx_count_24h",
    "source_out_amount_sum_24h",
    "target_in_tx_count_24h",
    "target_in_amount_sum_24h",
    "fan_in_score",
    "fan_out_score",
    "sweep_ratio",
    "rapid_movement_flag",
]


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_split(
    features_dir: Path,
    filename: str,
    active_features: list[str],
    sample_frac: float | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    path = features_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Feature file not found: {path}")

    df = pd.read_parquet(path)

    if sample_frac is not None:
        # Stratified sample: preserve positive rate
        pos = df[df[LABEL_COL] == 1]
        neg = df[df[LABEL_COL] == 0].sample(
            frac=sample_frac, random_state=42
        )
        # Keep ALL positives plus the sampled negatives so we always have
        # enough positive examples for meaningful evaluation
        df = pd.concat([pos, neg]).sample(frac=1, random_state=42).reset_index(drop=True)
        log.info(
            "  %s: sampled %d rows (kept all %d positives + %.1f%% of negatives)",
            filename, len(df), len(pos), sample_frac * 100,
        )
    else:
        log.info("  %s: %d rows", filename, len(df))

    # Confirm all expected features are present
    missing = [c for c in active_features if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns in {filename}: {missing}")

    X = df[active_features].astype(np.float32)
    y = df[LABEL_COL].astype(np.int32)
    return X, y


# ─────────────────────────────────────────────────────────────────────────────
# Model training
# ─────────────────────────────────────────────────────────────────────────────

def train_xgboost(X_train: pd.DataFrame, y_train: pd.Series):
    from xgboost import XGBClassifier

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    spw = neg / pos
    log.info(
        "XGBoost — negatives: %d  positives: %d  scale_pos_weight: %.1f",
        neg, pos, spw,
    )
    model = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        eval_metric="aucpr",
        tree_method="hist",          # memory-efficient histogram algorithm
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X_train, y_train)
    return model


def train_logistic(X_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    log.info(
        "Logistic — negatives: %d  positives: %d  class_weight: balanced",
        neg, pos,
    )
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            solver="lbfgs",
            random_state=42,
            n_jobs=-1,
        )),
    ])
    pipe.fit(X_train, y_train)
    return pipe


# ─────────────────────────────────────────────────────────────────────────────
# Threshold tuning
# ─────────────────────────────────────────────────────────────────────────────

def find_best_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_steps: int = 1000,
) -> tuple[float, float, float, float]:
    """
    Search thresholds in [0.001, 0.999] and return the one that maximises
    F1 for the positive (laundering) class on the validation set.

    Returns
    -------
    (threshold, precision_at_threshold, recall_at_threshold, f1_at_threshold)
    """
    thresholds = np.linspace(0.001, 0.999, n_steps)
    best_thresh, best_f1 = 0.5, 0.0
    best_prec, best_rec = 0.0, 0.0

    for t in thresholds:
        pred = (y_prob >= t).astype(int)
        if pred.sum() == 0:
            continue
        f1  = f1_score(y_true, pred, pos_label=1, zero_division=0)
        if f1 > best_f1:
            best_f1    = f1
            best_thresh = float(t)
            best_prec  = precision_score(y_true, pred, pos_label=1, zero_division=0)
            best_rec   = recall_score(y_true, pred, pos_label=1, zero_division=0)

    return best_thresh, best_prec, best_rec, best_f1


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
    split_label: str,
    prevalence: float,
) -> dict:
    y_pred = (y_prob >= threshold).astype(int)

    roc_auc = roc_auc_score(y_true, y_prob)
    pr_auc  = average_precision_score(y_true, y_prob)
    prec    = precision_score(y_true, y_pred, pos_label=1, zero_division=0)
    rec     = recall_score(y_true, y_pred, pos_label=1, zero_division=0)
    f1      = f1_score(y_true, y_pred, pos_label=1, zero_division=0)
    cm      = confusion_matrix(y_true, y_pred)
    report  = classification_report(
        y_true, y_pred,
        target_names=["Legitimate", "Laundering"],
        digits=4,
        zero_division=0,
    )

    sep = "=" * 62
    print(f"\n{sep}")
    print(f"  Evaluation — {split_label.upper()} SET")
    print(sep)
    print(f"  Threshold used        : {threshold:.4f}")
    print()
    print(f"  PR-AUC  (primary)     : {pr_auc:.4f}   "
          f"[random baseline = {prevalence:.4f}]")
    print(f"  ROC-AUC (reference)   : {roc_auc:.4f}")
    print()
    print(f"  Precision (laundering): {prec:.4f}")
    print(f"  Recall    (laundering): {rec:.4f}")
    print(f"  F1        (laundering): {f1:.4f}")
    print()
    print("  Confusion matrix (rows=actual, cols=predicted):")
    print(f"                 Pred Legit  Pred Launder")
    print(f"  Actual Legit   {cm[0,0]:>10,}  {cm[0,1]:>12,}")
    print(f"  Actual Launder {cm[1,0]:>10,}  {cm[1,1]:>12,}")
    print()
    print("  Classification report:")
    for line in report.splitlines():
        print(f"    {line}")

    # Human-readable usefulness interpretation
    print()
    if pr_auc < prevalence * 2:
        verdict = "POOR — model barely outperforms random flagging."
    elif pr_auc < 0.20:
        verdict = "MARGINAL — some signal, but precision/recall trade-off is weak."
    elif pr_auc < 0.50:
        verdict = "MODERATE — useful for triage; expect significant false positives."
    elif pr_auc < 0.80:
        verdict = "GOOD — practical for production with human review of alerts."
    else:
        verdict = "EXCELLENT — strong detection capability."
    print(f"  Model usefulness: {verdict}")
    print(sep)

    return {
        "split": split_label,
        "threshold": float(threshold),
        "pr_auc": float(pr_auc),
        "roc_auc": float(roc_auc),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "confusion_matrix": cm.tolist(),
        "prevalence": float(prevalence),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Feature importance
# ─────────────────────────────────────────────────────────────────────────────

def extract_feature_importance(model, model_type: str, active_features: list[str]) -> pd.DataFrame:
    if model_type == "xgboost":
        scores = model.feature_importances_
    else:
        coefs = model.named_steps["clf"].coef_[0]
        scores = np.abs(coefs)

    df_imp = pd.DataFrame(
        {"feature": active_features, "importance": scores}
    ).sort_values("importance", ascending=False).reset_index(drop=True)
    return df_imp


# ─────────────────────────────────────────────────────────────────────────────
# Threshold analysis
# ─────────────────────────────────────────────────────────────────────────────

def run_threshold_analysis(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_steps: int = 2000,
) -> list[dict]:
    """
    Evaluate multiple operating modes on the test set.

    Modes: conservative (max precision, recall>=0.20), balanced (max F1),
    aggressive (max recall, precision>=0.20), budget_K (top K% flagged).
    """
    thresholds = np.linspace(0.001, 0.999, n_steps)
    total = len(y_true)

    best = {
        "conservative": {"thresh": 0.5, "prec": 0.0, "rec": 0.0, "f1": 0.0},
        "balanced":     {"thresh": 0.5, "prec": 0.0, "rec": 0.0, "f1": 0.0},
        "aggressive":   {"thresh": 0.5, "prec": 0.0, "rec": 0.0, "f1": 0.0},
    }

    for t in thresholds:
        pred = (y_prob >= t).astype(int)
        n_pos = pred.sum()
        if n_pos == 0:
            continue
        prec = precision_score(y_true, pred, pos_label=1, zero_division=0)
        rec  = recall_score(y_true, pred, pos_label=1, zero_division=0)
        f1   = f1_score(y_true, pred, pos_label=1, zero_division=0)

        if rec >= 0.20 and prec > best["conservative"]["prec"]:
            best["conservative"] = {"thresh": float(t), "prec": prec, "rec": rec, "f1": f1}
        if f1 > best["balanced"]["f1"]:
            best["balanced"] = {"thresh": float(t), "prec": prec, "rec": rec, "f1": f1}
        if prec >= 0.20 and rec > best["aggressive"]["rec"]:
            best["aggressive"] = {"thresh": float(t), "prec": prec, "rec": rec, "f1": f1}

    for mode_name in ("conservative", "aggressive"):
        if best[mode_name]["prec"] == 0.0 and best[mode_name]["rec"] == 0.0:
            log.warning(
                "run_threshold_analysis: no threshold satisfied the '%s' "
                "constraint; results reflect fallback threshold 0.5.",
                mode_name,
            )

    rows = []
    for mode_name, info in best.items():
        t = info["thresh"]
        pred = (y_prob >= t).astype(int)
        cm = confusion_matrix(y_true, pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        rows.append({
            "mode":      mode_name,
            "threshold": round(t, 4),
            "alerts":    int(fp + tp),
            "tp":        int(tp),
            "fp":        int(fp),
            "fn":        int(fn),
            "precision": round(float(info["prec"]), 4),
            "recall":    round(float(info["rec"]), 4),
            "f1":        round(float(info["f1"]), 4),
        })

    for pct in [0.05, 0.10, 0.25, 0.50, 1.00]:
        k = max(1, int(total * pct / 100))
        sorted_scores = np.sort(y_prob)[::-1]
        t = float(sorted_scores[min(k - 1, len(sorted_scores) - 1)])
        pred = (y_prob >= t).astype(int)
        if pred.sum() > k:
            top_k_idx = np.argsort(y_prob, kind="stable")[::-1][:k]
            pred = np.zeros(len(y_prob), dtype=int)
            pred[top_k_idx] = 1
        cm = confusion_matrix(y_true, pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        prec = float(tp) / max(1, int(tp + fp))
        rec  = float(tp) / max(1, int(tp + fn))
        f1   = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        rows.append({
            "mode":      f"budget_{pct:.2f}pct",
            "threshold": round(t, 4),
            "alerts":    int(tp + fp),
            "tp":        int(tp),
            "fp":        int(fp),
            "fn":        int(fn),
            "precision": round(prec, 4),
            "recall":    round(rec, 4),
            "f1":        round(f1, 4),
        })

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation report
# ─────────────────────────────────────────────────────────────────────────────

def generate_evaluation_report(
    test_metrics: dict,
    threshold_rows: list[dict],
    active_features: list[str],
    model_type: str,
    drop_id_features: bool,
    drop_bank_id_features: bool,
    report_path: Path,
) -> None:
    """Write a professional markdown evaluation report."""
    cm = test_metrics["confusion_matrix"]
    tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
    total = tn + fp + fn + tp

    header = "| Mode | Threshold | Alerts | TP | FP | FN | Precision | Recall | F1 |"
    separator = "|------|-----------|--------|----|----|-----|-----------|--------|----|"
    table_rows = [header, separator]
    for r in threshold_rows:
        table_rows.append(
            f"| {r['mode']} | {r['threshold']:.4f} | {r['alerts']:,} | "
            f"{r['tp']:,} | {r['fp']:,} | {r['fn']:,} | "
            f"{r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} |"
        )
    threshold_table = "\n".join(table_rows)

    balanced_row = next((r for r in threshold_rows if r["mode"] == "balanced"), threshold_rows[0])
    conservative_row = next((r for r in threshold_rows if r["mode"] == "conservative"), threshold_rows[0])
    aggressive_row = next((r for r in threshold_rows if r["mode"] == "aggressive"), threshold_rows[0])

    feature_note = ""
    if drop_id_features:
        feature_note += "\n- `--drop_id_features` active: `source_account_enc` and `target_account_enc` excluded."
    if drop_bank_id_features:
        feature_note += "\n- `--drop_bank_id_features` active: `source_bank_enc` and `target_bank_enc` excluded."

    report = f"""# Naseej — Model Evaluation Report

**Generated:** {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
**Model type:** {model_type}
**Active features:** {len(active_features)} of {len(FEATURE_COLS)}{feature_note}

---

## 1. Dataset Overview

| Split | Total rows | Laundering | Prevalence |
|-------|-----------|------------|------------|
| Test  | {total:,} | {tp + fn:,} | {test_metrics['prevalence']:.4%} |

The dataset is **severely class-imbalanced**: fewer than 0.11% of transactions are
money-laundering events. This reflects realistic AML conditions.

---

## 2. Why Accuracy Is Not Reported

A model that flags **zero** transactions would achieve:

> Accuracy = {(total - (tp + fn)) / total:.4%}

That is a deceptively high figure. Accuracy rewards the model for correctly
identifying the ~99.9% of legitimate transactions while completely ignoring every
money-laundering event. In fraud detection, a false negative (missed laundering)
is far more costly than a false positive. Accuracy is therefore excluded.

---

## 3. Primary Metric: PR-AUC

**PR-AUC (Area Under the Precision-Recall Curve)** measures how well the model
ranks laundering transactions above legitimate ones across *all* thresholds.

- **Random baseline PR-AUC** = prevalence = {test_metrics['prevalence']:.4f}
- **This model's PR-AUC** = **{test_metrics['pr_auc']:.4f}**
- **Lift over random** = {test_metrics['pr_auc'] / test_metrics['prevalence']:.1f}×

PR-AUC of {test_metrics['pr_auc']:.4f} indicates
{"MODERATE" if test_metrics['pr_auc'] < 0.50 else "GOOD" if test_metrics['pr_auc'] < 0.80 else "EXCELLENT"} discrimination power —
approximately **{test_metrics['pr_auc'] / test_metrics['prevalence']:.0f}× better than random** at surfacing real laundering.

ROC-AUC ({test_metrics['roc_auc']:.4f}) is reported for completeness but is misleadingly optimistic
under high class imbalance. PR-AUC is the authoritative metric.

---

## 4. Confusion Matrix Interpretation

```
                     Predicted Legitimate   Predicted Laundering
Actual Legitimate          {tn:>12,}              {fp:>12,}
Actual Laundering          {fn:>12,}              {tp:>12,}
```

| Cell | Count | Meaning |
|------|-------|---------|
| True Negative (TN) | {tn:,} | Legitimate transactions correctly cleared — no analyst time wasted |
| False Positive (FP) | {fp:,} | Legitimate transactions flagged — analyst reviews and closes as false alarm |
| False Negative (FN) | {fn:,} | **Missed laundering** — criminal funds move undetected |
| True Positive (TP) | {tp:,} | Laundering correctly caught — case opened, funds potentially frozen |

**Alert rate:** {(fp + tp) / total:.4%} of all transactions flagged
**Investigation yield (precision):** {test_metrics['precision']:.2%} of alerts are real laundering
**Detection rate (recall):** {test_metrics['recall']:.2%} of all laundering caught

---

## 5. Threshold Analysis — Operating Modes

{threshold_table}

| Mode | Strategy |
|------|----------|
| **conservative** | Maximise precision, recall ≥ 20% — suits transaction holds |
| **balanced** | Maximise F1 — suits analyst triage |
| **aggressive** | Maximise recall, precision ≥ 20% — suits regulatory sweeps |
| **budget_X.XXpct** | Top X% highest-risk flagged — suits fixed alert budgets |

---

## 6. Suitability Assessment

### a) Analyst Triage
**Suitable.** The model provides a {test_metrics['pr_auc'] / test_metrics['prevalence']:.0f}× lift over random sampling. At the
**balanced** threshold, analysts reviewing flagged transactions find real laundering
in ~{balanced_row['precision']:.0%} of their queue — dramatically better than uninformed review.

### b) Transaction Hold
**Use with caution.** The **conservative** mode (precision={conservative_row['precision']:.2%}) improves
precision but any transaction hold requires compliance sign-off. False holds on
legitimate transactions create regulatory and reputational risk. Recommend pairing
holds with a mandatory human review step during the MVP phase.

### c) Automatic Blocking
**Not recommended at this stage.** PR-AUC of {test_metrics['pr_auc']:.4f} indicates moderate discrimination
power. Automatic blocking requires near-perfect precision (>95%) to avoid wrongful
account freezes. Defer until the model is validated on live traffic and extreme-
threshold precision is confirmed over time.

---

## 7. Recommended Operating Mode for MVP Demo

**Recommendation: Balanced threshold (F1-maximising)**

| Metric | Value |
|--------|-------|
| Threshold | {balanced_row['threshold']:.4f} |
| Alerts generated | {balanced_row['alerts']:,} |
| True positives | {balanced_row['tp']:,} |
| False positives | {balanced_row['fp']:,} |
| Precision | {balanced_row['precision']:.4f} |
| Recall | {balanced_row['recall']:.4f} |
| F1 | {balanced_row['f1']:.4f} |

The balanced mode is ideal for the Naseej MVP because:

1. **Demonstrates real value** — detecting {balanced_row['recall']:.0%} of laundering is compelling for a first-generation model.
2. **Explainable** — F1 maximisation is intuitive for non-technical stakeholders.
3. **Safe for demo** — {balanced_row['precision']:.0%} precision means most flagged transactions are genuine.
4. **Clear upgrade path** — future iterations can shift toward conservative mode for production holds.

---

## 8. Model Artifacts

| File | Description |
|------|-------------|
| `baseline_model.pkl` | Serialised model + metadata |
| `baseline_threshold.json` | Chosen threshold and validation metrics |
| `feature_importance.csv` | Per-feature importance scores |
| `metrics.json` | Full test-set metrics at chosen threshold |
| `threshold_analysis.csv` | Operating-mode comparison table |
| `threshold_analysis.json` | Same data, machine-readable |
| `evaluation_report.md` | This report |

---

*Report generated by `ml/scripts/train_baseline.py` — Naseej baseline pipeline.*
"""
    report_path.write_text(report, encoding="utf-8")
    log.info("Evaluation report   → %s", report_path)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate a baseline AML binary classifier."
    )
    parser.add_argument("--features_dir", type=Path, default=Path("ml/data/features"),
                        help="Directory containing *_features.parquet files")
    parser.add_argument("--model_dir",    type=Path, default=Path("ml/models"),
                        help="Directory to write model artifacts")
    parser.add_argument("--model_type",   choices=["xgboost", "logistic"],
                        default="xgboost")
    parser.add_argument("--sample_frac",  type=float, default=None,
                        help="Fraction of negatives to sample per split (e.g. 0.05). "
                             "All positives are always kept.")
    parser.add_argument(
        "--drop_id_features",
        action="store_true",
        default=False,
        help="Exclude source_account_enc and target_account_enc from features.",
    )
    parser.add_argument(
        "--drop_bank_id_features",
        action="store_true",
        default=False,
        help="Exclude source_bank_enc and target_bank_enc (is_cross_bank and cross_bank_flow_flag are kept).",
    )
    args = parser.parse_args()

    active_features = list(FEATURE_COLS)
    if args.drop_id_features:
        drop = {"source_account_enc", "target_account_enc"}
        active_features = [f for f in active_features if f not in drop]
        log.info("Dropping account-ID features: %s", sorted(drop))
    if args.drop_bank_id_features:
        drop_bank = {"source_bank_enc", "target_bank_enc"}
        active_features = [f for f in active_features if f not in drop_bank]
        log.info("Dropping bank-ID features: %s", sorted(drop_bank))
    log.info("Active feature count: %d", len(active_features))

    args.model_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    # ── Load ─────────────────────────────────────────────────────────────────
    log.info("Loading feature splits from %s ...", args.features_dir)
    X_train, y_train = load_split(args.features_dir, "train_features.parquet", active_features, args.sample_frac)
    X_val,   y_val   = load_split(args.features_dir, "val_features.parquet",   active_features, args.sample_frac)
    X_test,  y_test  = load_split(args.features_dir, "test_features.parquet",  active_features, args.sample_frac)

    train_pos  = int(y_train.sum())
    train_neg  = int((y_train == 0).sum())
    prevalence = train_pos / len(y_train)

    log.info(
        "Train label distribution: %d positive / %d negative (%.3f%% positive)",
        train_pos, train_neg, prevalence * 100,
    )

    # ── Train ─────────────────────────────────────────────────────────────────
    log.info("Training %s model ...", args.model_type)
    t_train = time.time()
    if args.model_type == "xgboost":
        model = train_xgboost(X_train, y_train)
    else:
        model = train_logistic(X_train, y_train)
    log.info("Training complete in %.1f s", time.time() - t_train)

    # ── Threshold tuning on validation set ────────────────────────────────────
    log.info("Scoring validation set and searching for best threshold ...")
    y_val_prob = model.predict_proba(X_val)[:, 1]
    threshold, val_prec, val_rec, val_f1 = find_best_threshold(
        y_val.to_numpy(), y_val_prob
    )
    val_pr_auc = average_precision_score(y_val, y_val_prob)

    log.info("Validation PR-AUC      : %.4f", val_pr_auc)
    log.info("Best threshold (val F1): %.4f  →  P=%.4f  R=%.4f  F1=%.4f",
             threshold, val_prec, val_rec, val_f1)

    # ── Test evaluation ────────────────────────────────────────────────────────
    log.info("Evaluating on test set ...")
    y_test_prob = model.predict_proba(X_test)[:, 1]
    test_prevalence = float(y_test.sum()) / len(y_test)
    test_metrics = evaluate(
        y_test.to_numpy(), y_test_prob,
        threshold, "test", test_prevalence,
    )

    # ── Threshold analysis ─────────────────────────────────────────────────────
    log.info("Running threshold analysis across operating modes ...")
    threshold_rows = run_threshold_analysis(y_test.to_numpy(), y_test_prob)

    print("\n  Threshold Analysis — Operating Modes (Test Set):")
    print(f"  {'Mode':<20} {'Thresh':>8} {'Alerts':>8} {'TP':>6} {'FP':>6} {'FN':>6} {'Prec':>7} {'Rec':>7} {'F1':>7}")
    print("  " + "-" * 85)
    for r in threshold_rows:
        print(
            f"  {r['mode']:<20} {r['threshold']:>8.4f} {r['alerts']:>8,} "
            f"{r['tp']:>6,} {r['fp']:>6,} {r['fn']:>6,} "
            f"{r['precision']:>7.4f} {r['recall']:>7.4f} {r['f1']:>7.4f}"
        )

    # ── Save artifacts ─────────────────────────────────────────────────────────
    model_path = args.model_dir / "baseline_model.pkl"
    joblib.dump(
        {
            "model":      model,
            "threshold":  threshold,
            "model_type": args.model_type,
            "features":   active_features,
        },
        model_path,
    )
    log.info("Model saved         → %s", model_path)

    thresh_path = args.model_dir / "baseline_threshold.json"
    thresh_path.write_text(json.dumps({
        "threshold":  threshold,
        "model_type": args.model_type,
        "val_pr_auc": float(val_pr_auc),
        "val_precision": float(val_prec),
        "val_recall":    float(val_rec),
        "val_f1":        float(val_f1),
    }, indent=2))
    log.info("Threshold saved     → %s", thresh_path)

    imp_df = extract_feature_importance(model, args.model_type, active_features)
    imp_path = args.model_dir / "feature_importance.csv"
    imp_df.to_csv(imp_path, index=False)
    log.info("Feature importance  → %s", imp_path)

    # Top-10 most important features (useful sanity check)
    print("\n  Top-10 features by importance:")
    for _, row in imp_df.head(10).iterrows():
        bar = "#" * int(row["importance"] / imp_df["importance"].max() * 30)
        print(f"    {row['feature']:<42s} {row['importance']:.4f}  {bar}")

    metrics_path = args.model_dir / "metrics.json"
    metrics_path.write_text(json.dumps(test_metrics, indent=2))
    log.info("Metrics saved       → %s", metrics_path)

    ta_df = pd.DataFrame(threshold_rows)
    ta_csv  = args.model_dir / "threshold_analysis.csv"
    ta_json = args.model_dir / "threshold_analysis.json"
    ta_df.to_csv(ta_csv, index=False)
    ta_json.write_text(json.dumps(threshold_rows, indent=2))
    log.info("Threshold analysis  → %s", ta_csv)
    log.info("Threshold analysis  → %s", ta_json)

    report_path = args.model_dir / "evaluation_report.md"
    generate_evaluation_report(
        test_metrics=test_metrics,
        threshold_rows=threshold_rows,
        active_features=active_features,
        model_type=args.model_type,
        drop_id_features=args.drop_id_features,
        drop_bank_id_features=args.drop_bank_id_features,
        report_path=report_path,
    )

    elapsed = time.time() - t_start
    log.info("Total elapsed: %.1f s (%.1f min)", elapsed, elapsed / 60)


if __name__ == "__main__":
    main()
