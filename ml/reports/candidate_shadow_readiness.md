# Candidate Shadow-Scoring Readiness (SHADOW ONLY)

- Generated: 2026-06-13T16:36:25Z  ·  Deployed: **False**  ·  Deployment recommended: **False**

## Artifact availability

| Artifact | Present |
|---|---|
| `candidate_model_joblib` | ✅ |
| `candidate_model_metrics` | ✅ |
| `candidate_thresholds` | ✅ |
| `feature_contract` | ✅ |
| `training_feature_manifest` | ✅ |

## Feature availability

- Approved feature count: **15**
- Intrinsic (from payload): `amount`, `is_cross_bank`, `hour`, `day_of_week`, `is_weekend`, `currency_enc`, `payment_type_enc`
- Windowed (from online store): `source_out_tx_count_1h`, `source_out_tx_count_24h`, `source_out_amount_sum_1h`, `source_out_amount_sum_24h`, `target_in_tx_count_1h`, `target_in_tx_count_24h`, `target_in_amount_sum_1h`, `target_in_amount_sum_24h`
- Missing-feature behaviour: no node window history or unparseable timestamp → missing_feature, not scored
- Excluded (confirmed never used): `source_account_code`, `target_account_code`, `source_bank_code`, `target_bank_code`, `source_outflow_count_all_time`, `target_inflow_count_all_time`, `account_pair_count_all_time`, `fan_in_count_24h`, `fan_out_count_24h`, `fan_in_normalized_1h`, `fan_out_normalized_1h`, `scatter_gather_score`, `simple_cycle_score`, `account_velocity_zscore`, `sweep_after_fan_in_flag`

## Endpoint

- `POST /api/model/candidate/score-shadow`
- Auth: node API key; source_node_id must match the authenticated node
- PII guard: same find_transaction_pii guard as /api/features/score-with-context
- Audited: True  ·  Creates cases: False  ·  Affects deployed scoring: False

## Known limitations
- Shadow comparison only — does NOT drive decisions, create cases, or affect /api/score-transaction.
- Synthetic AMLworld benchmark; candidate not deployed and not production-validated.
- Candidate features are point-in-time online windows; baseline single-tx score uses no history (its deployed behaviour).
- Bucketed/aggregate values only — no raw identifiers or raw feature values are exposed.

## Why not deployed

Synthetic-benchmark candidate; comparison-only. Needs out-of-time validation on real supervised data under SAMA governance, calibration, drift monitoring, and sign-off.

## Needed before deployment
- Out-of-time validation on real (non-synthetic) data under SAMA governance.
- Online/offline parity confirmed on the live serving path at scale (not just the replay harness).
- Calibration + drift monitoring + alerting.
- A documented rollback and human-in-the-loop governance plan.

> SHADOW ONLY — comparison/monitoring artefact. The deployed model, scoring endpoint, and explainability endpoints are unchanged.
