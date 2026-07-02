"""Explainability endpoints — analyst-readable "Why flagged?" answers.

Three endpoints, mirroring the existing auth/visibility posture:

  POST /api/explain/transaction   node auth; pseudonymous tx → context-score
                                   explanation. Same PII guard as
                                   /api/features/score-with-context.
  GET  /api/explain/case/{id}      node auth; respects case visibility/RBAC
                                   (404 if absent, audited 403 if hidden).
  GET  /api/explain/model          public read-only; report-derived summary,
                                   degrades gracefully if reports are missing.

Every served explanation and every denial writes a metadata-only audit
record. Payloads and PII are never logged; explanation bodies are PII-safe by
construction and double-checked by the explanation service before return.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import AuthContext, require_context
from ..core.schemas import ContextScoreIn, TransactionIn
from ..services import (
    audit_service,
    explanation_service,
    pii_guard,
)
from ..services.access_control import case_visible, pattern_visible
from ..services.case_service import CaseNotFoundError, get_case_store
from ..services.registry_service import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/explain", tags=["explain"])

_GENERIC_403 = "Not authorized for this resource or action."


def _reject(ctx: AuthContext, endpoint: str, action: str, status: int,
            reasons: list[str], decision: str = "denied") -> HTTPException:
    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action,
        decision=decision, reason="; ".join(reasons[:5]),
    )
    if status == 403:
        return HTTPException(status_code=403, detail=_GENERIC_403)
    return HTTPException(status_code=status, detail={"accepted": False, "reasons": reasons})


# ── transaction explanation ──────────────────────────────────────────────────

@router.post("/transaction")
def explain_transaction(
    body: ContextScoreIn,
    ctx: AuthContext = Depends(require_context),
) -> dict:
    endpoint, action = "/api/explain/transaction", "explain_transaction"

    if body.source_node_id is not None and body.source_node_id != ctx.node_id:
        raise _reject(ctx, endpoint, action, 403,
                      ["source_node_id does not match authenticated node"])

    violations = pii_guard.find_transaction_pii(body.model_dump(exclude_none=True))
    if violations:
        raise _reject(ctx, endpoint, action, 422, violations, decision="rejected")

    # Reuse the existing context-scoring path so the explanation matches what
    # the scoring endpoint would return for the same transaction.
    from .routes_features import score_with_context

    context_out = score_with_context(body, ctx)
    context_result = context_out.model_dump()

    tx = TransactionIn(
        timestamp=body.timestamp, from_bank=body.from_bank,
        from_account=body.from_account, to_bank=body.to_bank,
        to_account=body.to_account, amount=body.amount,
        currency=body.currency, payment_format=body.payment_format,
    )
    explanation = explanation_service.explain_transaction(tx, context_result=context_result)

    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action, decision="served",
        risk_tier=explanation.get("risk_tier"),
        reason=f"method={explanation.get('explanation_method')} factors={len(explanation.get('top_factors', []))}",
    )
    return explanation


# ── case explanation ─────────────────────────────────────────────────────────

@router.get("/case/{case_id}")
def explain_case(case_id: str, ctx: AuthContext = Depends(require_context)) -> dict:
    endpoint, action = "/api/explain/case/{case_id}", "explain_case"

    try:
        case = get_case_store().get(case_id)
    except CaseNotFoundError:
        # 404 mirrors the case-read endpoint; no audit (nothing existed).
        raise HTTPException(status_code=404, detail=f"case {case_id} not found")

    if not case_visible(ctx, case):
        raise _reject(ctx, endpoint, action, 403, ["case not visible to requesting node"])

    # Best-effort enrich with the registered pattern's bucketed evidence, but
    # only if the caller may also see that pattern (fail-safe: skip otherwise).
    pattern = None
    envelope = get_registry().get(case.get("pattern_id", ""))
    if envelope is not None and pattern_visible(ctx, envelope["pattern"]):
        pattern = envelope["pattern"]

    explanation = explanation_service.explain_case(case, pattern=pattern)

    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action, decision="served",
        risk_tier=explanation.get("risk_tier"), pattern_id=case.get("pattern_id"),
        reason=f"typology={case.get('typology')}",
    )
    return explanation


# ── model explanation (public) ───────────────────────────────────────────────

@router.get("/model")
def explain_model() -> dict:
    return explanation_service.explain_model()
