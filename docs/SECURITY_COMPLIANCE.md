# Security & Compliance — نسيج | Naseej

Defensive financial-crime prevention only. This document states the
security and compliance posture of the research prototype and the
commitments the post-MVP product must meet.

**Status:** design commitments + current-prototype facts. Nothing here is a
certification claim. Naseej has not been audited, certified, or approved by
SAMA, SDAIA, or any other authority.

---

## 1. PDPL by design (SDAIA Personal Data Protection Law)

| Principle | How Naseej applies it |
|---|---|
| Data minimization | The cross-bank exchange object has no fields for personal data (`additionalProperties: false` — see [`THREAT_PATTERN_CONTRACT.md`](THREAT_PATTERN_CONTRACT.md)) |
| Purpose limitation | Shared objects carry `governance_tags.sharing_scope` and may only be used for fraud/AML prevention |
| Storage limitation | `governance_tags.retention_days` travels with every object; receiving nodes purge mechanically |
| Residency | Raw transaction data never leaves the bank's own infrastructure; only pattern hashes cross the boundary |
| Verifiability | `verify_zero_pii()` runs before every broadcast; 136 automated tests prove the hash engine excludes names, IBANs, national IDs, phone numbers, account numbers, device IDs, and DOBs |

**Prototype fact:** every value in the demo and test suite is synthetic
(AMLworld dataset + invented account handles). No real PII exists anywhere
in this repository.

## 2. SAMA counter-fraud alignment

Naseej targets the SAMA Counter-Fraud Framework objectives of proactive
detection, early-warning sharing, and cross-institution coordination:

- Early warning: a pattern detected at one bank reaches all member nodes
  before the same typology executes elsewhere.
- Coordination without disclosure: intelligence sharing that does not
  require inter-bank disclosure of customer data.
- Supervisory visibility: the post-MVP regulator dashboard gives SAMA
  read access to network statistics and audit trails (never customer data).

Production deployment would require SAMA sandbox participation and
supervision; that path is described in the roadmap, not claimed as done.

## 3. Zero-PII data exchange

The only object that crosses a bank boundary is the threat pattern object.
Its guarantees:

1. No PII fields exist in the schema (rejection at parse time).
2. All quantitative values are bucketed (no raw amounts/timestamps).
3. Node identities in graph signatures are positional, not account-derived.
4. Free-text `evidence_summary` is screened by a PII detector before broadcast.
5. The hash is deterministic over shape, not identity: the same topology at
   two banks produces the same hash with zero shared customer data.

**Enforced in the API path** (`POST /api/patterns`), in order:

| Gate | Implementation | Rejects |
|---|---|---|
| Node authentication | `X-API-Key` → node id (`backend/app/core/auth.py`) | 401 unknown/missing key |
| Publish permission | node profile `can_publish_patterns` (`backend/app/core/nodes.py`) | 403 — e.g. a read-only regulator node |
| JSON Schema (closed) | `docs/schemas/threat_pattern.schema.json` via `jsonschema`, format checking on | 422 — any extra field, bad format, wrong enum |
| Node identity match | `source_node_id` must equal the authenticated node | 403 — publishing as another node |
| Zero-PII content guard | `backend/app/services/pii_guard.py`, fail-closed | 422 — forbidden key names anywhere; IBAN-like, phone-like, email, account-handle, long-digit-run, or Arabic-script content in string fields |

Rejection reasons name the failing field and rule, never the offending
value, so neither API responses nor audit records can leak PII.

**v1 guard limitation:** exchange free text is English-only. Arabic content
is rejected wholesale because Arabic personal names cannot be reliably
distinguished from other Arabic text with a regex guard — failing closed is
the safe default. Arabic-capable PII detection (NER) is a post-MVP work
item; this is a guard limitation, not a product stance.

## 4. Audit logging

**Implemented (prototype level):** every request to a protected endpoint —
scoring, pattern analysis, registry reads and writes, and every rejection —
appends one record to a hash-chained JSONL log
(`backend/app/services/audit_service.py`, default
`backend/data/audit/audit.jsonl`, override `NASEEJ_AUDIT_LOG`).

Record fields: timestamp (UTC), node id, endpoint, action, decision, risk
tier, pattern id/hash, sanitized rejection reason, and `prev` (SHA-256 of
the previous record). The record schema is closed — there is no field for
payloads, so raw transactions and PII cannot be logged. `verify_chain()`
detects any in-place edit. Rejected payloads' `pattern_id` is logged only
when UUID-shaped, so attacker-controlled fields cannot smuggle data into
the log.

**Honest scope:** a hash chain makes tampering *detectable*, not impossible
— the file is still OS-mutable and the chain head lives with the file.
Path to immutable storage (post-MVP): ship the same records to a write-once
sink (object storage with a WORM/object-lock policy or a managed ledger
table) and anchor the rolling chain head externally, e.g. a daily head hash
published to the regulator dashboard. The record format does not change;
only the sink does.

## 5. Node identity, roles, and access partitioning

**Implemented (prototype level).** Each authenticated node resolves to a
server-side profile (`backend/app/core/nodes.py`): node type
(bank / regulator / admin), an `allowed_roles` envelope with a
`default_role`, and capability flags (publish patterns, create cases, view
network patterns, view all cases, confirm fraud, escalate). Effective
permissions are the intersection of node capabilities and role grants,
resolved per request into an `AuthContext`.

What is enforced now:

- **Pattern partitioning** — registry reads honor
  `governance_tags.sharing_scope` (`local_only` / `bilateral` /
  `network_all` / `regulator_only`; bilateral recipients listed in
  `shared_with_node_ids`, fail-closed when empty). A bank node never sees
  another bank's local-only or non-addressed bilateral intelligence.
- **Case partitioning** — a node lists/reads only cases it owns or that
  are explicitly visible to it; only the owner mutates. Regulator/admin
  nodes may hold `cases:view_all` (read-only oversight).
- **Role-based decisions** — analyst: take under review, notes, close
  no-action; senior analyst: + escalate, mark false positive; MLRO:
  + confirm fraud; regulator/admin: no case mutations. Roles come from the
  auth context only — request bodies are never consulted, and a role
  outside the node's envelope is an audited 403.
- **Denial auditing** — every denied access writes an audit record with a
  static sanitized reason and returns a generic 403 message.

Honest scope: this is one shared-secret credential **per node**, not per
analyst — role selection within the node's envelope is by header, which is
suitable for a single-tenant prototype only. Real deployments need
per-analyst credentials from the bank's IAM (role as a verified claim),
mTLS per node, and key rotation. A 403-vs-404 distinction still reveals
whether a guessed id exists; closing that requires uniform 404s, which we
trade away for clearer API semantics at this stage.

### Feature store boundary (node-local)

**Implemented (prototype level,** [`FEATURE_STORE.md`](FEATURE_STORE.md)**).**
The feature store ingests *pseudonymous* synthetic transactions
(`POST /api/features/ingest-transaction`) and computes rolling velocity /
counterparty / graph-window features **inside one node's boundary**:

- **Closed schema + dedicated PII guard.** The ten-field ingest schema
  rejects unknown fields; `pii_guard.find_transaction_pii` (fail-closed)
  rejects PII *shapes* inside values — IBAN patterns, 8+ digit runs,
  phone/email patterns, Arabic free text, space-containing name-like
  handles. The network-boundary guard in §3 is untouched: raw handles
  still never cross between banks.
- **Partitioned on the authenticated identity.** Window state is keyed on
  the `AuthContext` node id, never on request input. Bank B querying a
  Bank A account receives the same generic audited 403 as querying a
  nonexistent account, so membership cannot be probed. Feature values
  never leave the node that computed them; the cross-bank exchange remains
  pattern hashes only.
- **Audited, metadata-only.** Ingest, lookup, contextual scoring and every
  denial append audit records; handles and amounts have no field to land
  in (asserted by tests).
- **Honest guard limitation:** the guard blocks PII shapes — it cannot
  prove a handle is synthetic (a concatenated real name would pass). Real
  deployments must tokenise account identifiers upstream, inside the bank.

## 6. Human-in-the-loop review

- No autonomous blocking is claimed or implemented. The demo's "BLOCKED"
  stage illustrates the *target* prevention story; the documented operating
  model routes every match to an analyst queue.
- `governance_tags.requires_human_review` lets the broadcasting bank force
  analyst review at receiving banks.
- The analyst workflow (queue, explanation, override, feedback) is specified
  in [`INVESTIGATOR_EXPERIENCE.md`](INVESTIGATOR_EXPERIENCE.md).

## 7. Model risk governance

- Model documentation: training data, features, metrics, and limitations are
  versioned in `ml/reports/` and `ml/models/`.
- Threshold governance: operating modes (conservative/balanced/aggressive)
  are explicit, with per-mode precision/recall published in
  `threshold_analysis.json`.
- Honest metrics: PR-AUC is the primary metric at 0.1% prevalence; accuracy
  is deliberately not reported.
- Post-MVP: drift monitoring, challenger models, and periodic revalidation
  per the Model Monitoring service; phase 7 of the
  [`ML_ROADMAP.md`](ML_ROADMAP.md) covers explainability (SHAP) and review.

## 8. False-positive handling

- Every alert carries a "why flagged" explanation (typology + features).
- Analyst dispositions (confirmed / false positive) are recorded as labels
  and fed back into training data.
- False-positive rate is a first-class published metric (currently 0.05% on
  the synthetic test set) and a drift-monitored quantity post-MVP.
- A pattern repeatedly dispositioned as false positive across nodes triggers
  registry-level review and possible revocation of the broadcast.

## 9. Incident response workflow (post-MVP commitment)

1. **Detect** — monitoring alert, node report, or regulator query.
2. **Classify** — privacy incident (suspected PII in a broadcast), integrity
   incident (bad/poisoned patterns), or availability incident.
3. **Contain** — revoke the affected pattern ids network-wide; suspend the
   offending node's broadcast rights at the gateway.
4. **Notify** — member banks, and SDAIA/SAMA per PDPL breach-notification
   timelines if personal data was involved.
5. **Recover & review** — root cause, corrective controls, post-incident
   report into the audit log.

Poisoning note: a malicious or compromised node broadcasting misleading
patterns is the main integrity threat. Mitigations: schema validation,
per-node rate limits, anomaly detection on broadcast behavior, human review
before action, and full audit traceability per `source_node_id`.

## 10. Data retention assumptions

| Data class | Where | Assumed retention |
|---|---|---|
| Raw transactions | Bank premises only | Bank's own policy / SAMA rules — never enters Naseej |
| Threat pattern objects | Registry + receiving nodes | `retention_days` per object (default 90, max 10 years) |
| Audit log | Core | 10 years (financial-sector norm), append-only |
| Case records | Bank premises | Bank's AML record-keeping obligations (typically 10 years) |
| Model artifacts & metrics | Bank + core | Life of model + 2 revalidation cycles |

These are assumptions to validate with compliance counsel, not legal advice.

## 11. Explicitly out of scope

- Offensive security tooling of any kind (exploitation, evasion, deanonymization).
- Re-identification of customers from pattern hashes, by anyone, including regulators.
- Autonomous customer blocking without human review.
- Sanctions screening, KYC/CDD, and transaction monitoring rule engines —
  Naseej complements these, it does not replace them.
- Customer-facing decisions or adverse-action notices.
- Processing of real customer data in the research prototype — synthetic only.
