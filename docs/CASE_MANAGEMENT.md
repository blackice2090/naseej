# Case Management — نسيج | Naseej

How detected threat patterns become analyst-reviewable cases, and why a
human is always in the loop.

**Status:** implemented at prototype level (`backend/app/services/case_service.py`,
`backend/app/api/routes_cases.py`, investigator view in `naseej-ai/`).
Research prototype on synthetic data — not a production case-management
system.

---

## The human-in-the-loop model

Naseej **detects and recommends; analysts decide.** No code path in this
repository executes an action against a customer or transaction. The
strongest thing the system produces is a *recommended action* on a case,
and the status machine makes a fraud verdict unreachable without review:

- A case opens as `open` — created from a registered, zero-PII threat
  pattern, never directly from raw transactions.
- `closed_confirmed` and `closed_false_positive` are only reachable from
  `under_review` or `escalated`. There is no `open → closed_confirmed`
  edge, so a fraud confirmation **cannot skip human review** — this is
  encoded in the transition table, not just policy text.
- Every status change requires an attributed analyst decision with a
  written reason, which is appended to an immutable decision history.

### Why autonomous blocking is not claimed

1. **Model honesty** — the baseline scores 27.3% precision at threshold on
   synthetic data; most alerts are not fraud. Auto-blocking at that
   precision would harm legitimate customers roughly 3 times in 4.
2. **Regulatory posture** — SAMA-supervised institutions remain accountable
   for customer-impacting decisions; a network recommendation is evidence,
   not authority.
3. **Adversarial robustness** — until pattern-poisoning defenses exist
   (see SECURITY_COMPLIANCE §9), acting automatically on network
   intelligence would let a compromised node weaponize false patterns.

The demo's "BLOCKED" stamp illustrates the *target* prevention story at
machine speed; the documented operating model routes that same match into
the investigator queue you can open from the top nav.

---

## Case lifecycle

```
                              ┌──────────────────┐
                    ┌────────►│   under_review   │◄────────┐
                    │         └────────┬─────────┘         │ (de-escalate)
              ┌─────┴────┐             │            ┌──────┴─────┐
 pattern ────►│   open   │─────────────┼───────────►│ escalated  │
 (registry)   └─────┬────┘             │            └──────┬─────┘
                    │                  ▼                   │
                    │     ┌─────────────────────────┐      │
                    └────►│ closed_no_action        │      │
                          │ closed_confirmed     ◄──┴──────┘
                          │ closed_false_positive │   (only from review/
                          └─────────────────────────┘    escalated)
```

| From \ To | under_review | escalated | closed_confirmed | closed_false_positive | closed_no_action |
|---|---|---|---|---|---|
| **open** | ✓ | ✓ | — | — | ✓ |
| **under_review** | — | ✓ | ✓ | ✓ | ✓ |
| **escalated** | ✓ | — | ✓ | ✓ | ✓ |
| **closed_\*** | — | — | — | — | — |

Closed states are terminal. Invalid transitions are rejected with HTTP 409
and the rejection itself is audited.

## Analyst decisions

Decisions are semantic shortcuts onto the same status machine — validated
against the table above, never bypassing it:

| Decision | Resulting status | Minimum role | Notes |
|---|---|---|---|
| `take_under_review` | `under_review` | analyst | assigns the case to the acting node on first touch |
| `escalate` | `escalated` | senior_analyst | senior/compliance attention |
| `confirm_fraud` | `closed_confirmed` | mlro | only from review/escalated |
| `mark_false_positive` | `closed_false_positive` | senior_analyst | sets `false_positive_flag`; feeds the FP-rate story |
| `close_no_action` | `closed_no_action` | analyst | triage dismissal |

Role permissions are enforced on `POST /decision` **and** on
`PATCH /status` (each target status maps to the decision that produces it),
so there is no unguarded path onto the status machine. A decision the
caller's role does not permit is an audited 403.

Each decision appends to `decision_history`: timestamp, node id, decision,
reason, previous → new status, the acting analyst role, and the audit ref
of the corresponding audit-log record. History entries are never modified
or removed — the store appends full case snapshots to JSONL and never
rewrites a line, so silent overwrites are structurally impossible.

## Where roles come from

**Never from request bodies.** The backend resolves an `AuthContext` per
request (`backend/app/core/auth.py` + `nodes.py`): the API key
authenticates the node, the node's server-side profile defines its
`allowed_roles` envelope and `default_role`, and the request acts under the
default role unless `X-Analyst-Role` selects another role *from that
envelope* (anything outside it is an audited 403). A body-supplied
`analyst_role` field is ignored by construction — the input schemas have no
such field — and `decision_history` records the context-resolved role.

Local-simulation profiles (`NASEEJ_NODE_PROFILES` overrides them in JSON):

| Dev key | Node | Type | Default role | Allowed roles |
|---|---|---|---|---|
| `dev-key-bank-a-local-only` | `NODE_A7C2F9E1` (Bank A) | bank | analyst | analyst, senior_analyst, mlro |
| `dev-key-bank-b-local-only` | `NODE_B3D8E2F4` (Bank B) | bank | mlro | analyst, senior_analyst, mlro |
| `dev-key-regulator-local-only` | `NODE_REG5C7A1` | regulator | regulator | regulator |

This is one-credential-per-node prototype auth: in a real deployment each
analyst gets their own credential from the bank's IAM and the role arrives
as a verified claim, not a header.

## Case ownership & visibility

Every case records `owner_node_id` (the node that opened it) and
`visible_to_node_ids` (owner + the pattern's detecting node). Enforcement
(`backend/app/services/access_control.py`):

- A node **lists and reads** only cases it owns or that are explicitly
  visible to it. Regulator/admin nodes with `cases:view_all` read
  everything — and can mutate nothing (their roles grant no decision
  permissions).
- Only the **owning node mutates** a case (status, decisions, notes); the
  detecting node of a cross-bank pattern can follow the case read-only.
- A node cannot open a case from a pattern it is not cleared to read
  (sharing-scope check at creation).
- Denied access returns a generic 403 and writes an audit record with a
  static, sanitized reason — caller-supplied content never reaches the log.
  (Known limitation: 403-vs-404 still reveals that a guessed id exists.)

## Recommended actions

Derived from pattern risk when the case is created (`recommend_action()`):

| Condition | Recommendation |
|---|---|
| risk ≥ 0.9 | `freeze_for_review` |
| risk ≥ 0.7, cross-bank | `escalate_to_compliance` |
| risk ≥ 0.7 | `delay_transaction` |
| risk ≥ 0.4 | `request_step_up_verification` |
| otherwise | `monitor` |

These are recommendations rendered in the UI with an explicit "no action is
executed by Naseej" notice.

## Privacy in cases

A case carries exactly what the zero-PII pattern carried (hash, typology,
buckets, evidence summary) plus analyst free text. All free text — notes
**and** decision reasons — passes the same fail-closed PII guard as network
exchanges before it is stored: Arabic script, IBAN-like strings, phone-like
numbers, emails, account handles, and long digit runs are rejected with
sanitized reasons. Rejected text is never stored and the rejection is
audited without echoing the content. Analyst identity is a role label plus
node id — personal analyst identifiers stay in the bank's own IAM.

## "Why flagged?" explanations

The investigator's "Why flagged?" panel is backed by the explainability engine
([`EXPLAINABILITY.md`](EXPLAINABILITY.md)) when the backend is live:
`GET /api/explain/case/{case_id}` returns a PII-safe explanation with the
typology rationale (what was detected and why it matters for AML), top risk
factors (SHAP or deterministic fallback attribution, bucketed values only),
any contextual velocity signals, the threshold policy, and the model
limitations. The endpoint respects the same case visibility and RBAC as the
case reads (404 unknown, audited generic 403 if hidden) and audits every
served/denied explanation. When the backend is offline the panel falls back to
the static typology copy — the case story never breaks and never overstates.
The explanation is **decision-support only**, never a legal sufficiency claim.

## How audit logs support investigation

Every case write produces a hash-chained audit record, and the record's
ref (the SHA-256 of its log line) is attached to the case's `audit_refs`
and to the triggering decision-history entry. An investigator or regulator
can therefore walk: case → decision history entry → audit ref → position
in the tamper-evident log — and `verify_chain()` proves the log wasn't
edited after the fact. Reads are audited too (`case_list`, `case_get`),
so access to case data is itself reviewable.

## Simulated vs real

| Aspect | Status |
|---|---|
| Status machine, transition enforcement, decision history | **Real** — backend-enforced, 34 tests |
| PII guard on notes/reasons | **Real** — same guard as network exchange |
| Audit chaining of every case write | **Real** |
| Case storage | Real but prototype-grade (JSONL snapshots, single process) |
| Investigator UI when backend is live | Real API calls end to end |
| Investigator UI when backend is offline | Mock cases, local-only "safe mock controls" mirroring the same role + transition rules, labelled `MOCK DATA` |
| The demo's case creation | Real pipeline when live (register pattern → gates → case); local mock when offline |
| Case ownership, visibility & role permissions | **Real** — backend-enforced per request, audited denials |
| Analyst identity & roles | Role-from-auth-context is real; identity is one credential per node (no per-analyst IAM yet) |
| Customer/transaction context panels | Not built — cases link to pattern hashes only |
| "Why flagged?" explanation (SHAP/fallback, bucketed, PII-safe) | **Real** when live (`/api/explain/case`); static typology copy offline |

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/auth/whoami` | GET | backend-resolved identity (node, role, permissions) for UI mirroring |
| `/api/cases/from-pattern/{pattern_id}` | POST | open a case from a registered pattern (404 unknown, 403 invisible pattern or missing `cases:create`, 409 duplicate open) |
| `/api/cases` | GET | list cases visible to the caller (`?status=` filter) |
| `/api/cases/{case_id}` | GET | full case (403 if not visible) |
| `/api/cases/{case_id}/status` | PATCH | raw status transition (owner-only, role-gated, validated) |
| `/api/cases/{case_id}/notes` | POST | append analyst note (owner-only, PII-guarded) |
| `/api/cases/{case_id}/decision` | POST | semantic decision (owner-only, role-gated, validated, PII-guarded) |
| `/api/explain/case/{case_id}` | GET | PII-safe "Why flagged?" explanation (visibility + RBAC enforced, audited) |

All endpoints require node authentication (`X-API-Key`); all writes and all
denials are audited.

## Closed-case feedback → calibration dataset

When a case is **closed**, its outcome can become a bucketed, PII-safe
calibration label via `POST /api/feedback/from-case/{case_id}` — the analyst
feedback loop ([ANALYST_FEEDBACK_LOOP.md](ANALYST_FEEDBACK_LOOP.md)). Only
closed cases yield a final label (`closed_confirmed → confirmed_fraud`,
`closed_false_positive → false_positive`, `closed_no_action → no_action`); a
non-closed case returns 409. This endpoint **respects the same visibility/RBAC**
as the case reads, **never creates or mutates a case**, stores no PII or raw
values, and is audited. It is comparison/calibration-dataset only — the
candidate model is not deployed and not calibrated.
