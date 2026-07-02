# Threshold Analysis — Naseej ML Evaluation

- Generated: 2026-06-13T10:01:20Z  ·  Model: `random_forest`  ·  Split: test
- Thresholds are selected on the validation split and frozen before touching test.

| Mode | Threshold | Precision | Recall | F1 | FPR | Alerts/100k | Recommended use |
|---|---|---|---|---|---|---|---|
| high_precision | 0.2349 | 0.8201 | 0.3504 | 0.4910 | 0.000158 | 87.6 | Compliance escalation — few, high-confidence alerts for SAR-style review. |
| balanced | 0.1249 | 0.5742 | 0.5426 | 0.5580 | 0.000826 | 193.6 | Analyst queue — day-to-day triage balance between precision and recall. |
| high_recall | 0.0799 | 0.4085 | 0.6637 | 0.5057 | 0.001973 | 332.9 | Monitoring only — broad watchlist; too noisy for direct escalation. |

> Research prototype evaluated on the synthetic AMLworld HI-Small benchmark. Not production validation. Accuracy is intentionally not reported: at ~0.1% laundering prevalence a model that alerts on nothing is 99.9% accurate and useless.
