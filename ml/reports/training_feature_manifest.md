# Training Feature Manifest

- Contract: `feature-contract-2`  ·  Parity report: `ml/reports/feature_parity_report.json`
- Approved: **15**  ·  Excluded: **29**

**Policy:** Approved = trainable AND servable AND not identity-memorisation risk AND parity-clean. Account-id and bank-id encodings are EXCLUDED (memorisation + non-reproducible at serving). All-time cumulative and pair features are EXCLUDED (online prunes >25h). The fan_in/fan_out score name collisions are EXCLUDED until reconciled.

## ✅ Approved training features

| Canonical | Offline name | Online name | Parity | Explainable |
|---|---|---|---|---|
| `amount` | amount | amount | match | True |
| `is_cross_bank` | is_cross_bank | tx_is_cross_bank | name_only | True |
| `hour_of_day` | hour | — | match | True |
| `day_of_week` | day_of_week | — | match | True |
| `is_weekend` | is_weekend | — | match | True |
| `currency_code` | currency_enc | — | name_only | True |
| `payment_type_code` | payment_type_enc | — | name_only | True |
| `source_outflow_count_1h` | source_out_tx_count_1h | source_out_degree_1h | name_only | True |
| `source_outflow_count_24h` | source_out_tx_count_24h | source_out_degree_24h | name_only | True |
| `target_inflow_count_1h` | target_in_tx_count_1h | target_in_degree_1h | name_only | True |
| `target_inflow_count_24h` | target_in_tx_count_24h | target_in_degree_24h | name_only | True |
| `source_outflow_amount_1h` | source_out_amount_sum_1h | amount_sent_1h | name_only | True |
| `source_outflow_amount_24h` | source_out_amount_sum_24h | amount_sent_24h | name_only | True |
| `target_inflow_amount_1h` | target_in_amount_sum_1h | amount_received_1h | name_only | True |
| `target_inflow_amount_24h` | target_in_amount_sum_24h | amount_received_24h | name_only | True |

## 🚫 Excluded features

| Canonical | Reason | Memorisation risk | Leakage |
|---|---|---|---|
| `source_bank_code` | identity/memorisation risk — not servable consistently and does not generalise | True | high |
| `target_bank_code` | identity/memorisation risk — not servable consistently and does not generalise | True | high |
| `source_account_code` | identity/memorisation risk — not servable consistently and does not generalise | True | high |
| `target_account_code` | identity/memorisation risk — not servable consistently and does not generalise | True | high |
| `source_outflow_count_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | low |
| `source_outflow_amount_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | medium |
| `source_unique_targets_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | low |
| `target_inflow_count_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | low |
| `target_inflow_amount_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | medium |
| `target_unique_sources_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | low |
| `account_pair_count_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | low |
| `account_pair_amount_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | medium |
| `fan_in_count_24h` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | low |
| `fan_in_normalized_1h` | not a training feature (serve-only / online-only) | False | low |
| `fan_out_count_24h` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | low |
| `fan_out_normalized_1h` | not a training feature (serve-only / online-only) | False | low |
| `sweep_ratio_all_time` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | medium |
| `rolling_amount_ratio_24h` | not a training feature (serve-only / online-only) | False | medium |
| `rapid_movement_flag` | not servable: online store cannot reproduce this definition (see mismatch_notes) | False | low |
| `sweep_after_fan_in_flag` | not a training feature (serve-only / online-only) | False | low |
| `cross_bank_transfer_count_24h` | not a training feature (serve-only / online-only) | False | medium |
| `account_velocity_zscore` | not a training feature (serve-only / online-only) | False | low |
| `scatter_gather_score` | not a training feature (serve-only / online-only) | False | low |
| `simple_cycle_score` | not a training feature (serve-only / online-only) | False | low |
| `unique_targets_1h` | not a training feature (serve-only / online-only) | False | low |
| `unique_sources_1h` | not a training feature (serve-only / online-only) | False | low |
| `new_beneficiary_flag` | not a training feature (serve-only / online-only) | False | low |
| `beneficiary_age_bucket` | not a training feature (serve-only / online-only) | False | low |
| `first_seen_delta_bucket` | not a training feature (serve-only / online-only) | False | low |

**Identity/memorisation-flagged:** `source_bank_code`, `target_bank_code`, `source_account_code`, `target_account_code`

> Synthetic-benchmark manifest. Approval here is a parity/leakage gate, NOT a production sign-off. The deployed model is not retrained in this phase.
