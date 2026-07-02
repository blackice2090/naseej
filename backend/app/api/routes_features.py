"""Feature-store endpoints: ingestion, lookup, contextual scoring.

Gate order on every write, mirroring the pattern registry:
auth (node key) → closed Pydantic schema → source-node match → transaction
PII guard → store update → audit record. All denials are generic 403s with
the static audited reason; rejected payloads are never echoed or logged.

Node isolation: every store read/write below is keyed on the *authenticated*
node id (ctx.node_id), never on anything from the request body or path — a
node cannot name another node's partition even on a tampered request.

Contextual scoring honesty: /score-with-context layers a deterministic,
explainable rule adjustment over the existing baseline model score. The
model has NOT been retrained on the new features; the response says so
explicitly (``model_retrained_on_context: false``) and the rule weights are
visible in this file. No claim of production readiness.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import AuthContext, require_context
from ..core.schemas import (
    AccountFeaturesOut,
    ContextScoreIn,
    ContextScoreOut,
    FeatureIngestOut,
    FeatureTransactionIn,
    TransactionIn,
)
from ..services import (
    audit_service,
    feature_catalogue,
    feature_store_service,
    model_service,
    pii_guard,
    privacy_service,
    scoring_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/features", tags=["features"])

_GENERIC_403 = "Not authorized for this resource or action."

# Path-parameter handle shape — checked before any store lookup so an
# IBAN/phone pasted into the URL is denied without touching state.
_ACCOUNT_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-\.]{1,63}$")


def _reject(ctx: AuthContext, endpoint: str, action: str, status: int,
            reasons: list[str], decision: str = "rejected") -> HTTPException:
    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action,
        decision=decision, reason="; ".join(reasons[:5]),
    )
    if status == 403:
        return HTTPException(status_code=403, detail=_GENERIC_403)
    return HTTPException(status_code=status, detail={"accepted": False, "reasons": reasons})


# ── ingestion ───────────────────────────────────────────────────────────────

@router.post("/ingest-transaction", response_model=FeatureIngestOut, status_code=201)
def ingest_transaction(
    tx: FeatureTransactionIn,
    ctx: AuthContext = Depends(require_context),
) -> FeatureIngestOut:
    endpoint, action = "/api/features/ingest-transaction", "feature_ingest"

    # Gate 1 — only bank nodes feed their own store (a read-only regulator
    # node observes, it does not inject local history).
    if ctx.node_type != "bank":
        raise _reject(ctx, endpoint, action, 403,
                      ["node type may not ingest transactions"], decision="denied")

    # Gate 2 — the claimed source node must be the authenticated node.
    if tx.source_node_id != ctx.node_id:
        raise _reject(ctx, endpoint, action, 403,
                      ["source_node_id does not match authenticated node"],
                      decision="denied")

    # Gate 3 — transaction PII guard (value shapes; the schema already
    # rejected unknown fields).
    violations = pii_guard.find_transaction_pii(tx.model_dump())
    if violations:
        raise _reject(ctx, endpoint, action, 422, violations)

    try:
        stats = feature_store_service.ingest(
            ctx.node_id,
            transaction_id=tx.transaction_id, timestamp=tx.timestamp,
            from_bank=str(tx.from_bank), from_account=tx.from_account,
            to_bank=str(tx.to_bank), to_account=tx.to_account, amount=tx.amount,
        )
    except ValueError:
        raise _reject(ctx, endpoint, action, 422, ["unparseable timestamp"])

    # Metadata-only audit record — the transaction itself is never logged.
    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action,
        decision="accepted",
        reason=f"events_in_window={stats['events_in_window']}",
    )
    return FeatureIngestOut(
        transaction_id=tx.transaction_id,
        events_in_window=stats["events_in_window"],
        accounts_tracked=stats["accounts_tracked"],
    )


# ── lookup ──────────────────────────────────────────────────────────────────

@router.get("/account/{account_id}", response_model=AccountFeaturesOut)
def account_features(
    account_id: str,
    ctx: AuthContext = Depends(require_context),
) -> AccountFeaturesOut:
    endpoint, action = "/api/features/account/{account_id}", "feature_lookup"

    if not _ACCOUNT_PATH_RE.match(account_id):
        raise _reject(ctx, endpoint, action, 403,
                      ["account id fails handle shape rule"], decision="denied")

    # One generic denial for both "another node's account" and "account that
    # does not exist" — a cross-node probe learns nothing from the status.
    feats = feature_store_service.account_features(ctx.node_id, account_id)
    if feats is None:
        raise _reject(ctx, endpoint, action, 403,
                      ["account not observed locally by this node"], decision="denied")

    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action, decision="served",
    )
    return AccountFeaturesOut(account_id=account_id, features=feats)


# ── contextual scoring ──────────────────────────────────────────────────────

# Transparent rule layer over the baseline score. Each rule: (description
# template, weight). Weights are deliberately modest and capped — this is
# an explainable adjustment, not a trained model.
_ADJUSTMENT_CAP = 0.45
_FINAL_CAP = 0.99


def _contextual_rules(feats: dict[str, Any], tx: ContextScoreIn) -> list[tuple[str, float]]:
    hits: list[tuple[str, float]] = []
    in_1h = feats.get("target_in_degree_1h", 0)
    if in_1h >= 4:
        hits.append((f"{in_1h} inbound transfers to the source account within the last hour", 0.15))
    if feats.get("sweep_after_fan_in_flag"):
        kind = "Cross-bank" if feats.get("tx_is_cross_bank") else "Internal"
        hits.append((f"{kind} sweep follows rapid fan-in (outflow ≥ 60% of recent inflow)", 0.20))
    if feats.get("new_beneficiary_flag") and (
        feats.get("rolling_amount_ratio", 0) >= 3 or tx.amount > 10_000
    ):
        hits.append((f"New beneficiary bucket ({feats.get('beneficiary_age_bucket')}) "
                     "for an unusually large transfer", 0.10))
    if feats.get("tx_is_cross_bank") and feats.get("cross_bank_transfer_count_24h", 0) >= 2:
        hits.append((f"Cross-bank velocity spike: "
                     f"{feats['cross_bank_transfer_count_24h']} cross-bank transfers in 24h", 0.10))
    if feats.get("account_velocity_zscore", 0) > 2:
        hits.append((f"Outbound velocity z-score {feats['account_velocity_zscore']:.1f} "
                     "vs the account's own 24h baseline", 0.10))
    return hits


@router.post("/score-with-context", response_model=ContextScoreOut)
def score_with_context(
    body: ContextScoreIn,
    ctx: AuthContext = Depends(require_context),
) -> ContextScoreOut:
    endpoint, action = "/api/features/score-with-context", "score_with_context"

    if body.source_node_id is not None and body.source_node_id != ctx.node_id:
        raise _reject(ctx, endpoint, action, 403,
                      ["source_node_id does not match authenticated node"],
                      decision="denied")

    # The guard tolerates missing optional keys (transaction_id, timestamp).
    violations = pii_guard.find_transaction_pii(body.model_dump(exclude_none=True))
    if violations:
        raise _reject(ctx, endpoint, action, 422, violations)

    # Base score: the existing single-transaction model path, unchanged.
    base = scoring_service.score(TransactionIn(
        timestamp=body.timestamp, from_bank=body.from_bank,
        from_account=body.from_account, to_bank=body.to_bank,
        to_account=body.to_account, amount=body.amount,
        currency=body.currency, payment_format=body.payment_format,
    ))

    feats = feature_store_service.transaction_context(
        ctx.node_id,
        from_account=body.from_account, to_account=body.to_account,
        amount=body.amount, timestamp=body.timestamp,
        cross_bank=str(body.from_bank) != str(body.to_bank),
    )

    explanation: list[str] = []
    adjustment = 0.0
    if feats.get("history_available"):
        rule_hits = _contextual_rules(feats, body)
        # Rounded before use so base + adjustment = final holds exactly.
        adjustment = round(min(_ADJUSTMENT_CAP, sum(w for _, w in rule_hits)), 4)
        explanation = [desc for desc, _ in rule_hits]
        if not rule_hits:
            explanation = ["Local window history shows no velocity or counterparty anomaly"]
    else:
        explanation = ["No local history for the source account — "
                       "contextual adjustment unavailable, base model score only"]

    explanation.append(
        "Adjustment is a deterministic rule layer over the baseline model; "
        "the model has not been retrained on context features"
    )

    final = min(_FINAL_CAP, base.risk_score + adjustment)

    # Context can only escalate the baseline verdict, never soften it. The
    # rule layer is not a calibrated probability, so escalating to "block"
    # needs a clearly high combined score (0.5), not the tiny PR-threshold.
    threshold = model_service.get_threshold() or 0.5
    context_verdict = ("block" if final >= 0.5
                       else "suspicious" if final >= threshold else "benign")
    rank = {"benign": 0, "suspicious": 1, "block": 2}
    prediction = max(base.prediction, context_verdict, key=lambda v: rank[v])

    # Strip internal/bookkeeping keys from the echoed features; everything
    # left is aggregate or bucketed (catalogue privacy levels).
    safe_feats = {k: v for k, v in feats.items() if k != "history_available"}

    pattern_hash = None
    if adjustment > 0:
        pattern_hash = privacy_service.generate_pattern_hash({
            "pattern_type": "contextual_velocity",
            "fan_in_normalized_1h": feats.get("fan_in_normalized_1h", 0.0),
            "sweep_after_fan_in_flag": feats.get("sweep_after_fan_in_flag", 0),
            "cross_bank": feats.get("tx_is_cross_bank", False),
        })

    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action,
        decision=prediction,
        risk_tier="high" if prediction == "block"
        else "medium" if prediction == "suspicious" else "low",
        pattern_hash=pattern_hash,
        reason=f"base={base.risk_score:.4f} adjustment={adjustment:.2f} "
               f"history={bool(feats.get('history_available'))}",
    )

    return ContextScoreOut(
        base_model_score=round(base.risk_score, 6),
        contextual_risk_adjustment=round(adjustment, 4),
        final_contextual_score=round(final, 6),
        prediction=prediction,
        explanation=explanation,
        context_features=safe_feats,
        base_score_source=base.source,
        pattern_hash=pattern_hash,
    )


# ── metadata ────────────────────────────────────────────────────────────────

@router.get("/status")
def feature_store_status(ctx: AuthContext = Depends(require_context)) -> dict:
    """Node-scoped store status — a node sees only its own partition."""
    return {
        "feature_store": "active",
        "scope": "node_local",
        **feature_store_service.node_status(ctx.node_id),
    }


@router.get("/catalogue")
def catalogue(ctx: AuthContext = Depends(require_context)) -> dict:
    return {
        "features": feature_catalogue.as_dicts(),
        "count": len(feature_catalogue.CATALOGUE),
        "note": "Node-local features; values never cross the bank boundary.",
    }
