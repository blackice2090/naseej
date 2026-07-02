"""Model evaluation helpers (Phase 4).

Computes the imbalanced-classification metrics the dashboard cares about:
PR-AUC, ROC-AUC, precision, recall, F1, false positive rate, alert / confirmed
counts, and the F1-optimal probability threshold.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)


@dataclass
class Metrics:
    threshold: float
    pr_auc: float
    roc_auc: float
    precision: float
    recall: float
    f1: float
    fpr: float
    n_alerts: int
    n_confirmed_laundering: int
    n_total: int
    n_positive: int
    prevalence: float
    confusion_matrix: list[list[int]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def best_threshold_by_f1(y_true: np.ndarray, y_score: np.ndarray) -> tuple[float, float]:
    """Return (threshold, f1) maximizing F1 over the PR curve."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    f1 = 2 * precision * recall / np.where(precision + recall == 0, 1.0, precision + recall)
    f1[:-1]  # drop the last point that has no threshold associated
    if len(thresholds) == 0:
        return 0.5, 0.0
    best_idx = int(np.nanargmax(f1[:-1]))
    return float(thresholds[best_idx]), float(f1[best_idx])


def compute_metrics(
    y_true: np.ndarray,
    y_score: np.ndarray,
    *,
    threshold: float | None = None,
) -> Metrics:
    """Compute the full metric bundle at a given (or F1-optimal) threshold."""
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    if threshold is None:
        threshold, _ = best_threshold_by_f1(y_true, y_score)
    y_pred = (y_score >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    fpr = fp / max(fp + tn, 1)

    return Metrics(
        threshold=float(threshold),
        pr_auc=float(average_precision_score(y_true, y_score)),
        roc_auc=float(roc_auc_score(y_true, y_score)) if len(np.unique(y_true)) > 1 else float("nan"),
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        fpr=float(fpr),
        n_alerts=int(y_pred.sum()),
        n_confirmed_laundering=int(tp),
        n_total=int(len(y_true)),
        n_positive=int(y_true.sum()),
        prevalence=float(y_true.mean()),
        confusion_matrix=[[int(tn), int(fp)], [int(fn), int(tp)]],
    )


__all__ = ["Metrics", "compute_metrics", "best_threshold_by_f1"]
