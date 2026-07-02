# Training Summary — Naseej Baseline (xgboost)

- Input: `ml\data\features\train_features.parquet`
- Model artefact: `ml\models\baseline_model.joblib`
- Split sizes: train=210000, val=44999, test=45001
- Feature columns (32): ['amount', 'currency_enc', 'payment_type_enc', 'source_bank_enc', 'target_bank_enc', 'source_account_enc', 'target_account_enc', 'is_cross_bank', 'cross_bank_flow_flag', 'hour', 'day_of_week', 'is_weekend', 'source_out_tx_count_total_before', 'source_out_amount_sum_total_before', 'source_unique_targets_total_before', 'target_in_tx_count_total_before', 'target_in_amount_sum_total_before', 'target_unique_sources_total_before', 'account_pair_tx_count_before', 'account_pair_amount_sum_before', 'source_out_tx_count_1h', 'source_out_amount_sum_1h', 'target_in_tx_count_1h', 'target_in_amount_sum_1h', 'source_out_tx_count_24h', 'source_out_amount_sum_24h', 'target_in_tx_count_24h', 'target_in_amount_sum_24h', 'fan_in_score', 'fan_out_score', 'sweep_ratio', 'rapid_movement_flag']

## Leaderboard (val)

| Model | val PR-AUC | val ROC-AUC | val F1 | val threshold | fit (s) |
|---|---|---|---|---|---|
| xgboost | 0.2271 | 0.9697 | 0.2955 | 0.0606 | 4.3 |
| random_forest | 0.1356 | 0.9109 | 0.2692 | 0.1349 | 13.7 |
| logistic_regression | 0.0244 | 0.9519 | 0.0732 | 0.9970 | 4.1 |

## Test metrics (best model at val-optimal threshold)

- PR-AUC: **0.2275**
- ROC-AUC: **0.9516**
- Precision: **0.2727**  ·  Recall: **0.1957**  ·  F1: **0.2278**
- False Positive Rate: 0.000534
- Alerts: 33  ·  Confirmed laundering caught: 9  ·  Total positives: 46
- Prevalence: 0.00102

Confusion matrix (rows=actual, cols=predicted, [benign, laundering]):
```
[[44931, 24],
 [37, 9]]
```

## Top features

- `payment_type_enc` — 0.21146
- `account_pair_tx_count_before` — 0.15440
- `is_cross_bank` — 0.07599
- `target_unique_sources_total_before` — 0.04717
- `cross_bank_flow_flag` — 0.04457
- `account_pair_amount_sum_before` — 0.03560
- `source_out_amount_sum_total_before` — 0.03271
- `source_out_tx_count_24h` — 0.02930
- `fan_out_score` — 0.02783
- `target_in_tx_count_1h` — 0.02702

> Research prototype. AMLworld synthetic data — not a production banking system.
