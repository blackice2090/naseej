# Candidate Model — Explainability Check (SHADOW ONLY)

- Generated: 2026-06-13T16:18:04Z  ·  Model: `xgboost`  ·  Method: **shap** (SHAP TreeExplainer (0.51.0))
- All approved features resolve in the feature contract: **True**
- PII-safe (bucketed values only): **True**

## Top factors (one synthetic test row)

| Feature | Human label | Value bucket | Direction | Level |
|---|---|---|---|---|
| `payment_type_enc` | Payment type | known_category | decreases_risk | high |
| `source_out_amount_sum_1h` | Source sent volume in last 1h | micro | decreases_risk | medium |
| `source_out_tx_count_24h` | Source sends in last 24h | none | decreases_risk | low |
| `day_of_week` | Day of week | weekday | decreases_risk | low |
| `amount` | Transaction amount | micro | decreases_risk | low |
| `hour` | Time of day | off_hours | decreases_risk | low |

## Feature → contract resolution

| Feature | Canonical | Label | Bucket | Resolves |
|---|---|---|---|---|
| `amount` | amount | Transaction amount | micro | True |
| `is_cross_bank` | is_cross_bank | Cross-bank transfer | cross_bank | True |
| `hour` | hour_of_day | Time of day | off_hours | True |
| `day_of_week` | day_of_week | Day of week | weekday | True |
| `is_weekend` | is_weekend | Weekend timing | weekday | True |
| `currency_enc` | currency_code | Currency | known_category | True |
| `payment_type_enc` | payment_type_code | Payment type | known_category | True |
| `source_out_tx_count_1h` | source_outflow_count_1h | Source sends in last 1h | none | True |
| `source_out_tx_count_24h` | source_outflow_count_24h | Source sends in last 24h | none | True |
| `target_in_tx_count_1h` | target_inflow_count_1h | Beneficiary inflows in last 1h | none | True |
| `target_in_tx_count_24h` | target_inflow_count_24h | Beneficiary inflows in last 24h | none | True |
| `source_out_amount_sum_1h` | source_outflow_amount_1h | Source sent volume in last 1h | micro | True |
| `source_out_amount_sum_24h` | source_outflow_amount_24h | Source sent volume in last 24h | micro | True |
| `target_in_amount_sum_1h` | target_inflow_amount_1h | Beneficiary inflow volume in last 1h | micro | True |
| `target_in_amount_sum_24h` | target_inflow_amount_24h | Beneficiary inflow volume in last 24h | micro | True |

> SHADOW CANDIDATE — evaluated on synthetic AMLworld HI-Small, NOT deployed. The live model, scoring endpoint, demo, explainability, and offline fallback are unchanged. Accuracy is intentionally omitted (≈0.1% prevalence).
