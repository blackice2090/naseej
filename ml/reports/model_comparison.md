# Model Comparison — Naseej ML Evaluation

- Generated: 2026-06-13T10:01:19Z  ·  Dataset: AMLworld HI-Small (synthetic) — research benchmark, not production validation.
- Protocol: temporal 70%/15%/15% by timestamp; balanced threshold maximizes F1 on validation; test metrics reported at that frozen threshold.
- Primary metric: **PR-AUC**. Labels are highly imbalanced (~0.1% positive); accuracy is dominated by the negative class and is intentionally not reported.

## Library availability

- `logistic_regression`: evaluated (scikit-learn 1.8.0)
- `random_forest`: evaluated (scikit-learn 1.8.0)
- `xgboost`: evaluated (xgboost 3.2.0)
- `lightgbm`: evaluated (lightgbm 4.6.0)

## Leaderboard (test split, threshold frozen on validation)

| Model | test PR-AUC | test ROC-AUC | Precision | Recall | F1 | FPR | Alerts/100k | fit (s) |
|---|---|---|---|---|---|---|---|---|
| lightgbm **(test-leader)** | 0.6118 | 0.9832 | 0.6364 | 0.5561 | 0.5935 | 0.000652 | 179.1 | 13.9 |
| xgboost | 0.5784 | 0.9859 | 0.6168 | 0.5496 | 0.5813 | 0.000701 | 182.6 | 14.1 |
| random_forest **(selected)** | 0.5740 | 0.9658 | 0.5742 | 0.5426 | 0.5580 | 0.000826 | 193.6 | 70.2 |
| logistic_regression | 0.0434 | 0.9587 | 0.0470 | 0.4644 | 0.0854 | 0.019337 | 2024.9 | 4.8 |

**Selected model (validation PR-AUC):** `random_forest`  ·  **Test-set leader (held-out PR-AUC):** `lightgbm` (0.6118)

Model selection is on validation PR-AUC (test held out), which picks 'random_forest'. The highest held-out test PR-AUC belongs to 'lightgbm' (0.6118). On validation these two are within 0.0066 PR-AUC (a near-tie), so 'random_forest' winning selection while 'lightgbm' leads on test reflects estimation noise near the top, not a decisive gap. The gradient-boosting models lead on the unbiased test set.

Test-leader `lightgbm` confusion matrix (test, rows=actual, cols=predicted, [benign, laundering]):
```
[[759694, 496],
 [693, 868]]
```

Deployed baseline (`model_metrics.json`, untouched): xgboost PR-AUC 0.2275 under a different protocol (stratified random split over a 300k sample of pre-featurized rows (legacy protocol)) — not directly comparable.

All features are point-in-time (strictly-before semantics). The temporal split prevents train/test time overlap; this differs from the deployed baseline's stratified-random protocol, so numbers are not directly comparable with model_metrics.json.

> Research prototype evaluated on the synthetic AMLworld HI-Small benchmark. Not production validation. Accuracy is intentionally not reported: at ~0.1% laundering prevalence a model that alerts on nothing is 99.9% accurate and useless.
