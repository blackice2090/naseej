"""Analyst feedback loop — turn closed-case outcomes into calibration labels.

Endpoints (all node-authenticated, node-scoped, audited):
  POST /api/feedback/from-case/{case_id}   create a feedback label from a CLOSED
                                           case the caller may see; non-closed → 409.
  GET  /api/feedback                        node-scoped aggregate feedback counts.
  GET  /api/feedback/calibration-dataset    node-scoped calibration-dataset summary.

Respects case visibility/RBAC exactly like the case reads: 404 if the case does
not exist, audited generic 403 if it exists but the caller may not see it. These
endpoints NEVER create or mutate a case, and store only bucketed, PII-safe
labels (no raw transactions, identifiers, or feature values).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import AuthContext, require_context
from ..services import audit_service, feedback_service
from ..services.access_control import case_visible
from ..services.case_service import CaseNotFoundError, get_case_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_GENERIC_403 = "Not authorized for this resource or action."


def _visible_case_or_error(ctx: AuthContext, case_id: str, endpoint: str, action: str) -> dict:
    try:
        case = get_case_store().get(case_id)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"case {case_id} not found")
    if not case_visible(ctx, case):
        audit_service.record(node_id=ctx.node_id, endpoint=endpoint, action=action,
                             decision="denied", reason="case not visible to requesting node")
        raise HTTPException(status_code=403, detail=_GENERIC_403)
    return case


@router.post("/from-case/{case_id}", status_code=201)
def feedback_from_case(case_id: str, ctx: AuthContext = Depends(require_context)) -> dict:
    endpoint, action = "/api/feedback/from-case/{case_id}", "feedback_create"
    case = _visible_case_or_error(ctx, case_id, endpoint, action)

    # Only CLOSED cases yield a final calibration label (human-in-the-loop:
    # an open/under-review case has no confirmed outcome to learn from).
    status = case.get("status", "")
    if not feedback_service.is_closed(status):
        audit_service.record(node_id=ctx.node_id, endpoint=endpoint, action=action,
                             decision="rejected", pattern_id=case.get("pattern_id"),
                             reason=f"case not closed (status={status}); no final label")
        raise HTTPException(
            status_code=409,
            detail=f"case is '{status}', not closed — no final calibration label available",
        )

    rec = feedback_service.record(case, ctx.node_id)
    if rec is None:
        audit_service.record(node_id=ctx.node_id, endpoint=endpoint, action=action,
                             decision="rejected", reason="feedback blocked by PII guard")
        raise HTTPException(status_code=422, detail={"accepted": False,
                                                     "reasons": ["feedback record failed safety guard"]})

    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action, decision="accepted",
        pattern_id=case.get("pattern_id"), reason=f"label={rec['feedback_label']}",
    )
    # Safe, bucketed subset (no raw values; case/pattern ids are system refs).
    return {
        "accepted": True,
        "feedback_id": rec["feedback_id"],
        "case_id": rec["case_id"],
        "feedback_label": rec["feedback_label"],
        "candidate_risk_tier_bucket": rec["candidate_risk_tier_bucket"],
        "baseline_risk_tier_bucket": rec["baseline_risk_tier_bucket"],
        "linked_shadow_observation_id": rec["linked_shadow_observation_id"],
        "shadow_only": True,
        "pii_safe": True,
    }


@router.get("")
def feedback_summary(ctx: AuthContext = Depends(require_context)) -> dict:
    data = feedback_service.summary(ctx.node_id)
    audit_service.record(node_id=ctx.node_id, endpoint="/api/feedback", action="feedback_list",
                        decision="served", reason=f"labeled={data['labeled_count']}")
    return data


@router.get("/calibration-dataset")
def calibration_dataset(node_id: str | None = None, ctx: AuthContext = Depends(require_context)) -> dict:
    endpoint, action = "/api/feedback/calibration-dataset", "feedback_calibration_dataset"
    target = ctx.node_id
    if node_id and node_id != ctx.node_id:
        if not ctx.has("cases:view_all"):
            audit_service.record(node_id=ctx.node_id, endpoint=endpoint, action=action,
                                decision="denied", reason="cross-node calibration view requires view-all")
            raise HTTPException(status_code=403, detail=_GENERIC_403)
        target = node_id
    data = feedback_service.calibration_dataset(target)
    audit_service.record(node_id=ctx.node_id, endpoint=endpoint, action=action,
                        decision="served", reason=f"labeled={data['labeled_count']} met={data['minimum_label_threshold_met']}")
    return data
