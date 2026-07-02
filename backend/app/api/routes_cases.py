"""Case Management endpoints — human-in-the-loop investigation.

Every endpoint requires node authentication and resolves an AuthContext
(node id, node type, role, permissions). Enforcement order on mutations:

    auth (401) → case exists (404) → visible to node (403) → node owns the
    case (403) → role permits the action (403) → PII guard on free text
    (422) → status machine (409) → store + audit

Access denials return 403 with a generic message (they never describe the
hidden object), and every denial writes an audit record with a sanitized,
static reason — caller-supplied content never reaches the log.

The acting analyst role comes from the AuthContext, never from the request
body; decision history records that resolved role. Nothing here executes an
action against a transaction: recommended actions are recommendations, and
status changes are attributed analyst decisions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import AuthContext, require_context
from ..core.schemas import CaseDecisionIn, CaseNoteIn, CaseStatusPatchIn
from ..services import audit_service, pii_guard
from ..services.access_control import (
    DECISION_PERMISSION,
    case_mutable_by,
    case_visible,
    pattern_visible,
)
from ..services.case_service import (
    DECISION_TO_STATUS,
    TRANSITIONS,
    CaseNotFoundError,
    DuplicateOpenCaseError,
    InvalidTransitionError,
    get_case_store,
)
from ..services.registry_service import get_registry

router = APIRouter(prefix="/api/cases", tags=["cases"])

# Status targets map 1:1 onto decisions, so PATCH /status is gated by the
# same permissions as POST /decision — no side door onto the status machine.
_STATUS_TO_DECISION = {status: decision for decision, status in DECISION_TO_STATUS.items()}


def _audit(node_id: str, endpoint: str, action: str, decision: str, **kw) -> str:
    return audit_service.record(
        node_id=node_id, endpoint=endpoint, action=action, decision=decision, **kw
    )["ref"]


def _deny(ctx: AuthContext, endpoint: str, action: str, reason: str) -> HTTPException:
    """Audited 403. *reason* must be a static, sanitized string (it is
    logged); the HTTP detail stays generic so it cannot leak what exists."""
    _audit(ctx.node_id, endpoint, action, "denied", reason=reason)
    return HTTPException(status_code=403, detail="Not authorized for this resource or action.")


def _guard_free_text(ctx: AuthContext, endpoint: str, action: str, fields: dict[str, str]) -> None:
    """Reject any analyst free text containing possible PII (fail-closed)."""
    violations = pii_guard.find_pii(fields)
    if violations:
        _audit(ctx.node_id, endpoint, action, "rejected", reason="; ".join(violations[:5]))
        raise HTTPException(status_code=422, detail={"accepted": False, "reasons": violations})


def _visible_case_or_error(ctx: AuthContext, case_id: str, endpoint: str, action: str) -> dict:
    """404 if the case does not exist, audited 403 if it exists but the
    caller may not see it. A 403 deliberately confirms only that *some*
    case id was guessed — the body never describes it (documented
    limitation: distinguishing 403/404 reveals id existence)."""
    try:
        case = get_case_store().get(case_id)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"case {case_id} not found")
    if not case_visible(ctx, case):
        raise _deny(ctx, endpoint, action, "case not visible to requesting node")
    return case


def _require_mutation_rights(
    ctx: AuthContext, case: dict, decision: str, endpoint: str, action: str
) -> None:
    if not case_mutable_by(ctx, case):
        raise _deny(ctx, endpoint, action, "only the owning node may modify a case")
    needed = DECISION_PERMISSION[decision]
    if not ctx.has(needed):
        raise _deny(ctx, endpoint, action, f"role lacks permission {needed}")


# ── creation ───────────────────────────────────────────────────────────────


@router.post("/from-pattern/{pattern_id}", status_code=201)
def create_case_from_pattern(pattern_id: str, ctx: AuthContext = Depends(require_context)) -> dict:
    if not ctx.has("cases:create"):
        raise _deny(ctx, "/api/cases/from-pattern", "case_create",
                    "node lacks permission cases:create")

    envelope = get_registry().get(pattern_id)
    if envelope is None:
        _audit(ctx.node_id, "/api/cases/from-pattern", "case_create", "rejected",
               reason="pattern not found in registry")
        raise HTTPException(status_code=404, detail=f"pattern {pattern_id} not found in registry")

    # A node cannot open a case on intelligence it is not cleared to read.
    if not pattern_visible(ctx, envelope["pattern"]):
        raise _deny(ctx, "/api/cases/from-pattern", "case_create",
                    "pattern not visible to requesting node")

    try:
        case = get_case_store().create_from_pattern(envelope["pattern"], owner_node_id=ctx.node_id)
    except DuplicateOpenCaseError:
        _audit(ctx.node_id, "/api/cases/from-pattern", "case_create", "rejected",
               pattern_id=pattern_id, reason="open case already exists for pattern")
        raise HTTPException(status_code=409, detail=f"an open case already exists for pattern {pattern_id}")

    ref = _audit(
        ctx.node_id, "/api/cases/from-pattern", "case_create", "accepted",
        risk_tier=case["risk_tier"], pattern_id=pattern_id, pattern_hash=case["pattern_hash"],
    )
    return get_case_store().attach_audit_ref(case["case_id"], ref)


# ── reads ──────────────────────────────────────────────────────────────────


@router.get("")
def list_cases(status: str | None = None, ctx: AuthContext = Depends(require_context)) -> dict:
    items = [c for c in get_case_store().list(status=status) if case_visible(ctx, c)]
    audit_service.record(
        node_id=ctx.node_id, endpoint="/api/cases", action="case_list", decision="served",
        reason=f"count={len(items)}" + (f" status={status}" if status else ""),
    )
    return {"count": len(items), "cases": items}


@router.get("/{case_id}")
def get_case(case_id: str, ctx: AuthContext = Depends(require_context)) -> dict:
    case = _visible_case_or_error(ctx, case_id, "/api/cases/{case_id}", "case_get")
    audit_service.record(
        node_id=ctx.node_id, endpoint="/api/cases/{case_id}", action="case_get",
        decision="served", pattern_id=case["pattern_id"],
    )
    return case


# ── mutations ──────────────────────────────────────────────────────────────


@router.patch("/{case_id}/status")
def change_status(
    case_id: str, payload: CaseStatusPatchIn, ctx: AuthContext = Depends(require_context)
) -> dict:
    endpoint, action = "/api/cases/{case_id}/status", "case_status_change"
    case = _visible_case_or_error(ctx, case_id, endpoint, action)
    decision_for_target = _STATUS_TO_DECISION[payload.new_status]
    _require_mutation_rights(ctx, case, decision_for_target, endpoint, action)
    _guard_free_text(ctx, endpoint, action, {"reason": payload.reason})
    try:
        # Validate before audit so the audit decision is accurate; the store
        # re-validates under its lock.
        if payload.new_status not in TRANSITIONS.get(case["status"], frozenset()):
            raise InvalidTransitionError(f"{case['status']} → {payload.new_status}")
        ref = _audit(
            ctx.node_id, endpoint, action, "accepted",
            risk_tier=case["risk_tier"], pattern_id=case["pattern_id"],
            reason=f"{case['status']} → {payload.new_status}",
        )
        return get_case_store().transition(
            case_id, payload.new_status,
            node_id=ctx.node_id, reason=payload.reason,
            analyst_role=ctx.role, audit_ref=ref,
        )
    except InvalidTransitionError as exc:
        _audit(ctx.node_id, endpoint, action, "rejected",
               pattern_id=case["pattern_id"], reason=f"invalid transition {exc}")
        raise HTTPException(status_code=409, detail=f"invalid status transition: {exc}")


@router.post("/{case_id}/notes")
def add_note(
    case_id: str, payload: CaseNoteIn, ctx: AuthContext = Depends(require_context)
) -> dict:
    endpoint, action = "/api/cases/{case_id}/notes", "case_note_add"
    case = _visible_case_or_error(ctx, case_id, endpoint, action)
    if not case_mutable_by(ctx, case):
        raise _deny(ctx, endpoint, action, "only the owning node may modify a case")
    if not ctx.has("cases:note"):
        raise _deny(ctx, endpoint, action, "role lacks permission cases:note")
    _guard_free_text(ctx, endpoint, action, {"note": payload.note})
    ref = _audit(
        ctx.node_id, endpoint, action, "accepted",
        risk_tier=case["risk_tier"], pattern_id=case["pattern_id"],
    )
    return get_case_store().add_note(
        case_id, payload.note,
        node_id=ctx.node_id, analyst_role=ctx.role, audit_ref=ref,
    )


@router.post("/{case_id}/decision")
def record_decision(
    case_id: str, payload: CaseDecisionIn, ctx: AuthContext = Depends(require_context)
) -> dict:
    endpoint, action = "/api/cases/{case_id}/decision", "case_decision"
    case = _visible_case_or_error(ctx, case_id, endpoint, action)
    _require_mutation_rights(ctx, case, payload.decision, endpoint, action)
    _guard_free_text(ctx, endpoint, action, {"reason": payload.reason})
    new_status = DECISION_TO_STATUS[payload.decision]
    try:
        if new_status not in TRANSITIONS.get(case["status"], frozenset()):
            raise InvalidTransitionError(f"{case['status']} → {new_status}")
        ref = _audit(
            ctx.node_id, endpoint, action, "accepted",
            risk_tier=case["risk_tier"], pattern_id=case["pattern_id"],
            reason=f"{payload.decision}: {case['status']} → {new_status}",
        )
        return get_case_store().transition(
            case_id, new_status,
            node_id=ctx.node_id, reason=payload.reason,
            analyst_role=ctx.role,
            decision=payload.decision, audit_ref=ref,
        )
    except InvalidTransitionError as exc:
        _audit(ctx.node_id, endpoint, action, "rejected",
               pattern_id=case["pattern_id"],
               reason=f"decision {payload.decision} invalid from {case['status']}")
        raise HTTPException(
            status_code=409,
            detail=f"decision '{payload.decision}' is not allowed from status '{case['status']}'",
        )
