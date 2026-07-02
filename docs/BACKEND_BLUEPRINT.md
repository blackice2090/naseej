# Post-MVP Backend Blueprint — نسيج | Naseej

Target service decomposition for the post-MVP phase, and how today's
FastAPI scaffolding maps onto it.

**Honesty note:** today the backend is a single FastAPI process
(`backend/app/`) serving a demo. This blueprint is the growth path, not a
description of what exists. Nothing here should be read as production-ready.

---

## Guiding constraints

- **Data residency:** raw transaction data never leaves a bank's own
  infrastructure. Only schema-validated threat pattern objects
  ([`THREAT_PATTERN_CONTRACT.md`](THREAT_PATTERN_CONTRACT.md)) cross the boundary.
- **Defensive scope only:** the platform detects and prevents financial
  crime. No offensive capabilities, no customer-deanonymization tooling.
- **Human in the loop:** no service may auto-block a customer transaction
  without an analyst decision path (see [`INVESTIGATOR_EXPERIENCE.md`](INVESTIGATOR_EXPERIENCE.md)).
- **Everything audited:** every read or write of threat intelligence is an
  audit event.

---

## Topology

```
                      ┌──────────────────────── Naseej Core (shared) ───────────────────────┐
                      │                                                                      │
  Bank A premises     │   ┌──────────────┐   ┌────────────────────┐   ┌─────────────────┐   │
┌──────────────────┐  │   │ API Gateway  │   │ Threat Pattern     │   │ Audit Log       │   │
│ Bank Node Service├──┼──►│ mTLS · authz │──►│ Registry           │──►│ Service         │   │
│  ├ Privacy Layer │  │   │ rate limits  │   │ validate · store · │   │ append-only     │   │
│  ├ Graph Feature │  │   └──────────────┘   │ route · retain     │   └─────────────────┘   │
│  │   Engine      │  │                      └────────────────────┘                         │
│  ├ Risk Scoring  │  │   ┌──────────────────┐   ┌──────────────────┐                       │
│  │   Service     │  │   │ Admin/Regulator  │   │ Model Monitoring │                       │
│  └ Case Mgmt     │  │   │ Dashboard        │   │ Service          │                       │
└──────────────────┘  │   └──────────────────┘   └──────────────────┘                       │
  (replicated at      │                                                                      │
   each member bank)  └──────────────────────────────────────────────────────────────────────┘
```

Bank-side services run inside each member bank. Core services run in the
shared network operator environment (post-MVP assumption: SAMA-supervised
hosting).

---

## Services

### 1. API Gateway *(core)*
Single entry point for bank nodes. mTLS client certificates per node,
token-based service auth, rate limiting, schema-validation rejection at
the edge, request audit emission.
**Today: partial.** Per-node API keys (`X-API-Key` → node id, env
`NASEEJ_NODE_KEYS`, dev defaults for local simulation) protect scoring,
pattern analysis, the registry, and cases; each request resolves an
AuthContext (node type, role, permissions) from a server-side node profile
(`core/nodes.py`, env `NASEEJ_NODE_PROFILES`), with role selection bounded
by the node's allowed-roles envelope. Schema rejection and audit emission
run on every registry request. Still missing: mTLS, key rotation, rate
limiting, replay protection, per-analyst credentials (bank IAM).

### 2. Bank Node Service *(bank-side)*
The deployable unit a member bank runs. Hosts the privacy layer, graph
feature engine, and risk scoring locally so raw data stays on premises.
Publishes validated threat patterns; subscribes to network broadcasts and
matches them against local transactions.
**Today:** simulated by the browser demo (Bank A and Bank B are React panels).

### 3. Threat Pattern Registry *(core)*
Stores threat pattern objects, enforces `governance_tags` (sharing scope,
retention), routes broadcasts to subscribed nodes, serves hash lookups.
**Today: minimal.** File-backed registry (`backend/data/patterns.jsonl`)
behind `POST/GET /api/patterns`: node auth → publish permission → closed
JSON Schema → source-node match → zero-PII content guard → audited write;
duplicate `pattern_id` rejected. Reads enforce
`governance_tags.sharing_scope` (`local_only` / `bilateral` /
`network_all` / `regulator_only`) per caller, with audited 403 denials.
Still missing: broadcast routing, retention enforcement from
`governance_tags`, revocation.

### 4. Privacy Layer *(bank-side)*
Normalizes findings, buckets values, generates `NSJ_*` hashes, runs
`verify_zero_pii()`, blocks any non-conforming broadcast.
**Today: real.** `backend/app/services/privacy_service.py` +
`ml/src/privacy_hash.py`, proved by 136 tests in `ml/tests/test_privacy_hash.py`.

### 5. Graph Feature Engine *(bank-side)*
Builds account-level graph features (degree, velocity, fan-in/out scores)
from the bank's transaction stream; feeds the pattern library and the
scoring model.
**Today: batch-real + incremental prototype.** `ml/src/graph_features.py`
and `ml/scripts/build_graph_features.py` produce the training features;
`ml/src/pattern_library.py` detects 8 typologies. The serving side now has
a node-scoped in-memory **feature store**
(`backend/app/services/feature_store_service.py`,
[`FEATURE_STORE.md`](FEATURE_STORE.md)): pseudonymous events ingested via
`POST /api/features/ingest-transaction` feed rolling 1h/24h windows whose
features are declared in a catalogue (`feature_catalogue.py`). Bank A's
window state is invisible to Bank B by construction. Still missing:
persistent backing store, streaming ingestion, TTL/caching infra.

### 6. Risk Scoring Service *(bank-side)*
Serves the trained model for transaction scoring with calibrated
thresholds per operating mode (conservative / balanced / aggressive).
**Today: real but limited.** `backend/app/services/scoring_service.py`
runs live XGBoost inference; the legacy single-transaction mode lacks
velocity history, so scores are conservative (documented limitation).
`POST /api/features/score-with-context` layers a deterministic,
capped rule adjustment computed from the feature store on top of the
baseline score — explainable and honest (`model_retrained_on_context:
false`), but not a retrained model. Retraining on point-in-time window
features is the next ML step ([`FEATURE_STORE.md`](FEATURE_STORE.md) §8).

### 7. Case Management Service *(bank-side)*
Alert lifecycle: open → triage → decision (confirm / false positive /
escalate) → closure, with case notes and analyst attribution. Feeds
false-positive labels back to model training.
**Today: minimal.** File-backed case store with an enforced status machine
(fraud confirmation unreachable without review), append-only decision
history, PII-guarded notes/reasons, audit refs on every write, and the
investigator UI on top ([`CASE_MANAGEMENT.md`](CASE_MANAGEMENT.md)).
Cases are partitioned per node (owner + explicit visibility, regulator
view-all read-only) and decisions are role-gated from the AuthContext
(analyst / senior_analyst / MLRO), with every denial audited.
Still missing: FP-label export to training, assignment workflow, SLA
tracking, real per-analyst IAM integration.

### 8. Audit Log Service *(core + bank-side)*
Append-only, hash-chained event log: every broadcast, ingestion, match,
analyst decision, and admin action. Queryable by the regulator dashboard.
**Today: prototype.** Hash-chained JSONL (`audit_service.py`) records every
scoring call, pattern analysis, registry read/write, and rejection —
metadata only, PII-free by construction, with `verify_chain()` tamper
detection. Still missing: immutable sink (WORM storage), external chain
anchoring, query API.

### 9. Admin / Regulator Dashboard *(core)*
Network health, per-node broadcast/ingestion volumes, retention compliance,
audit search. Read-only regulator view — regulators see network statistics
and audit trails, never customer data (which never enters the core anyway).
**Today: none.**

### 10. Model Monitoring Service *(core, aggregated)*
Tracks score-distribution drift, alert-rate drift, precision proxies from
case outcomes, per-node model versions; raises governance alerts when a
node's model degrades.
**Today: static.** `GET /api/model/metrics` serves the offline evaluation
report from `ml/reports/`. The ML evaluation phase adds four read-only
companion reports under the same prefix (`/api/model/comparison`,
`/per-typology-recall`, `/threshold-analysis`, `/ablation-report`) — all
public, all serving offline `ml/reports/*.json` and degrading to a `source:
"fallback"` payload when a report has not been generated. See
[`MODEL_EVALUATION.md`](MODEL_EVALUATION.md).

---

## Current API surface (implemented)

| Endpoint | Auth | Maps to target service | Status |
|---|---|---|---|
| `GET /health` | public | Gateway health | real |
| `GET /api/auth/whoami` | node key | Gateway / identity | minimal (node, role, permissions for UI mirroring) |
| `GET /api/model/metrics` | public | Model Monitoring | real (offline report) |
| `GET /api/model/feature-importance` | public | Model Monitoring | real (offline report) |
| `GET /api/model/comparison` | public | Model Monitoring | real (offline report, fallback if absent) |
| `GET /api/model/per-typology-recall` | public | Model Monitoring | real (offline report, heuristic labels, fallback if absent) |
| `GET /api/model/threshold-analysis` | public | Model Monitoring | real (offline report, fallback if absent) |
| `GET /api/model/ablation-report` | public | Model Monitoring | real (offline report, fallback if absent) |
| `GET /api/model/feature-contract` | public | Feature Reconciliation | real (canonical offline/online contract, fallback if absent) |
| `GET /api/model/feature-parity` | public | Feature Reconciliation | real (replay-harness parity report, fallback if absent) |
| `GET /api/model/training-feature-manifest` | public | Feature Reconciliation | real (approved/excluded training features, fallback if absent) |
| `GET /api/cross-bank/results` | public | Model Monitoring | real (offline experiment) |
| `POST /api/score-transaction` | node key | Risk Scoring | real (live XGBoost) + audited |
| `POST /api/analyze-pattern` | node key | Privacy Layer + Graph Feature Engine | real (pattern library + hashing) + audited |
| `POST /api/patterns` | node key + publish perm | Threat Pattern Registry | minimal (schema + PII gates, file-backed) |
| `GET /api/patterns` | node key | Threat Pattern Registry | minimal (sharing-scope filtered list, typology filter) |
| `GET /api/patterns/{id}` | node key | Threat Pattern Registry | minimal (sharing-scope enforced, audited 403) |
| `POST /api/cases/from-pattern/{id}` | node key + create perm | Case Management | minimal (derives case from a *visible* registered pattern) |
| `GET /api/cases[/{id}]` | node key | Case Management | minimal (partitioned list/get, status filter) |
| `PATCH /api/cases/{id}/status` | node key, owner, role-gated | Case Management | minimal (enforced status machine) |
| `POST /api/cases/{id}/notes` | node key, owner | Case Management | minimal (PII-guarded) |
| `POST /api/cases/{id}/decision` | node key, owner, role-gated | Case Management | minimal (attributed, append-only history) |
| `POST /api/features/ingest-transaction` | node key (bank), source-node match | Graph Feature Engine | minimal (in-memory windows, PII-guarded, audited) |
| `GET /api/features/account/{id}` | node key, node-scoped | Graph Feature Engine | minimal (generic 403 for unseen/cross-node) |
| `POST /api/features/score-with-context` | node key | Risk Scoring | minimal (baseline model + capped rule layer, audited) |
| `GET /api/features/status` | node key | Graph Feature Engine | minimal (caller's own partition only) |
| `GET /api/features/catalogue` | node key | Graph Feature Engine | real (declared feature contract) |
| `POST /api/explain/transaction` | node key, source-node match | Explainability | minimal (SHAP/fallback attribution + context rules, PII-safe, audited) |
| `GET /api/explain/case/{id}` | node key, case visibility/RBAC | Explainability | minimal (typology + bucketed evidence, audited 403 if hidden) |
| `GET /api/explain/model` | public | Explainability / Model Monitoring | real (report-derived summary, graceful fallback) |

## Build order (post-MVP)

1. ~~**Persistence + Threat Pattern Registry**~~ — ✅ minimal version done
   (file-backed JSONL; sharing-scope enforcement ✅; next: Postgres,
   retention enforcement, broadcast routing, revocation).
2. ~~**API Gateway basics — API keys, schema rejection**~~ — ✅ done at the
   app layer, including node profiles, roles, and access partitioning
   (next: rate limiting, mTLS, key rotation, per-analyst credentials).
3. ~~**Audit Log Service**~~ — ✅ prototype done (hash-chained JSONL; next:
   immutable sink + query API).
4. ~~**Case Management Service** — minimal alert queue backing the
   investigator UI.~~ — ✅ minimal version done (status machine, decisions,
   notes, investigator view; next: FP-label export, assignment, SLAs).
5. ~~**Feature store for the Graph Feature Engine** — removes the
   single-transaction scoring limitation.~~ — ✅ minimal version done
   (node-scoped in-memory windows + contextual rule scoring,
   [`FEATURE_STORE.md`](FEATURE_STORE.md); next: persistent store,
   point-in-time training features, model retraining).
6. Two-process **Bank Node simulation** (two FastAPI instances exchanging
   pattern objects through the registry) — replaces the in-browser
   broadcast animation with a real network hop.
7. **Model Monitoring** (drift snapshots), then **Admin/Regulator Dashboard**.

Items 1–4 are deliberately boring technology: one relational database
(e.g. Postgres), one FastAPI app per concern, no message broker until two
real processes need one.
