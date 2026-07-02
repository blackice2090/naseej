"""
evaluate_model.py
-----------------
Loads a trained model artifact from ml/models/ and evaluates it against the
held-out test split in ml/data/features/test.parquet.

Outputs:
  - Classification report (precision, recall, F1 per class)
  - Confusion matrix
  - AUC-PR (area under precision-recall curve) — primary metric
  - AUC-ROC (secondary reference metric)
  - Precision-recall curve saved as ml/models/pr_curve.png

AUC-PR is the primary metric because the dataset is severely class-imbalanced;
AUC-ROC is optimistic under imbalance and is reported only for reference.

Usage:
    python ml/scripts/evaluate_model.py \
        --model_path ml/models/baseline_xgboost.joblib \
        --features_dir ml/data/features \
        --out_dir ml/models
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

CATEGORICAL_COLS = ["currency", "payment_type"]
LABEL_COL = "is_laundering"


def load_test(features_dir: Path, feature_cols: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    path = features_dir / "test.parquet"
    df = pd.read_parquet(path)
    for col in CATEGORICAL_COLS:
        df[col] = pd.Categorical(df[col]).codes
    X = df[feature_cols]
    y = df[LABEL_COL]
    return X, y


def save_pr_curve(y_true: np.ndarray, y_prob: np.ndarray, out_path: Path) -> None:
    prec, rec, _ = precision_recall_curve(y_true, y_prob)
    auc_pr = average_precision_score(y_true, y_prob)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(rec, prec, lw=2, label=f"AUC-PR = {auc_pr:.4f}")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve — Test Set")
    ax.legend()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("PR curve saved → %s", out_path)


def save_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, out_path: Path) -> None:
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(cm, display_labels=["Legit", "Laundering"])
    fig, ax = plt.subplots(figsize=(5, 4))
    disp.plot(ax=ax, colorbar=False)
    ax.set_title("Confusion Matrix — Test Set")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Confusion matrix saved → %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained AML classifier on the test set.")
    parser.add_argument("--model_path", type=Path, default=Path("ml/models/baseline_xgboost.joblib"))
    parser.add_argument("--features_dir", type=Path, default=Path("ml/data/features"))
    parser.add_argument("--out_dir", type=Path, default=Path("ml/models"))
    args = parser.parse_args()

    log.info("Loading model from %s", args.model_path)
    artifact = joblib.load(args.model_path)
    model = artifact["model"]
    threshold = artifact["threshold"]
    feature_cols = artifact["features"]

    log.info("Loading test set...")
    X_test, y_test = load_test(args.features_dir, feature_cols)

    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= threshold).astype(int)

    auc_pr = average_precision_score(y_test, y_prob)
    auc_roc = roc_auc_score(y_test, y_prob)

    print("\n=== Classification Report ===")
    print(classification_report(y_test, y_pred, target_names=["Legit", "Laundering"], digits=4))
    print(f"AUC-PR  (primary)  : {auc_pr:.4f}")
    print(f"AUC-ROC (reference): {auc_roc:.4f}")
    print(f"Threshold used     : {threshold:.4f}\n")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    save_pr_curve(y_test.to_numpy(), y_prob, args.out_dir / "pr_curve.png")
    save_confusion_matrix(y_test.to_numpy(), y_pred, args.out_dir / "confusion_matrix.png")

    log.info("Evaluation complete.")


if __name__ == "__main__":
    main()
