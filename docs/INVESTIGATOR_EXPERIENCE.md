# Investigator Experience — نسيج | Naseej

UI plan for the fraud-analyst workspace (post-MVP). The current demo shows
the network story; this page is where a bank's AML analysts actually work.
Backed by the Case Management Service ([`BACKEND_BLUEPRINT.md`](BACKEND_BLUEPRINT.md) §7).

**Status: first iteration implemented.** The INVESTIGATOR view (top nav)
ships the risk queue, case detail, "Why flagged?" panel, recommended
action, attributed decisions with append-only history, PII-guarded notes,
and audit-trail refs — backed by the live case API when the backend is up,
and by clearly-labelled mock data offline. See
[`CASE_MANAGEMENT.md`](CASE_MANAGEMENT.md) for the lifecycle and
enforcement details. The rest of this document remains the target design
for what is not yet built (graph explanation overlay, SHAP attribution,
structured FP feedback, regulator role).

---

## Personas

- **Analyst** — works the alert queue, dispositions alerts, writes case notes.
- **Senior analyst / MLRO** — handles escalations, approves blocks, owns SAR filing decisions (outside Naseej scope).
- **Auditor / regulator** — read-only access to decisions and trails.

## Layout

```
┌────────────────────────────────────────────────────────────────────┐
│ TopNav: Naseej · bank node id · analyst identity · queue stats     │
├──────────────┬─────────────────────────────────────────────────────┤
│              │  ALERT DETAIL                                       │
│  RISK QUEUE  │  ┌───────────────────────────┬───────────────────┐  │
│              │  │ Why flagged?              │ Graph explanation │  │
│  ▸ alert     │  │ typology · score ·        │ local subgraph    │  │
│  ▸ alert     │  │ matched NSJ_* hash ·      │ view (bank's own  │  │
│  ▸ alert     │  │ contributing features     │ data only)        │  │
│  (sorted by  │  ├───────────────────────────┴───────────────────┤  │
│  risk·age)   │  │ Recommended action · Analyst decision          │  │
│              │  ├────────────────────────────────────────────────┤  │
│              │  │ Case notes · Audit trail                       │  │
└──────────────┴──┴────────────────────────────────────────────────┴──┘
```

## Components

### 1. Risk queue
Prioritized list of open alerts: risk score, typology badge, age, source
(local model vs. network hash match), SLA indicator. Sort by risk × age;
filter by typology, source, and status. Bulk actions are deliberately
excluded — every disposition is individual and attributed.

### 2. Alert details
One alert = one local transaction (or transaction group) plus the trigger:
either a local model score above threshold or a match against a received
`NSJ_*` pattern hash. Shows bucketed pattern features, the matched threat
pattern object (which is inherently zero-PII), and the bank's **own** customer
context — which never leaves the bank.

### 3. Graph explanation
Interactive subgraph of the bank's local view: accounts as nodes, transfers
as edges, the flagged structure highlighted. Toggle to overlay the abstract
pattern shape (from `graph_signature`) on the local subgraph so the analyst
sees *why* the topology matched.

### 4. "Why flagged?" explanation
Plain-language panel, assembled from structured fields (never free-form
model output): typology description, the features that fired
(e.g. "5 inflows within 40 minutes — bucket: high burst"), model score vs.
threshold and operating mode, and the source node's `evidence_summary` when
the trigger was a network match. Post-MVP phase 7 adds SHAP-based feature
attribution for model-scored alerts.

### 5. Recommended action
The system recommends — never executes: `REVIEW` / `HOLD` / `BLOCK` with the
rationale and the policy basis (threshold + operating mode). Recommendations
above a severity line require senior-analyst co-sign.

### 6. Human decision & override
Decision buttons: **Confirm fraud** · **False positive** · **Escalate** ·
**Request more info**. Any decision that contradicts the recommendation
requires a mandatory reason — overrides are first-class data, not exceptions.
All decisions are attributed and timestamped.

### 7. Case notes
Chronological, append-only notes per alert with analyst attribution.
Notes are local to the bank and never broadcast. A PII linter warns when a
note's content would block future sharing of derived intelligence.

### 8. False-positive feedback
"False positive" dispositions capture a structured reason (legitimate
business pattern / known customer behavior / data quality / other) and flow
back as training labels. Per-typology FP rates appear on the queue header so
analysts see model quality drift before the monitoring service alarms.

### 9. Audit trail
Every alert renders its full event history: created, viewed, scored,
matched, recommended, decided, escalated, closed — actor, timestamp, and
before/after values. Read-only, exportable for regulator requests.

---

## Privacy boundaries in this UI

- Customer PII shown here is the bank's **own** data, inside the bank's own
  deployment — Naseej network objects remain zero-PII.
- Nothing an analyst types is broadcast; sharing is only ever the
  schema-validated pattern object.
- Regulator role sees decisions and trails, not customer identities.

## Build order

1. ~~Risk queue + alert details against the Case Management API~~ ✅
2. ~~Decision actions + audit trail (write path, attribution)~~ ✅
3. ~~"Why flagged?" panel from structured pattern features~~ ✅ (typology
   explanation + evidence summary; SHAP attribution still pending)
4. Graph explanation view (reuse demo `GraphView` as the starting point).
5. False-positive feedback loop into training labels (the
   `false_positive_flag` is captured; the training-label export is not).
