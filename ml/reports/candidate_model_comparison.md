# Candidate Model — Comparison (SHADOW ONLY)

- Generated: 2026-06-13T16:18:02Z  ·  Selected (val PR-AUC): **xgboost**  ·  Test leader: `xgboost`

## Library availability
- `logistic_regression`: evaluated (scikit-learn 1.8.0)
- `random_forest`: evaluated (scikit-learn 1.8.0)
- `xgboost`: evaluated (xgboost 3.2.0)
- `lightgbm`: evaluated (lightgbm 4.6.0)

## Leaderboard (approved features only; test split, threshold frozen on val)

| Model | test PR-AUC | ROC-AUC | Precision | Recall | F1 | Alerts/100k |
|---|---|---|---|---|---|---|
| xgboost **(selected)** | 0.4247 | 0.9765 | 0.4400 | 0.4510 | 0.4454 | 210.0 |
| lightgbm | 0.3438 | 0.9693 | 0.3723 | 0.3959 | 0.3837 | 217.9 |
| random_forest | 0.3035 | 0.9450 | 0.3661 | 0.3511 | 0.3584 | 196.5 |
| logistic_regression | 0.0193 | 0.9362 | 0.0276 | 0.6464 | 0.0530 | 4795.1 |

## Cross-report context (protocol-aware)
- **Same temporal protocol** — graph_context (no identity) PR-AUC 0.5548008078184025, full_with_account_ids 0.5739926220170071 (identity lift forgone: 0.0192). Candidate uses a strict subset of graph_context (servable, parity-clean). The full_with_account_ids set adds account-id memorisation lift the candidate deliberately forgoes.
- Prior eval leader `lightgbm` PR-AUC 0.6118 — Same temporal split — directly comparable; that run included identity + serve/train-only features.
- Deployed baseline `xgboost` PR-AUC 0.2275 — NOT directly comparable — different split protocol. Shown for reference only.

## Excluded features (confirmed not used)
- `source_bank_code` — identity/memorisation risk (definition_mismatch)
- `target_bank_code` — identity/memorisation risk (definition_mismatch)
- `source_account_code` — identity/memorisation risk (definition_mismatch)
- `target_account_code` — identity/memorisation risk (definition_mismatch)
- `source_outflow_count_all_time` — not servable (all-time / no online twin) (train_only)
- `source_outflow_amount_all_time` — not servable (all-time / no online twin) (train_only)
- `source_unique_targets_all_time` — not servable (all-time / no online twin) (train_only)
- `target_inflow_count_all_time` — not servable (all-time / no online twin) (train_only)
- `target_inflow_amount_all_time` — not servable (all-time / no online twin) (train_only)
- `target_unique_sources_all_time` — not servable (all-time / no online twin) (train_only)
- `account_pair_count_all_time` — not servable (all-time / no online twin) (train_only)
- `account_pair_amount_all_time` — not servable (all-time / no online twin) (train_only)
- `fan_in_count_24h` — not servable (all-time / no online twin) (train_only)
- `fan_in_normalized_1h` — serving-only (no offline twin) (serve_only)
- `fan_out_count_24h` — not servable (all-time / no online twin) (train_only)
- `fan_out_normalized_1h` — serving-only (no offline twin) (serve_only)
- `sweep_ratio_all_time` — not servable (all-time / no online twin) (train_only)
- `rolling_amount_ratio_24h` — serving-only (no offline twin) (serve_only)
- `rapid_movement_flag` — not servable (all-time / no online twin) (train_only)
- `sweep_after_fan_in_flag` — serving-only (no offline twin) (serve_only)
- `cross_bank_transfer_count_24h` — serving-only (no offline twin) (serve_only)
- `account_velocity_zscore` — serving-only (no offline twin) (serve_only)
- `scatter_gather_score` — serving-only (no offline twin) (serve_only)
- `simple_cycle_score` — serving-only (no offline twin) (serve_only)
- `unique_targets_1h` — serving-only (no offline twin) (serve_only)
- `unique_sources_1h` — serving-only (no offline twin) (serve_only)
- `new_beneficiary_flag` — serving-only (no offline twin) (serve_only)
- `beneficiary_age_bucket` — serving-only (no offline twin) (serve_only)
- `first_seen_delta_bucket` — serving-only (no offline twin) (serve_only)

> SHADOW CANDIDATE — evaluated on synthetic AMLworld HI-Small, NOT deployed. The live model, scoring endpoint, demo, explainability, and offline fallback are unchanged. Accuracy is intentionally omitted (≈0.1% prevalence).
