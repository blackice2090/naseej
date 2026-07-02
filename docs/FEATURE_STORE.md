# Feature Store & Real-Time Velocity Features

**Status: research prototype · synthetic/pseudonymous data only · not production-ready**

This document describes the node-local feature store added after the
access-partitioning phase. It exists to fix one concrete, documented
limitation: single-transaction scoring had no account history, so every
history-dependent model feature was filled with `0.0` and the model scored
near the base rate.

---

## 1. Why this exists — the single-transaction limitation

`POST /api/score-transaction` builds a feature vector from one transaction.
The training pipeline (`ml/src/graph_features.py`) computed velocity windows,
cumulative counts and graph degrees over the *full dataset*; at serving time
none of that history existed, so `backend/app/services/scoring_service.py`
set all of it to zero — explicitly documented as a conservative bias.

The feature store closes that gap for locally ingested history:

| Before | After |
|---|---|
| Every velocity feature = 0 | Rolling 1h/24h windows computed from ingested events |
| No counterparty memory | New-beneficiary flag, relationship age buckets |
| No graph context | Fan-in/fan-out/scatter-gather/cycle scores per window |
| Score = transaction attributes only | Score = baseline model + transparent contextual rule layer |

What it does **not** do: it does not retrain the model. The XGBoost bundle
still consumes the same vector it was trained on. The new features feed a
**deterministic, explainable rule adjustment** layered on top
(`/api/features/score-with-context`), and every response says so
(`model_retrained_on_context: false`).

---

## 2. Components

| Piece | Where |
|---|---|
| Feature catalogue (machine-readable) | `backend/app/services/feature_catalogue.py`, served at `GET /api/features/catalogue` |
| Store engine (windows, isolation, snapshot) | `backend/app/services/feature_store_service.py` |
| Transaction PII guard | `pii_guard.find_transaction_pii` in `backend/app/services/pii_guard.py` |
| Endpoints | `backend/app/api/routes_features.py` |
| Pattern-analysis enrichment | `feature_store_service.enrich_pattern_analysis`, called by `/api/analyze-pattern` |
| Tests (39) | `backend/tests/test_feature_store.py` |

---

## 3. Feature catalogue

Twenty-one features, each declared with `feature_name`, `description`,
`entity_type`, `refresh_interval`, `owner`, `lineage`, `privacy_level`,
`allowed_usage`, `leakage_risk`, `bias_risk`, and `retention_days`. The
catalogue in code is authoritative; this table summarises it.

| Feature | Entity | What it measures |
|---|---|---|
| `source_out_degree_1h` / `_24h` | account | Outbound transfer count in window |
| `target_in_degree_1h` / `_24h` | account | Inbound transfer count in window |
| `amount_sent_1h` / `_24h` | account | Outbound amount sum in window |
| `amount_received_1h` / `_24h` | account | Inbound amount sum in window |
| `unique_targets_1h` | account | Distinct beneficiaries in 1h |
| `unique_sources_1h` | account | Distinct payers in 1h |
| `cross_bank_transfer_count_24h` | account | Transfers with differing banks in 24h |
| `new_beneficiary_flag` | counterparty | First-ever (locally observed) source→beneficiary transfer |
| `beneficiary_age_bucket` | counterparty | Relationship age: `unseen` / `new_0_1h` / `recent_1_24h` / `established_gt_24h` |
| `first_seen_delta_bucket` | account | Same buckets for the account itself |
| `sweep_after_fan_in_flag` | graph_window | ≥3 inbound in 1h, then outflow ≥ 60% of inflow |
| `fan_in_normalized_1h` / `fan_out_normalized_1h` | graph_window | `min(1, degree_1h / 5)` (renamed from `fan_in_score`/`fan_out_score` to end the offline/online name collision — see [FEATURE_CONTRACT.md](FEATURE_CONTRACT.md)) |
| `scatter_gather_score` | graph_window | Geometric mean of fan-in and fan-out normalised intensities |
| `simple_cycle_score` | graph_window | 2-/3-cycle through the account in the 24h window |
| `account_velocity_zscore` | account | Current 1h outbound count vs the account's own 24h hourly baseline |
| `rolling_amount_ratio` | transaction | Transaction amount vs the account's average outbound amount (24h) |

Shared catalogue values in this prototype:

- **refresh_interval** — `event-driven`: features are recomputed from the
  window on every ingest/lookup; there is no batch pipeline or TTL cache.
- **owner** — `naseej-ml-research (prototype placeholder)`; a real
  deployment would assign per-feature ownership.
- **lineage** — every feature derives from the rolling window of
  pseudonymous transactions ingested via `POST /api/features/ingest-transaction`,
  mirroring the train-time definitions in `ml/src/graph_features.py`. There
  are no external joins, reference tables, or third-party signals.
- **retention_days** — raw window events ~1 day (pruned at a 25h horizon);
  first-seen registries 30 days. Both are in-memory pruning, not a managed
  storage policy.

---

## 4. Privacy boundaries

```
            ┌── Bank A node boundary ─────────────────────────────┐
            │  ingest (pseudonymous events)                       │
            │     └─► node-local windows ─► features ─► scoring   │
            │                                            │        │
            └────────────────────────────────────────────┼────────┘
                                                         │ ONLY zero-PII
                                                         ▼ pattern hashes
                                                  Naseej network
```

- **What is stored:** pseudonymous handles (`0xMULE_01`-style synthetic
  identifiers), bank ids, amounts, timestamps — nothing else. The ingest
  schema is closed (`extra="forbid"`), so a name/IBAN/phone *field* cannot
  exist, and `find_transaction_pii` rejects PII *shapes inside values*
  (IBAN patterns, 8+ digit runs, phone/email patterns, Arabic free text,
  space-containing name-like strings). Fail-closed: a guard error is a
  rejection.
- **What is never stored:** customer names, IBANs, national IDs, phone
  numbers, addresses, raw customer records, or any field outside the
  ten-field transaction schema.
- **What never crosses the node boundary:** feature values. They feed the
  node's own scoring and analyst explanations only. The cross-bank exchange
  remains exactly what it was — `NSJ_*` pattern hashes.
- **Audit:** every ingest, lookup, scoring call and denial appends a
  metadata-only record to the hash-chained audit log (action, decision,
  static reason). Raw payloads, handles and amounts never appear in audit
  records — covered by tests.

### Node isolation

The store is partitioned by the **authenticated** node id (`AuthContext`),
never by anything in a request body or path. Bank B asking for a Bank A
account gets the same generic `403` as asking for an account that does not
exist — a cross-node probe learns nothing from the response. The
`/api/features/status` endpoint reports only the caller's own partition.
`/api/analyze-pattern` enrichment likewise only fires when the *calling*
node's own store has seen the batch's central account.

---

## 5. Leakage risks (what could go wrong, and current mitigations)

| Risk | Mitigation in this prototype |
|---|---|
| Feature values reveal account turnover/behaviour cross-node | Values never leave the computing node; no cross-node feature API exists |
| Membership probing ("does Bank A know account X?") | Unseen and not-mine return the identical generic 403, audited |
| Handles in logs | Audit records are enumerated metadata; tests assert no handles/amounts appear |
| PII smuggled into handle fields | Shape + content rules; closed schema; fail-closed guard |
| Concatenated real name as a "handle" (`MohammedAli`) | **Not detectable** — the guard blocks PII shapes, it cannot prove a handle is synthetic. Documented limitation; real deployments must tokenise upstream inside the bank |
| Train-time vs serve-time leakage (label leakage) | The contextual layer is rules, not training; no labels enter the store. Before any retraining, window features must be recomputed point-in-time to avoid lookahead bias |

## 6. Bias risks

These features encode *behavioural unusualness*, which correlates with
legitimate life events. The catalogue records a bias note per feature; the
recurring themes:

- **Velocity features** penalise legitimately bursty accounts — payroll,
  merchants, charity drives. They must remain alert signals feeding human
  triage, never automatic blocks (consistent with the case-management
  governance ladder).
- **Newness features** (`new_beneficiary_flag`, `first_seen_delta_bucket`)
  penalise new customers and the financially excluded with thin history.
  Bucket thresholds are uncalibrated guesses on synthetic data.
- **Cross-bank counts** penalise customers who legitimately use several
  banks.
- The rule weights in `/score-with-context` are hand-set, visible in
  `routes_features.py`, and capped (+0.45 total) so the contextual layer
  cannot dominate the baseline model silently.

## 7. What is real vs simulated

| Real (works as described) | Simulated / prototype-only |
|---|---|
| Rolling 1h/24h window computation from ingested events | The events themselves are synthetic demo transactions |
| Node isolation on the authenticated identity | Only 3 dev nodes exist locally |
| PII guard, audit records, generic denials | — |
| Baseline XGBoost inference (`base_model_score`) | — |
| Contextual rule layer with explanations | Rule weights are hand-set, not learned or calibrated |
| In-memory store + optional JSONL snapshot | No database, no TTL infra, no horizontal scale, single process |
| `sweep_after_fan_in` confirmation in `/api/analyze-pattern` | Thresholds (3 inbound, 60% outflow) chosen for the demo pattern |

## 8. What remains before retraining the model on these features

1. **Point-in-time feature generation over the training set** — recompute
   the catalogue features for every historical transaction *as of* its
   timestamp (no lookahead), producing a new training matrix.
2. **Leakage audit** of each feature against the label (laundering flag).
3. **Re-run the temporal split + threshold selection** and publish new
   `ml/reports/*` artifacts; the honest-copy rule then requires updating
   `naseej-ai/src/data/mockData.js` fallbacks to match.
4. **Calibration + ablation** — show the window features actually add
   PR-AUC over the baseline before replacing the rule layer.
5. **Bias evaluation** on the newness/velocity features (section 6).
6. Until all of that lands, `/score-with-context` keeps reporting
   `model_retrained_on_context: false`.

### Progress (2026-06): offline ablation done; reconciliation contract now exists

The offline evaluation suite ([`MODEL_EVALUATION.md`](MODEL_EVALUATION.md))
satisfies item 4 **for the offline point-in-time features**: a leakage-controlled
ablation shows context features lift PR-AUC from 0.18 (graph only) to 0.55.

The offline/online code-path gap is now **measured**, not just noted: the
feature contract ([`FEATURE_CONTRACT.md`](FEATURE_CONTRACT.md),
`ml/src/feature_contract.py`) reconciles every feature across paths, and the
parity checker (`ml/src/feature_parity_check.py`) replays **four** synthetic
scenarios through both and confirms the eight windowed count/amount features
match point-in-time. The fix sprint (contract v2) **resolved the name
collisions**: this store now emits `fan_in_normalized_1h`/`fan_out_normalized_1h`
(distinct from the offline 24h integer counts). The remaining blockers are
documented, not silent: the all-time cumulative features this store cannot
reproduce under 25h pruning (kept excluded — no 30d back-fill), and the
account/bank-id encodings (memorisation, permanently excluded). The **training
manifest** approves only 15 parity-clean, servable, non-memorising features.

So this is still **not** a green light to retrain: `/score-with-context`
continues to report `model_retrained_on_context: false` until the approved set is
parity-clean end to end and the train-only/serve-only gaps are addressed (see
FEATURE_CONTRACT.md §7).

---

## 9. API

All endpoints require a node `X-API-Key`. Dev keys work out of the box when
`NASEEJ_NODE_KEYS` is unset.

### Ingest a pseudonymous transaction

```bash
curl -X POST localhost:8000/api/features/ingest-transaction \
  -H "Content-Type: application/json" -H "X-API-Key: dev-key-bank-a-local-only" \
  -d '{
    "transaction_id": "TX-DEMO-0001",
    "timestamp": "2026-06-12T10:00:00",
    "source_node_id": "NODE_A7C2F9E1",
    "from_bank": "101", "from_account": "0xSRC_A1",
    "to_bank": "101",   "to_account": "0xMULE_01",
    "amount": 2400.0, "currency": "US Dollar", "payment_format": "ACH"
  }'
# → 201 {"accepted": true, "transaction_id": "TX-DEMO-0001",
#        "events_in_window": 1, "accounts_tracked": 2, "zero_pii": true}
# 401 without a key · 403 if source_node_id ≠ authenticated node
# 422 if any value looks like PII (IBAN shape, name, phone, digit run, Arabic)
```

### Look up account features (node-scoped)

```bash
curl localhost:8000/api/features/account/0xMULE_01 \
  -H "X-API-Key: dev-key-bank-a-local-only"
# → 200 {"account_id": "0xMULE_01", "features": {"target_in_degree_1h": 5, ...}}
# The same call with Bank B's key → 403 (generic; identical to "unknown account")
```

### Score with context

```bash
curl -X POST localhost:8000/api/features/score-with-context \
  -H "Content-Type: application/json" -H "X-API-Key: dev-key-bank-a-local-only" \
  -d '{
    "timestamp": "2026-06-12T10:12:00",
    "from_bank": "101", "from_account": "0xMULE_01",
    "to_bank": "28856", "to_account": "0xINTL_DEST",
    "amount": 11200.0, "currency": "US Dollar", "payment_format": "Wire"
  }'
# → 200 {
#   "base_model_score": 0.0123,
#   "contextual_risk_adjustment": 0.45,
#   "final_contextual_score": 0.4623,
#   "prediction": "suspicious",
#   "explanation": [
#     "5 inbound transfers to the source account within the last hour",
#     "Cross-bank sweep follows rapid fan-in (outflow ≥ 60% of recent inflow)",
#     "New beneficiary bucket (unseen) for an unusually large transfer",
#     "Adjustment is a deterministic rule layer over the baseline model; the model has not been retrained on context features"
#   ],
#   "context_features": {...},
#   "model_retrained_on_context": false
# }
```

`POST /api/score-transaction` is unchanged and remains the legacy
single-transaction path; `score-with-context` is additive.

### Explaining a context score

`POST /api/explain/transaction` (node auth, same PII guard) reuses
`score-with-context` and returns a PII-safe explanation that separates the
**base-model attribution** (SHAP when available, deterministic fallback
otherwise — `top_factors`, bucketed values only) from the **context rule
layer** (`contextual_factors`). It restates the honesty contract in
`model_limitations`: the model was not retrained on context features, and
context can escalate but never soften the base score. See
[`EXPLAINABILITY.md`](EXPLAINABILITY.md).

### Metadata

```bash
curl localhost:8000/api/features/status    -H "X-API-Key: dev-key-bank-a-local-only"
curl localhost:8000/api/features/catalogue -H "X-API-Key: dev-key-bank-a-local-only"
```

### Environment

| Variable | Effect |
|---|---|
| `NASEEJ_FEATURE_SNAPSHOT` | If set, every accepted event is appended to this JSONL file (pseudonymous fields only); `feature_store_service.restore_from_snapshot()` rebuilds memory from it. Unset by default — purely in-memory. |

---

## 10. Demo integration

During the attack sequence the frontend ingests each synthetic transaction
into Bank A's feature store (fire-and-forget; offline → skipped). At
DETECTED it calls `score-with-context` for the sweep and the research strip
shows the contextual explanations plus a `CONTEXT FEATURES: LIVE` indicator.
Offline, the strip falls back to the same explanations labelled
**SIMULATED** — the demo never breaks and never overstates.
