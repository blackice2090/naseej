# Candidate Model — Shadow Only (approved-features-only retrain)

**Status: research prototype · synthetic data · SHADOW candidate · NOT deployed · not production-ready**

This phase trains and evaluates a candidate model on **only** the approved,
parity-clean, servable, non-memorising feature set from the training feature
manifest. The candidate is documented for review and **never deployed**: the
live model, scoring endpoint, demo, explainability endpoints, case management,
and offline fallback are all unchanged.

Generate / regenerate:

```bash
python -m ml.src.train_candidate_model --train-sample 800000 --seed 42
```

Artifacts (all `candidate_*`; the deployed `baseline_model.joblib` and
`model_metrics.json` are never written):

| Artifact | Path |
|---|---|
| Candidate bundle | `ml/models/candidate_model.joblib` |
| Test metrics | `ml/reports/candidate_model_metrics.{json,md}` |
| Model comparison | `ml/reports/candidate_model_comparison.{json,md}` |
| Threshold policy | `ml/reports/candidate_thresholds.{json,md}` |
| Explainability check | `ml/reports/candidate_explainability_check.{json,md}` |

Served read-only (public, no node auth, no sensitive data, graceful fallback):
`GET /api/model/candidate/{metrics,comparison,thresholds,explainability-check}`.

---

## 0. Live shadow scoring (`POST /api/model/candidate/score-shadow`)

The candidate can now be scored **side-by-side with the deployed baseline**, for
comparison and monitoring only. This is the one candidate endpoint that takes a
payload and so requires node auth + the PII guard — but it never drives a
decision, creates a case, blocks/approves a transaction, or touches
`/api/score-transaction`.

**How it differs from deployed scoring:** `/api/score-transaction` runs the
deployed XGBoost baseline and is the system of record. `score-shadow` runs the
shadow candidate on its 15 approved features built from the **online feature
path** (payload + node-local windows) and returns its score next to the
baseline's — purely informational (`shadow_only: true`).

**Online feature serving:** intrinsic features (`amount`, `is_cross_bank`,
time-of-day, currency/payment codes) come from the payload; the 8 windowed
features come from the node's feature store — source-side
(`source_outflow_*`) read from the `from_account`'s window, target-side
(`target_inflow_*`) from the `to_account`'s window, point-in-time as of the
node's latest observed event. Identity/bank encodings, all-time cumulatives,
account-pair, and serve-only features are **hard-blocked** (assertion +
allow-list); none can enter the vector.

**Missing-feature behaviour:** if the node has no local window history, or the
timestamp is unparseable, the response is
`candidate_available: false, feature_vector_status: "missing_feature"` and the
transaction is **not scored** — the candidate never guesses. A missing candidate
artifact returns `feature_vector_status: "candidate_unavailable"`.

**Audit:** every request writes a metadata-only audit record
(`action: candidate_shadow_score`, `decision: scored | unavailable | rejected`,
`risk_tier`, sanitized `reason`) — never the transaction or feature values.

**Response fields:** `candidate_available`, `shadow_only`, `candidate_model_name`,
`candidate_score`, `candidate_risk_tier`, `candidate_threshold_mode`,
`candidate_recommended_action` (clearly labelled `(shadow)`), `baseline_score`,
`score_delta`, `agreement_with_baseline`, `feature_vector_status`,
`used_features` (15 canonical), `excluded_features_confirmed`, `limitations`,
`pii_safe: true`.

Readiness is summarised in `ml/reports/candidate_shadow_readiness.{json,md}`
(`python -m ml.src.candidate_shadow_readiness`).

**Shadow monitoring:** every shadow score also writes a bucketed, PII-safe
observation, aggregated node-scoped at
`GET /api/model/candidate/shadow-monitoring` with a prototype drift signal, and
a public calibration-readiness statement at
`GET /api/model/candidate/calibration-readiness`. Full detail in
[`SHADOW_MONITORING.md`](SHADOW_MONITORING.md). Monitoring observes only — it
never drives a decision, creates a case, or calibrates the candidate.

**Analyst feedback loop:** closed-case outcomes become bucketed, PII-safe
calibration labels (`POST /api/feedback/from-case/{id}`), aggregated at
`GET /api/feedback/calibration-dataset` with `insufficient_labels` until a
minimum-label threshold is met (proxies never faked). Full detail in
[`ANALYST_FEEDBACK_LOOP.md`](ANALYST_FEEDBACK_LOOP.md). This builds the dataset
*for* a future calibration — it does not calibrate or deploy the candidate.

> **Candidate explanation (deferred next step):** a live per-feature SHAP
> explanation on the shadow endpoint was intentionally **not** added — the
> existing `/api/explain/*` endpoints stay unchanged, and the candidate-only
> explainability evidence already lives in
> `candidate_explainability_check.json`. Wiring a live candidate explanation is
> a documented future step, not done here, to keep risk low.

---

## 1. Why this candidate exists

The reconciliation phases produced a contract that proves which features are
safe to train on: parity-clean across offline/online, servable point-in-time,
and free of identity-memorisation risk. This phase is the first model trained
strictly within that contract — a *clean-room* retrain that answers: **how much
detection skill survives when we drop the account/bank identity encodings and
every non-servable feature?** It is a shadow evaluation, not a deployment.

---

## 2. Approved feature set (15)

Read from `ml/reports/training_feature_manifest.json` at runtime; the candidate
matrix is built from these offline columns only:

`amount`, `is_cross_bank`, `hour_of_day`, `day_of_week`, `is_weekend`,
`currency_code`, `payment_type_code`, `source_outflow_count_1h/24h`,
`target_inflow_count_1h/24h`, `source_outflow_amount_1h/24h`,
`target_inflow_amount_1h/24h`.

All point-in-time (strictly-before windows from `build_graph_features.py`); no
feature uses a future transaction.

## 3. Excluded features (confirmed not used)

A hard block (`_assert_no_forbidden`) fails the run if any of these enter the
matrix:

- **Identity / memorisation:** `source_account_code`, `target_account_code`,
  `source_bank_code`, `target_bank_code`. (`is_cross_bank` is the approved
  structural replacement for bank identity.)
- **Not servable:** all `*_all_time` cumulatives and `account_pair_*` (online
  store prunes >25h).
- **Train-only scores:** the offline 24h `fan_in_count_24h` / `fan_out_count_24h`
  (no online twin), `sweep_ratio_all_time`, `rapid_movement_flag`.
- **Serve-only online features:** the normalised intensities, cycle/scatter
  scores, velocity z-score, newness buckets, etc. (no offline twin).

**No identity memorisation:** the candidate cannot memorise synthetic account or
bank ids because those encodings are excluded by construction.

---

## 4. Results (see `candidate_model_metrics.json` for exact figures)

<!-- CANDIDATE_RESULTS_START -->
Latest run (`seed=42`, temporal 70/15/15, 15 approved features):

| Model | val PR-AUC | test PR-AUC |
|---|---|---|
| **xgboost (selected)** | **0.1607** | **0.4247** |
| lightgbm | 0.1354 | 0.3438 |
| random_forest | 0.0934 | 0.3035 |
| logistic_regression | 0.0081 | 0.0193 |

Selected candidate **xgboost** — held-out test: PR-AUC **0.4247**, ROC-AUC 0.9765,
precision 0.440, recall 0.451, F1 0.4454, FPR 0.0012, ~210 alerts / 100k.
LightGBM was evaluated (4.6.0); selection is by validation PR-AUC.
<!-- CANDIDATE_RESULTS_END -->

### Candidate vs deployed baseline (protocol-aware)

- **Comparable (same temporal split):** `model_comparison.json` and
  `ablation_report.json`. The candidate's test PR-AUC **0.4247** sits **below**
  the ablation's `graph_context` (0.5548) and `full_with_account_ids` (0.5740).
  The gap to `full_with_account_ids` (≈0.15) is mostly the **serve-only
  graph/context features** the candidate excludes (cycle/scatter scores,
  velocity z-score, sweep flag — none has an offline twin), plus the ~0.019
  account-id memorisation lift it deliberately forgoes. This is the honest cost
  of a strictly parity-clean, servable, non-memorising feature set.
- **NOT comparable:** the deployed `model_metrics.json` (PR-AUC 0.2275) used a
  **stratified-random** split, not a temporal one. The comparison report shows
  it for reference only and flags it as not directly comparable.

---

## 5. Threshold policy

For the selected candidate, three operating points are chosen on validation
(maximising F-beta) and frozen before the held-out test:

| Mode | Use case |
|---|---|
| `high_precision` | Compliance escalation — few, high-confidence alerts |
| `balanced` | Analyst queue — day-to-day triage balance |
| `high_recall` | Monitoring only — broad watchlist, too noisy to escalate |

Exact thresholds + precision/recall/FPR/alerts-per-100k are in
`candidate_thresholds.json`. These are illustrative operating points on a
synthetic benchmark, not production cut-offs.

---

## 6. SHAP / fallback explainability status

`candidate_explainability_check.json` runs attribution on one synthetic test
row and verifies every approved feature resolves a `human_label` and
`value_bucket` **through the feature contract**:

- If the selected candidate is tree-based (XGBoost / LightGBM / RandomForest)
  and SHAP is installed → `method: "shap"` (TreeExplainer).
- Otherwise → deterministic feature/rule fallback.

Either way, factors expose **bucket labels only, never raw values**
(`pii_safe: true`). The deployed explanation endpoints (`/api/explain/*`) are
**unchanged** — this is a candidate-only check.

---

## 7. Deployment recommendation

**Not recommended.** This is a shadow evaluation. The candidate would need, at
minimum: out-of-time validation on real (non-synthetic) supervised data under
SAMA governance; calibration and drift monitoring; a serving path that computes
the approved features online (the windowed count/amount features are servable,
but a full serving integration + A/B shadow-scoring harness is not built);
and sign-off. `deployment_recommended: false` is set in every report.

---

## 8. Why GNN is still later

Unchanged from the reconciliation phase: the trainable+servable set is the 15
tabular features only. The serve-only graph/context features have no offline
twin and the all-time cumulatives have no servable twin, so there is no rich,
parity-clean graph feature set to build a leakage-audited temporal graph from
yet. A GNN comparison would not be trustworthy until that exists. This candidate
does not change that — it confirms the tabular ceiling without identity leakage.

---

## 9. Remaining risks

- Synthetic AMLworld only — nothing transfers to real data without out-of-time
  validation.
- The candidate is evaluated offline; online serving parity of the approved
  features is proven by the parity harness but a live shadow-scoring deployment
  is not built.
- Dropping identity features lowers headline PR-AUC vs the identity-using
  ablation — expected and acceptable (that lift does not generalise), but it
  means the candidate is a *more honest* ceiling, not a better leaderboard number.
- No production readiness is claimed; the deployed model is untouched.
