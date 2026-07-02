# Candidate Model — Threshold Policy (SHADOW ONLY)

- Generated: 2026-06-13T16:18:02Z  ·  Model: `xgboost`  ·  Split: test
- Each threshold maximises its F-beta on validation, then is frozen before test.

| Mode | Threshold | Precision | Recall | F1 | FPR | Alerts/100k | Recommended use |
|---|---|---|---|---|---|---|---|
| high_precision | 0.1360 | 0.6821 | 0.3107 | 0.4269 | 0.000297 | 93.3 | Compliance escalation — few, high-confidence alerts for SAR-style review. |
| balanced | 0.0524 | 0.4400 | 0.4510 | 0.4454 | 0.001179 | 210.0 | Analyst queue — day-to-day triage balance between precision and recall. |
| high_recall | 0.0247 | 0.2599 | 0.5567 | 0.3543 | 0.003256 | 439.0 | Monitoring only — broad watchlist; too noisy for direct escalation. |

> SHADOW CANDIDATE — evaluated on synthetic AMLworld HI-Small, NOT deployed. The live model, scoring endpoint, demo, explainability, and offline fallback are unchanged. Accuracy is intentionally omitted (≈0.1% prevalence).
