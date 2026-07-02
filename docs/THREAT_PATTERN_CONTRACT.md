# Threat Pattern Data Contract — نسيج | Naseej

The threat pattern object is the **only** thing that ever crosses a bank
boundary on the Naseej network. This document defines its contract; the
machine-readable schema lives at
[`docs/schemas/threat_pattern.schema.json`](schemas/threat_pattern.schema.json).

> Status: **enforced.** `POST /api/patterns` validates every submission
> against this schema (closed — unknown fields rejected), requires the
> publishing permission on the node's profile, checks the authenticated
> node against `source_node_id`, runs the fail-closed zero-PII content
> guard, and audits the decision. Registry **reads enforce
> `governance_tags.sharing_scope`** (see below): the list endpoint serves
> only what the caller may see, and fetching a hidden pattern is an
> audited 403. See [`BACKEND_BLUEPRINT.md`](BACKEND_BLUEPRINT.md) §3 for
> what the minimal registry still lacks (broadcast routing, retention
> enforcement, revocation). A valid example lives at
> [`examples/threat_pattern_example.json`](examples/threat_pattern_example.json).

---

## Design principles

1. **Zero PII by construction, not by policy.** The schema has
   `additionalProperties: false` at every level — a conforming object
   *cannot* carry a name, IBAN, or account number, because there is no
   field for one.
2. **Buckets, never raw values.** Amounts, counts, and time windows are
   categorical buckets. A receiving bank can match shape; it cannot
   reconstruct a transaction.
3. **Deterministic matching.** Two banks observing the same fraud topology
   produce the same `pattern_hash` (proved by
   `ml/tests/test_privacy_hash.py::TestSameTopologyDifferentPIIProducesIdenticalHash`).
4. **Attested privacy.** `privacy_guarantees.zero_pii_verified` is set only
   after the automated `verify_zero_pii()` check passes at the source node,
   and the receiving node re-validates against the schema before ingestion.
5. **Governance travels with the data.** Retention, sharing scope, and
   human-review requirements are part of the object, so a receiving node
   can enforce them mechanically.

---

## Field reference

| Field | Type | Purpose |
|---|---|---|
| `pattern_id` | UUIDv4 | Unique id of this broadcast message |
| `pattern_hash` | `NSJ_<TYPE>_<16-hex>` | Deterministic hash of normalized topology — the matching key |
| `typology` | enum | One of the 8 AML typologies in `ml/src/pattern_library.py` |
| `graph_signature` | object | Node/edge counts + sorted degree sequences (positional anonymity) |
| `velocity_features` | object | Bucketed window, transaction count, amount magnitude, burstiness |
| `risk_score` | 0–1 | Detecting node's calibrated risk estimate |
| `confidence` | 0–1 | Confidence in the typology classification |
| `detection_timestamp` | ISO-8601 UTC | Minute-rounded generation time |
| `source_node_id` | `NODE_<8>` | Opaque network node id (not a bank routing code) |
| `evidence_summary` | string ≤500 | PII-screened free text for receiving analysts |
| `privacy_guarantees` | object | Attestation: zero-PII check, bucketing version, hash algorithm |
| `governance_tags` | object | Sharing scope (+ bilateral recipients), retention days, human-review flag, regulatory basis |

## Sharing scopes (enforced on registry reads)

`governance_tags.sharing_scope` decides who may consume the object. The
registry enforces it on every read (`backend/app/services/access_control.py`);
denials are audited 403s.

| Scope | Who may read |
|---|---|
| `local_only` | the source node only — registered for the node's own audit trail |
| `bilateral` | source node + the nodes listed in `governance_tags.shared_with_node_ids` (an empty/absent list means nobody else — fail closed) |
| `network_all` | every authenticated node whose profile grants `patterns:view_network` |
| `regulator_only` | source node + regulator/admin node types |

`shared_with_node_ids` is an optional array of opaque node ids (max 32,
unique, `NODE_<8>` format) and is meaningful only under `bilateral`.

## What is deliberately absent

No field exists for — and the schema rejects any object containing —
customer names, national IDs / iqama numbers, IBANs / BBANs / account
numbers, phone numbers, email addresses, device or IP identifiers, dates
of birth, raw transaction rows, exact amounts, or exact timestamps.

---

## Example instance (synthetic)

```json
{
  "pattern_id": "7f3c9a1e-2b4d-4e8f-9a6c-1d5e8b3f7a20",
  "pattern_hash": "NSJ_MULE_VELOCITY_8f9b2c4d1e7a3c5d",
  "typology": "mule_velocity",
  "graph_signature": {
    "node_count": 7,
    "edge_count": 6,
    "in_degree_sequence": [0, 0, 0, 0, 0, 1, 5],
    "out_degree_sequence": [0, 0, 1, 1, 1, 1, 2],
    "diameter": 2,
    "is_cross_bank": true
  },
  "velocity_features": {
    "window_bucket": "under_1h",
    "tx_count_bucket": "2_to_5",
    "amount_bucket": "5k_to_25k",
    "burst_score_bucket": "high"
  },
  "risk_score": 0.91,
  "confidence": 0.87,
  "detection_timestamp": "2026-06-11T09:42:00Z",
  "source_node_id": "NODE_A7C2F9E1",
  "evidence_summary": "Fan-in of 5 sub-threshold transfers into a single account within 40 minutes, followed by an international wire sweep of the accumulated balance.",
  "privacy_guarantees": {
    "zero_pii_verified": true,
    "bucketing_version": "buckets-v1",
    "hash_algorithm": "sha256-canonical-json-v1",
    "k_anonymity_floor": 5
  },
  "governance_tags": {
    "sharing_scope": "network_all",
    "retention_days": 90,
    "requires_human_review": true,
    "regulatory_basis": "SAMA-CFF-early-warning"
  }
}
```

---

## Validation lifecycle

```
Source bank                         Naseej network                Receiving bank
───────────                         ──────────────                ──────────────
pattern library finding
   → normalize + bucket (privacy layer)
   → verify_zero_pii()  ── fail → never broadcast
   → schema-validate
   → sign + broadcast      ──────►  registry stores,   ──────►   schema re-validate
                                    audit-logs, routes            → match against local txs
                                    by sharing_scope              → analyst review queue
                                                                  → retention enforced from
                                                                    governance_tags
```

## Versioning rules

- `bucketing_version` pins the bucket boundaries. **Changing boundaries
  invalidates all existing hashes** — receiving nodes must only match
  hashes produced under the same version.
- Schema changes are additive-only within a major version; removing or
  re-typing a field is a breaking change requiring a network-wide
  coordinated upgrade.
