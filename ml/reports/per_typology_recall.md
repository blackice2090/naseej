# Per-Typology Recall — Naseej ML Evaluation

- Generated: 2026-06-13T10:02:05Z  ·  Primary model: `random_forest`
- Total test-split laundering transactions: 1561
- Weakest matched typology: `mule_velocity`

**Label method:** HEURISTIC: typologies are inferred by running the pattern-library detectors over test-period laundering neighbourhoods and assigning each laundering transaction the highest-priority typology touching its accounts. They are NOT AMLworld ground-truth pattern annotations.

| Typology | Samples | Detected | Recall | False negatives | Best model | Notes |
|---|---|---|---|---|---|---|
| cross_bank_pass_through | 1335 | 747 | 0.560 | 588 | lightgbm | Heuristic label inferred by the pattern library, not ground truth. |
| rapid_sweep | 106 | 81 | 0.764 | 25 | random_forest | Heuristic label inferred by the pattern library, not ground truth. |
| mule_velocity | 62 | 3 | 0.048 | 59 | logistic_regression | Heuristic label inferred by the pattern library, not ground truth. |
| scatter_gather | 0 | 0 | — | 0 | — | No test-split laundering transactions matched this typology heuristic. |
| gather_scatter | 0 | 0 | — | 0 | — | No test-split laundering transactions matched this typology heuristic. |
| simple_cycle | 9 | 4 | 0.444 | 5 | xgboost | Small sample (n=9) — recall estimate is unstable. Heuristic label inferred by the pattern library, not ground truth. |
| fan_in | 16 | 7 | 0.438 | 9 | random_forest | Small sample (n=16) — recall estimate is unstable. Heuristic label inferred by the pattern library, not ground truth. |
| fan_out | 8 | 3 | 0.375 | 5 | logistic_regression | Small sample (n=8) — recall estimate is unstable. Heuristic label inferred by the pattern library, not ground truth. |
| unknown_unmatched | 25 | 2 | 0.080 | 23 | logistic_regression | Small sample (n=25) — recall estimate is unstable. Heuristic label inferred by the pattern library, not ground truth. |

> Research prototype evaluated on the synthetic AMLworld HI-Small benchmark. Not production validation. Accuracy is intentionally not reported: at ~0.1% laundering prevalence a model that alerts on nothing is 99.9% accurate and useless.
