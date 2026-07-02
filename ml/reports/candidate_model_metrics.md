# Candidate Model — Test Metrics (SHADOW ONLY)

- Generated: 2026-06-13T16:18:02Z  ·  Selected: **xgboost**  ·  Status: **NOT deployed**
- Feature set: approved parity-clean only (15 features); identity encodings excluded.
- Protocol: temporal 70%/15%/15% by timestamp. Comparable with model_comparison.json + ablation_report.json (same temporal protocol); NOT with model_metrics.json (deployed baseline used a stratified-random split).

| Metric | Value |
|---|---|
| PR-AUC (primary) | **0.4247** |
| ROC-AUC | 0.9765 |
| Precision | 0.4400 |
| Recall | 0.4510 |
| F1 | 0.4454 |
| False positive rate | 0.001179 |
| Alerts / 100k | 210.0 |

Confusion matrix (rows=actual, cols=predicted, [benign, laundering]):
```
[[759294, 896],
 [857, 704]]
```

**Deployment recommended: NO** — shadow evaluation only.

> SHADOW CANDIDATE — evaluated on synthetic AMLworld HI-Small, NOT deployed. The live model, scoring endpoint, demo, explainability, and offline fallback are unchanged. Accuracy is intentionally omitted (≈0.1% prevalence).
