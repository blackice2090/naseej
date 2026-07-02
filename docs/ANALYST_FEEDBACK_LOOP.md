# Analyst Feedback Loop + Calibration Dataset Builder

**Status: research prototype · synthetic data · aggregate/bucketed only · NOT production calibration · candidate NOT deployed**

This phase connects **human investigation outcomes** to the shadow model's
(bucketed) observations, so Naseej can build a safe, labeled calibration dataset
over time — **without storing PII, raw transactions, raw identifiers, or raw
feature values**. It changes nothing about the deployed model,
`/api/score-transaction`, `/api/explain/*`, shadow scoring, or case management.
It never creates a case and never calibrates or deploys the candidate.

---

## 1. How analyst decisions become feedback labels

A case carries a human-in-the-loop verdict (see [CASE_MANAGEMENT.md](CASE_MANAGEMENT.md)).
When a case is **closed**, `POST /api/feedback/from-case/{case_id}` turns that
outcome into one calibration label:

| Closed status | feedback_label |
|---|---|
| `closed_confirmed` | `confirmed_fraud` |
| `closed_false_positive` | `false_positive` |
| `closed_no_action` | `no_action` |
| open / under_review / escalated | `unresolved` (rejected — see below) |

Only **closed** cases yield a final label. A non-closed case returns **409** —
an open case has no confirmed outcome to learn from, which is the
human-in-the-loop guarantee, encoded. In the demo, feedback is **auto-captured
on closure** (fire-and-forget) when the backend is live.

Linking: if the transaction was shadow-scored with a `pattern_id` matching the
case's pattern, the feedback record links to that shadow observation
(`linked_shadow_observation_id`) and copies its **bucketed** candidate/baseline
risk tiers and agreement. Otherwise those fields are `null` — the label is still
recorded, just unlinked.

---

## 2. What is stored (feedback record)

Append-only JSONL at `NASEEJ_FEEDBACK_LABELS_PATH`:

| Field | Example |
|---|---|
| `feedback_id`, `case_id`, `linked_pattern_id` | system UUIDs (refs, not customer ids) |
| `node_id` | `NODE_A7C2F9E1` (pseudonymous node label) |
| `final_case_status` | `closed_confirmed` |
| `analyst_decision` | `confirm_fraud` |
| `false_positive_flag` | `false` |
| `linked_shadow_observation_id` | UUID or `null` |
| `candidate_risk_tier_bucket` / `baseline_risk_tier_bucket` | `high` / `medium` (from the linked observation) |
| `agreement_with_baseline` | `agree` / `disagree` / `null` |
| `feedback_label` | `confirmed_fraud` / `false_positive` / `no_action` |
| `created_at`, `pii_safe` | `…Z`, `true` |

### What is NOT stored

No raw transaction payloads, account/bank ids, amounts, names, IBANs, phones,
emails, national ids, or **raw feature/score values**. Risk tiers are coarse
buckets carried over from the shadow observation. A PII guard
(`pii_guard.find_pii`, with format-pinned UUID/ref fields exempt from the
digit-run **content** rule but never from key-name rules) double-checks every
record before it is written and refuses to write anything flagged.

`case_id` / `pattern_id` are internal system references the case API already
exposes — they are not customer identifiers and are explicitly part of the
feedback schema (the link is the point).

---

## 3. Duplicate behaviour

Feedback is **append-only**: re-submitting a case appends a new snapshot.
Aggregation takes the **latest snapshot per `case_id`**, so a case is never
double-counted. This is the "update by appending a new snapshot" option — safe
and audit-friendly.

---

## 4. Calibration dataset (why labels are needed)

A model's scores are only trustworthy once compared against **real outcomes**.
The candidate runs in shadow and produces scores, but without labeled outcomes
there is nothing to calibrate against. The feedback loop accumulates those
labels. `GET /api/feedback/calibration-dataset` (node-scoped) returns:

`total_feedback_records`, `labeled_count`, `unresolved_count`,
`confirmed_fraud_count`, `false_positive_count`, `no_action_count`,
`candidate_risk_tier_vs_outcome`, `baseline_risk_tier_vs_outcome`,
`minimum_label_threshold`, `minimum_label_threshold_met`.

- **Below threshold** (default 30, env `NASEEJ_CALIBRATION_MIN_LABELS`):
  `status: insufficient_labels`, `message: "insufficient labels for calibration …"`,
  and **no proxies are computed** — calibration is never faked.
- **At/above threshold**: `status: prototype_ready` with **prototype** proxies —
  `candidate_precision_proxy`, `baseline_precision_proxy`,
  `false_positive_rate_proxy`, `disagreement_outcome_breakdown`,
  `candidate_vs_baseline_outcome_agreement`. These are coarse proxies from
  bucketed tiers + analyst outcomes, **clearly labelled NOT production-grade
  ECE/Brier** (no real probabilities/labels exist).

`GET /api/model/candidate/calibration-status` (public) returns only the overall
status enum + threshold — no per-node counts — and always states
`calibrated_for_production: false`, `deployment_recommended: false`.

---

## 5. Endpoints, auth, and node-scoping

| Endpoint | Auth | Scope |
|---|---|---|
| `POST /api/feedback/from-case/{case_id}` | node key | case must be **visible** to the caller (404 unknown, audited 403 if hidden); only closed cases (409 otherwise) |
| `GET /api/feedback` | node key | aggregate counts for the **caller's own** node |
| `GET /api/feedback/calibration-dataset` | node key | caller's own node; `?node_id=` cross-node needs `cases:view_all` (regulator) |
| `GET /api/model/candidate/calibration-status` | public | enum + threshold only, no sensitive data |

A bank sees only its own feedback. Regulator/admin may view aggregate-all only
via the existing `cases:view_all` permission. **Every** write and denied access
is audited (metadata only — never the case body or any payload).

---

## 6. Why this supports governance & human-in-the-loop AML

The loop closes the chain: a detection becomes a reviewable case, a human
analyst decides, and that decision becomes a labeled outcome that — over time,
and only with enough labels — could support calibrating a *candidate* before any
deployment is even considered. Every step is attributed, audited, node-scoped,
and zero-PII. Nothing is automated end-to-end; the human verdict is the label.

---

## 7. Why the candidate is still not deployed

Labels are sparse synthetic-benchmark outcomes; there is no out-of-time
validation, no real-distribution drift monitoring, no validated thresholds, and
no SAMA-governed pilot. The dataset builder is a *prerequisite* for calibration,
not calibration itself. `deployment_recommended: false` everywhere.

## 8. Remaining risks

- Synthetic AMLworld only; labels reflect demo/case outcomes, not real fraud.
- Proxies are prototype-grade and can mislead on small samples.
- Observation↔case linking is best-effort (requires `pattern_id` at scoring);
  unlinked labels carry no risk-tier comparison.
- Calibration, GNN, and federated learning have not started; deployment is not
  recommended and production readiness is not claimed.
