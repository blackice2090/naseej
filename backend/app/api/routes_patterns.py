"""Threat Pattern Registry endpoints.

Every write passes four gates, in order, and every request is audited:

    node auth (401) → publish permission (403) → JSON Schema (422) →
    zero-PII guard (422) → store (201)

Plus two integrity rules: the authenticated node must match the object's
``source_node_id`` (403 — a node cannot publish patterns as someone else),
and ``pattern_id`` must be new (409).

Reads enforce the pattern's ``governance_tags.sharing_scope``
(see services/access_control.py): the list endpoint serves only what the
caller may see, and fetching a hidden pattern by id is an audited 403 with
a generic message.

Rejection reasons are sanitized by construction (schema/guard messages name
fields and rules, never values) so they are safe to return and audit.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from ..core.auth import AuthContext, require_context
from ..core.pattern_schema import validate_pattern
from ..services import audit_service, pii_guard
from ..services.access_control import pattern_visible
from ..services.registry_service import DuplicatePatternError, get_registry

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


def _risk_tier(score: float) -> str:
    return "critical" if score >= 0.9 else "high" if score >= 0.7 else "medium" if score >= 0.4 else "low"


_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _safe_pattern_id(pattern: Any) -> str | None:
    """Only UUID-shaped ids are audit-loggable — an arbitrary string in the
    pattern_id field of a *rejected* payload could carry PII."""
    pid = pattern.get("pattern_id") if isinstance(pattern, dict) else None
    return pid if isinstance(pid, str) and _UUID_RE.match(pid) else None


@router.post("", status_code=201)
def register_pattern(
    pattern: dict[str, Any] = Body(...),
    ctx: AuthContext = Depends(require_context),
) -> dict:
    def reject(status: int, reasons: list[str], decision: str = "rejected") -> HTTPException:
        audit_service.record(
            node_id=ctx.node_id,
            endpoint="/api/patterns",
            action="pattern_register",
            decision=decision,
            pattern_id=_safe_pattern_id(pattern),
            reason="; ".join(reasons[:5]),
        )
        return HTTPException(status_code=status, detail={"accepted": False, "reasons": reasons})

    # Gate 1 — the node's profile must allow publishing at all (a read-only
    # regulator node cannot inject intelligence into the network).
    if not ctx.has("patterns:publish"):
        raise reject(403, ["node is not permitted to publish patterns"], decision="denied")

    # Gate 2 — canonical JSON Schema (closed: unknown fields rejected).
    schema_errors = validate_pattern(pattern)
    if schema_errors:
        raise reject(422, schema_errors)

    # Gate 3 — a node may only publish its own detections.
    if pattern["source_node_id"] != ctx.node_id:
        raise reject(403, [f"source_node_id does not match authenticated node {ctx.node_id}"])

    # Gate 4 — zero-PII content guard (fail-closed).
    pii_violations = pii_guard.find_pii(pattern)
    if pii_violations:
        raise reject(422, pii_violations)

    try:
        envelope = get_registry().add(pattern, source_node_id=ctx.node_id)
    except DuplicatePatternError:
        raise reject(409, [f"pattern_id {pattern['pattern_id']} already registered"])

    audit_service.record(
        node_id=ctx.node_id,
        endpoint="/api/patterns",
        action="pattern_register",
        decision="accepted",
        risk_tier=_risk_tier(pattern["risk_score"]),
        pattern_id=pattern["pattern_id"],
        pattern_hash=pattern["pattern_hash"],
    )
    return {"accepted": True, "pattern_id": pattern["pattern_id"], "registered_at": envelope["registered_at"]}


@router.get("")
def list_patterns(
    typology: str | None = None,
    ctx: AuthContext = Depends(require_context),
) -> dict:
    # Sharing-scope partitioning: serve only what this node may see.
    items = [e for e in get_registry().list(typology=typology)
             if pattern_visible(ctx, e["pattern"])]
    audit_service.record(
        node_id=ctx.node_id,
        endpoint="/api/patterns",
        action="pattern_list",
        decision="served",
        reason=f"count={len(items)}" + (f" typology={typology}" if typology else ""),
    )
    return {"count": len(items), "patterns": items}


@router.get("/{pattern_id}")
def get_pattern(
    pattern_id: str,
    ctx: AuthContext = Depends(require_context),
) -> dict:
    envelope = get_registry().get(pattern_id)
    safe_id = pattern_id if _UUID_RE.match(pattern_id) else None
    if envelope is None:
        audit_service.record(
            node_id=ctx.node_id, endpoint="/api/patterns/{pattern_id}",
            action="pattern_get", decision="not_found", pattern_id=safe_id,
        )
        raise HTTPException(status_code=404, detail=f"pattern {pattern_id} not found")
    if not pattern_visible(ctx, envelope["pattern"]):
        # Audited denial; the generic detail never describes the pattern.
        # (Known limitation: a 403 vs 404 still reveals the id exists.)
        audit_service.record(
            node_id=ctx.node_id, endpoint="/api/patterns/{pattern_id}",
            action="pattern_get", decision="denied", pattern_id=safe_id,
            reason="pattern not visible to requesting node (sharing_scope)",
        )
        raise HTTPException(status_code=403, detail="Not authorized for this resource or action.")
    audit_service.record(
        node_id=ctx.node_id, endpoint="/api/patterns/{pattern_id}",
        action="pattern_get", decision="served", pattern_id=safe_id,
    )
    return envelope
