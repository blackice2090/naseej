# Shadow Monitoring + Calibration + Drift (prototype)

**Status: research prototype · synthetic data · aggregate/bucketed only · NO deployment decision**

This phase turns live shadow scores ([CANDIDATE_MODEL.md](CANDIDATE_MODEL.md))
into **safe aggregate monitoring evidence** — baseline-vs-candidate agreement,
score-distribution buckets, alert-rate impact, threshold behaviour, prototype
drift signals, and calibration readiness — **without storing raw transactions,
raw identifiers, or raw feature values**.

It changes nothing about the deployed model, `/api/score-transaction`,
`/api/explain/*`, case management, or offline fallback. Shadow monitoring never
creates a case and never drives a decision.

---

## 1. What is stored (and what is not)

The observation store (`backend/app/services/shadow_monitoring_service.py`,
JSONL at `NASEEJ_SHADOW_OBSERVATIONS_PATH`) writes **one bucketed observation
per shadow-score request**:

| Field | Example |
|---|---|
| `timestamp` | `2026-06-13T16:58:18Z` (second precision) |
| `node_id` | `NODE_A7C2F9E1` (pseudonymous node label) |
| `candidate_model_name` | `xgboost` |
| `baseline_score_bucket` / `candidate_score_bucket` | `lt_0.01`, `0.05_0.10`, `0.50_1.00`, … |
| `score_delta_bucket` | `approx_equal`, `candidate_higher`, `candidate_much_lower`, … |
| `baseline_risk_tier` / `candidate_risk_tier` | `minimal` / `medium` / `high` |
| `agreement_with_baseline` | `agree` / `disagree` / `baseline_unavailable` |
| `threshold_mode` | `balanced` |
| `candidate_action` / `baseline_action` | `no_alert (shadow)` / `benign` |
| `feature_vector_status` | `complete` / `missing_feature` / `candidate_unavailable` |
| `shadow_only`, `pii_safe` | `true`, `true` |

**Never stored:** raw transaction payloads; account/bank ids; names, IBANs,
phones, emails, national ids; or **exact score/feature values**. Scores are
coarse buckets. A PII guard (`pii_guard.find_pii`) double-checks every record
before it is written and refuses to write anything it flags — defense in depth
over the controlled, categorical-only schema.

### Why bucketed?

Storing exact scores or feature values would let an observer reconstruct
transaction-level detail (e.g. amount, velocity) and re-identify behaviour. The
whole product posture is zero-PII; monitoring inherits it. Coarse buckets keep
the monitoring statistically useful (distribution shifts, alert-rate deltas)
while carrying no re-identifiable signal.

---

## 2. How it integrates with `score-shadow`

After `POST /api/model/candidate/score-shadow` produces a result, the route
records one observation (best-effort; a write failure never breaks scoring):

- **scored** → a `feature_vector_status: complete` observation with score
  buckets, tiers, agreement, and actions.
- **unavailable / missing_feature** → a safe observation with `none` buckets
  and the status — so the monitoring also tracks how often the candidate
  *couldn't* be scored online.

Audit logging is unchanged (metadata-only, separate from observations).

---

## 3. Aggregation (node-scoped, three windows)

`GET /api/model/candidate/shadow-monitoring` (node auth) returns aggregates for
**last 1h / last 24h / all** over the **caller's own** observations:

`total_shadow_requests`, `scored_count`, `unavailable_count`,
`missing_feature_count`, `agreement_rate`, `disagreement_rate`,
`candidate_higher_risk_rate`, `candidate_lower_risk_rate`,
`candidate_alert_rate`, `baseline_alert_rate`, `alert_delta`,
`missing_feature_rate`, `score_delta_distribution_buckets`,
`risk_tier_transition_matrix`, `threshold_mode_distribution`,
`feature_vector_status_distribution`.

**Node scoping:** a bank node sees only its own aggregates. A cross-node view
(`?node_id=`) requires the regulator/admin `cases:view_all` permission;
otherwise it is an audited 403. No raw observations are exposed — aggregate
counts/rates and bucket distributions only.

---

## 4. Drift (prototype signal)

`compute_drift(recent, baseline)` compares a recent aggregate (last 24h) to the
all-history baseline and returns `signal: normal | watch | unavailable` with
human-readable `reasons`. It flips to **watch** on:

- a missing-feature-rate spike (absolute ≥ 0.50, or +0.20 vs baseline),
- a disagreement-rate spike (≥ 0.50, or +0.20 vs baseline),
- an alert-rate shift (|recent − baseline| ≥ 0.20).

It returns **unavailable** below `8` observations in the window.

> This is a **prototype drift signal** on bucketed synthetic observations. It is
> NOT statistical production monitoring and **requires real-data validation**.

---

## 5. Calibration readiness

`GET /api/model/candidate/calibration-readiness` (public) serves a static
statement (`ml/reports/candidate_calibration_readiness.{json,md}`,
`python -m ml.src.candidate_calibration_readiness`):

- the candidate is **NOT calibrated for production**,
- live shadow mode has **no real labels**, so probabilities cannot be calibrated,
- **no deployment is recommended**,
- what is needed: labeled outcomes, out-of-time validation, threshold tuning on
  real labels, an analyst feedback loop, real-distribution drift monitoring, and
  a SAMA-governed pilot with a rollback + human-in-the-loop plan.

---

## 6. How monitoring differs from deployment

Monitoring **observes**; it does not **act**. The deployed baseline
(`/api/score-transaction`) remains the only scorer that influences anything, and
even it only recommends — humans decide (see [CASE_MANAGEMENT.md](CASE_MANAGEMENT.md)).
Shadow monitoring produces evidence for a *future* deployment decision; it makes
no such decision and the candidate stays undeployed.

---

## 7. Remaining risks before deployment

- Synthetic AMLworld only; monitoring reflects offline-distribution shadow
  scores, not real traffic.
- No real labels → no calibration, no validated thresholds.
- The drift signal is coarse and prototype-grade; it can miss or over-flag.
- Online/offline feature parity is proven by the replay harness but not yet at
  live scale (see [FEATURE_CONTRACT.md](FEATURE_CONTRACT.md)).
- A live per-feature candidate explanation on the shadow path remains a
  documented next step ([EXPLAINABILITY.md](EXPLAINABILITY.md)).

GNN and federated learning have not started; deployment is not recommended.

---

## 8. Analyst feedback loop (labels for calibration)

Monitoring observes scores; the **analyst feedback loop**
([ANALYST_FEEDBACK_LOOP.md](ANALYST_FEEDBACK_LOOP.md)) adds the missing piece —
**labels**. When a case closes, its outcome becomes a bucketed, PII-safe
calibration label linked (when possible) to the shadow observation that scored
its transaction. `GET /api/feedback/calibration-dataset` aggregates those
labels; below a minimum threshold it returns `insufficient_labels` (proxies are
never faked). The Shadow Monitoring row surfaces the labeled count + calibration
status, labelled **CALIBRATION DATASET — NOT PRODUCTION CALIBRATION**.
