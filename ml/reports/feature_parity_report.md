# Feature Parity Report — Offline vs Online

- Contract: `feature-contract-2`  ·  Harness: deterministic synthetic replay over multiple scenarios (no real data)
- Scenarios: fan_in_then_sweep, fan_out_dispersion, cross_bank_pass_through, quiet_legitimate
- Point-in-time: every scenario reads focus features strictly after all its events; no future tx influences any feature
- Parity targets clean across ALL scenarios: **True**
- Name collisions resolved: **True** (remaining: none)
- Result counts: {'not_replayed': 7, 'definition_mismatch': 4, 'matched': 8, 'train_only': 12, 'serve_only': 13}

## Per-feature classification

| Canonical | Offline name | Online name | Contract | Result |
|---|---|---|---|---|
| `amount` | amount | amount | match | not_replayed |
| `is_cross_bank` | is_cross_bank | tx_is_cross_bank | name_only | not_replayed |
| `hour_of_day` | hour | — | match | not_replayed |
| `day_of_week` | day_of_week | — | match | not_replayed |
| `is_weekend` | is_weekend | — | match | not_replayed |
| `currency_code` | currency_enc | — | name_only | not_replayed |
| `payment_type_code` | payment_type_enc | — | name_only | not_replayed |
| `source_bank_code` | source_bank_enc | — | definition_mismatch | definition_mismatch |
| `target_bank_code` | target_bank_enc | — | definition_mismatch | definition_mismatch |
| `source_account_code` | source_account_enc | — | definition_mismatch | definition_mismatch |
| `target_account_code` | target_account_enc | — | definition_mismatch | definition_mismatch |
| `source_outflow_count_1h` | source_out_tx_count_1h | source_out_degree_1h | name_only | matched |
| `source_outflow_count_24h` | source_out_tx_count_24h | source_out_degree_24h | name_only | matched |
| `target_inflow_count_1h` | target_in_tx_count_1h | target_in_degree_1h | name_only | matched |
| `target_inflow_count_24h` | target_in_tx_count_24h | target_in_degree_24h | name_only | matched |
| `source_outflow_amount_1h` | source_out_amount_sum_1h | amount_sent_1h | name_only | matched |
| `source_outflow_amount_24h` | source_out_amount_sum_24h | amount_sent_24h | name_only | matched |
| `target_inflow_amount_1h` | target_in_amount_sum_1h | amount_received_1h | name_only | matched |
| `target_inflow_amount_24h` | target_in_amount_sum_24h | amount_received_24h | name_only | matched |
| `source_outflow_count_all_time` | source_out_tx_count_total_before | — | train_only | train_only |
| `source_outflow_amount_all_time` | source_out_amount_sum_total_before | — | train_only | train_only |
| `source_unique_targets_all_time` | source_unique_targets_total_before | — | train_only | train_only |
| `target_inflow_count_all_time` | target_in_tx_count_total_before | — | train_only | train_only |
| `target_inflow_amount_all_time` | target_in_amount_sum_total_before | — | train_only | train_only |
| `target_unique_sources_all_time` | target_unique_sources_total_before | — | train_only | train_only |
| `account_pair_count_all_time` | account_pair_tx_count_before | — | train_only | train_only |
| `account_pair_amount_all_time` | account_pair_amount_sum_before | — | train_only | train_only |
| `fan_in_count_24h` | fan_in_score | — | train_only | train_only |
| `fan_in_normalized_1h` | — | fan_in_normalized_1h | serve_only | serve_only |
| `fan_out_count_24h` | fan_out_score | — | train_only | train_only |
| `fan_out_normalized_1h` | — | fan_out_normalized_1h | serve_only | serve_only |
| `sweep_ratio_all_time` | sweep_ratio | — | train_only | train_only |
| `rolling_amount_ratio_24h` | — | rolling_amount_ratio | serve_only | serve_only |
| `rapid_movement_flag` | rapid_movement_flag | — | train_only | train_only |
| `sweep_after_fan_in_flag` | — | sweep_after_fan_in_flag | serve_only | serve_only |
| `cross_bank_transfer_count_24h` | — | cross_bank_transfer_count_24h | serve_only | serve_only |
| `account_velocity_zscore` | — | account_velocity_zscore | serve_only | serve_only |
| `scatter_gather_score` | — | scatter_gather_score | serve_only | serve_only |
| `simple_cycle_score` | — | simple_cycle_score | serve_only | serve_only |
| `unique_targets_1h` | — | unique_targets_1h | serve_only | serve_only |
| `unique_sources_1h` | — | unique_sources_1h | serve_only | serve_only |
| `new_beneficiary_flag` | — | new_beneficiary_flag | serve_only | serve_only |
| `beneficiary_age_bucket` | — | beneficiary_age_bucket | serve_only | serve_only |
| `first_seen_delta_bucket` | — | first_seen_delta_bucket | serve_only | serve_only |

## Per-scenario parity-target comparisons (offline value vs online value)

### fan_in_then_sweep (as_of 2024-05-01T10:16:00)

| Canonical | Offline | Online | Result |
|---|---|---|---|
| `amount` | None | None | not_replayed |
| `is_cross_bank` | None | None | not_replayed |
| `source_outflow_count_1h` | 2 | 2 | matched |
| `source_outflow_count_24h` | 2 | 2 | matched |
| `target_inflow_count_1h` | 5 | 5 | matched |
| `target_inflow_count_24h` | 5 | 5 | matched |
| `source_outflow_amount_1h` | 3200.0 | 3200.0 | matched |
| `source_outflow_amount_24h` | 3200.0 | 3200.0 | matched |
| `target_inflow_amount_1h` | 6000.0 | 6000.0 | matched |
| `target_inflow_amount_24h` | 6000.0 | 6000.0 | matched |

### fan_out_dispersion (as_of 2024-06-01T09:16:00)

| Canonical | Offline | Online | Result |
|---|---|---|---|
| `amount` | None | None | not_replayed |
| `is_cross_bank` | None | None | not_replayed |
| `source_outflow_count_1h` | 6 | 6 | matched |
| `source_outflow_count_24h` | 6 | 6 | matched |
| `target_inflow_count_1h` | 0 | 0 | matched |
| `target_inflow_count_24h` | 0 | 0 | matched |
| `source_outflow_amount_1h` | 4950.0 | 4950.0 | matched |
| `source_outflow_amount_24h` | 4950.0 | 4950.0 | matched |
| `target_inflow_amount_1h` | 0.0 | 0 | matched |
| `target_inflow_amount_24h` | 0.0 | 0 | matched |

### cross_bank_pass_through (as_of 2024-06-02T14:21:00)

| Canonical | Offline | Online | Result |
|---|---|---|---|
| `amount` | None | None | not_replayed |
| `is_cross_bank` | None | None | not_replayed |
| `source_outflow_count_1h` | 2 | 2 | matched |
| `source_outflow_count_24h` | 2 | 2 | matched |
| `target_inflow_count_1h` | 3 | 3 | matched |
| `target_inflow_count_24h` | 3 | 3 | matched |
| `source_outflow_amount_1h` | 5500.0 | 5500.0 | matched |
| `source_outflow_amount_24h` | 5500.0 | 5500.0 | matched |
| `target_inflow_amount_1h` | 6150.0 | 6150.0 | matched |
| `target_inflow_amount_24h` | 6150.0 | 6150.0 | matched |

### quiet_legitimate (as_of 2024-06-03T08:33:00)

| Canonical | Offline | Online | Result |
|---|---|---|---|
| `amount` | None | None | not_replayed |
| `is_cross_bank` | None | None | not_replayed |
| `source_outflow_count_1h` | 1 | 1 | matched |
| `source_outflow_count_24h` | 1 | 1 | matched |
| `target_inflow_count_1h` | 0 | 0 | matched |
| `target_inflow_count_24h` | 0 | 0 | matched |
| `source_outflow_amount_1h` | 1200.0 | 1200.0 | matched |
| `source_outflow_amount_24h` | 1200.0 | 1200.0 | matched |
| `target_inflow_amount_1h` | 0.0 | 0 | matched |
| `target_inflow_amount_24h` | 0.0 | 0 | matched |

## Train-only (offline cannot be served today)
`source_outflow_count_all_time`, `source_outflow_amount_all_time`, `source_unique_targets_all_time`, `target_inflow_count_all_time`, `target_inflow_amount_all_time`, `target_unique_sources_all_time`, `account_pair_count_all_time`, `account_pair_amount_all_time`, `fan_in_count_24h`, `fan_out_count_24h`, `sweep_ratio_all_time`, `rapid_movement_flag`

## Serve-only (online has no training counterpart — decision B)
`fan_in_normalized_1h`, `fan_out_normalized_1h`, `rolling_amount_ratio_24h`, `sweep_after_fan_in_flag`, `cross_bank_transfer_count_24h`, `account_velocity_zscore`, `scatter_gather_score`, `simple_cycle_score`, `unique_targets_1h`, `unique_sources_1h`, `new_beneficiary_flag`, `beneficiary_age_bucket`, `first_seen_delta_bucket`

## Definition mismatches (genuine train/serve conflicts — excluded)
- `source_bank_code` — Offline LabelEncoder codes are NOT reproducible at serving (scoring_service hashes the bank id); memorisation risk. PERMANENTLY EXCLUDED from the approved training set. The safe structural replacement for bank identity is 'is_cross_bank' (approved); per-counterparty newness is covered by the serve-only beneficiary_age_bucket / new_beneficiary_flag.
- `target_bank_code` — Same encoding-parity problem as source_bank_code; excluded from training.
- `source_account_code` — Account-identity memorisation (ablation showed lift here does not generalise); serving always sends -1 (unseen). EXCLUDED from training.
- `target_account_code` — Account-identity memorisation; serving always sends -1. EXCLUDED from training.

> Synthetic AMLworld-style replay; not production validation. Retraining/GNN stay blocked until the approved set is parity-clean end-to-end (it now is for the 8 windowed features) AND the serve-only/train-only gaps are reconciled per FEATURE_CONTRACT.md.
