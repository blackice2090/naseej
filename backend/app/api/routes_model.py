"""Model metrics + feature importance endpoints (Phase 1 returns fallbacks).

Reports are public read-only. The one exception is the shadow-scoring endpoint
(POST /api/model/candidate/score-shadow), which requires node auth + the PII
guard because it accepts a pseudonymous transaction payload — but it is still
comparison-only and never drives a decision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core import config
from ..core.auth import AuthContext, require_context
from ..core.schemas import ShadowScoreIn
from ..services import (
    audit_service,
    candidate_service,
    feedback_service,
    model_service,
    pii_guard,
    shadow_monitoring_service,
)

router = APIRouter(prefix="/api/model", tags=["model"])

_GENERIC_403 = "Not authorized for this resource or action."


@router.get("/metrics")
def metrics() -> dict:
    data = model_service.load_json_report(config.MODEL_METRICS_PATH)
    if data is None:
        return model_service.fallback_metrics()
    data.setdefault("source", "live")
    return data


@router.get("/feature-importance")
def feature_importance() -> dict:
    data = model_service.load_json_report(config.FEATURE_IMPORTANCE_PATH)
    if data is None:
        return model_service.fallback_feature_importance()
    data.setdefault("source", "live")
    return data


# ── ML evaluation reports (read-only research artefacts, like /metrics) ────


def _evaluation_report(path, report_name: str) -> dict:
    data = model_service.load_json_report(path)
    if data is None:
        return model_service.fallback_evaluation_report(report_name)
    data.setdefault("source", "live")
    return data


@router.get("/comparison")
def model_comparison() -> dict:
    return _evaluation_report(config.MODEL_COMPARISON_PATH, "model_comparison")


@router.get("/per-typology-recall")
def per_typology_recall() -> dict:
    return _evaluation_report(config.PER_TYPOLOGY_RECALL_PATH, "per_typology_recall")


@router.get("/threshold-analysis")
def threshold_analysis() -> dict:
    return _evaluation_report(config.THRESHOLD_ANALYSIS_PATH, "threshold_analysis")


@router.get("/ablation-report")
def ablation_report() -> dict:
    return _evaluation_report(config.ABLATION_REPORT_PATH, "ablation_report")


# ── feature reconciliation artifacts (read-only; no sensitive data) ────────
# Contract/parity/manifest are bucketed/structural metadata about features —
# no raw values, no identifiers — so they are public read-only like /metrics.


@router.get("/feature-contract")
def feature_contract() -> dict:
    data = model_service.load_json_report(config.FEATURE_CONTRACT_PATH)
    if data is None:
        return model_service.fallback_feature_artifact(
            "feature_contract", "python -m ml.src.feature_contract")
    data.setdefault("source", "live")
    return data


@router.get("/feature-parity")
def feature_parity() -> dict:
    data = model_service.load_json_report(config.FEATURE_PARITY_PATH)
    if data is None:
        return model_service.fallback_feature_artifact(
            "feature_parity", "python -m ml.src.feature_parity_check")
    data.setdefault("source", "live")
    return data


@router.get("/training-feature-manifest")
def training_feature_manifest() -> dict:
    data = model_service.load_json_report(config.TRAINING_FEATURE_MANIFEST_PATH)
    if data is None:
        return model_service.fallback_feature_artifact(
            "training_feature_manifest", "python -m ml.src.feature_parity_check")
    data.setdefault("source", "live")
    return data


# ── shadow candidate model (read-only; NOT deployed; no sensitive data) ────
# These reports describe a candidate model evaluated on synthetic data and
# trained on approved parity-clean features only. The deployed model, scoring
# endpoint, and explainability endpoints are unchanged.

_CANDIDATE_HOWTO = "python -m ml.src.train_candidate_model"


def _candidate_report(path, report_name: str) -> dict:
    data = model_service.load_json_report(path)
    if data is None:
        return model_service.fallback_feature_artifact(report_name, _CANDIDATE_HOWTO)
    data.setdefault("source", "live")
    return data


@router.get("/candidate/metrics")
def candidate_metrics() -> dict:
    return _candidate_report(config.CANDIDATE_METRICS_PATH, "candidate_model_metrics")


@router.get("/candidate/comparison")
def candidate_comparison() -> dict:
    return _candidate_report(config.CANDIDATE_COMPARISON_PATH, "candidate_model_comparison")


@router.get("/candidate/thresholds")
def candidate_thresholds() -> dict:
    return _candidate_report(config.CANDIDATE_THRESHOLDS_PATH, "candidate_thresholds")


@router.get("/candidate/explainability-check")
def candidate_explainability_check() -> dict:
    return _candidate_report(config.CANDIDATE_EXPLAINABILITY_PATH, "candidate_explainability_check")


# ── live shadow scoring (node auth; comparison-only; never drives decisions) ──
# Mirrors /api/features/score-with-context's auth + PII posture. It does NOT
# create cases, block/approve, or affect /api/score-transaction.

@router.post("/candidate/score-shadow")
def candidate_score_shadow(
    body: ShadowScoreIn,
    ctx: AuthContext = Depends(require_context),
) -> dict:
    endpoint, action = "/api/model/candidate/score-shadow", "candidate_shadow_score"

    # Source-node match (same rule as score-with-context).
    if body.source_node_id is not None and body.source_node_id != ctx.node_id:
        audit_service.record(
            node_id=ctx.node_id, endpoint=endpoint, action=action, decision="rejected",
            reason="source_node_id does not match authenticated node",
        )
        raise HTTPException(status_code=403, detail=_GENERIC_403)

    # Same PII guard as score-with-context (rejects PII shapes in values). The
    # optional pattern_id is a metadata link, not a transaction field, so it is
    # excluded here; the observation write applies its own PII guard to it.
    guard_payload = body.model_dump(exclude_none=True)
    guard_payload.pop("pattern_id", None)
    violations = pii_guard.find_transaction_pii(guard_payload)
    if violations:
        audit_service.record(
            node_id=ctx.node_id, endpoint=endpoint, action=action, decision="rejected",
            reason="; ".join(violations[:5]),
        )
        raise HTTPException(status_code=422, detail={"accepted": False, "reasons": violations})

    result = candidate_service.score_shadow(ctx.node_id, body)

    # Audit metadata only — never the transaction or feature values.
    if not result["candidate_available"]:
        decision, reason = "unavailable", result.get("feature_vector_status", "candidate_unavailable")
    else:
        decision, reason = "scored", f"agreement={result.get('agreement_with_baseline')}"
    ref = audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action, decision=decision,
        risk_tier=result.get("candidate_risk_tier"), reason=reason,
    )["ref"]

    # Record a bucketed, PII-safe monitoring observation (best-effort; both
    # scored and unavailable/missing_feature). Carries the audit ref + optional
    # pattern_id so a case opened later can be linked. Never stores raw values.
    shadow_monitoring_service.record(ctx.node_id, result, audit_ref=ref, pattern_id=body.pattern_id)
    return result


# ── shadow monitoring (node-scoped aggregates) + calibration readiness ─────

@router.get("/candidate/shadow-monitoring")
def candidate_shadow_monitoring(
    node_id: str | None = None,
    ctx: AuthContext = Depends(require_context),
) -> dict:
    """Aggregate, bucketed shadow-monitoring for the caller's OWN node. A
    cross-node view requires the regulator/admin `cases:view_all` permission."""
    endpoint, action = "/api/model/candidate/shadow-monitoring", "candidate_shadow_monitoring"
    target = ctx.node_id
    if node_id and node_id != ctx.node_id:
        if not ctx.has("cases:view_all"):
            audit_service.record(
                node_id=ctx.node_id, endpoint=endpoint, action=action, decision="denied",
                reason="cross-node shadow monitoring requires view-all permission",
            )
            raise HTTPException(status_code=403, detail=_GENERIC_403)
        target = node_id
    data = shadow_monitoring_service.monitoring(target)
    audit_service.record(
        node_id=ctx.node_id, endpoint=endpoint, action=action, decision="served",
        reason=f"window=all scored={data['windows']['all']['scored_count']}",
    )
    return data


@router.get("/candidate/calibration-readiness")
def candidate_calibration_readiness() -> dict:
    """Public read-only: static calibration-readiness statement (or fallback)."""
    data = model_service.load_json_report(config.CANDIDATE_CALIBRATION_PATH)
    if data is None:
        return model_service.fallback_feature_artifact(
            "candidate_calibration_readiness", "python -m ml.src.candidate_calibration_readiness")
    data.setdefault("source", "live")
    return data


@router.get("/candidate/calibration-status")
def candidate_calibration_status() -> dict:
    """Public read-only: overall calibration status (enum + threshold only — no
    per-node counts or other sensitive data). Always degrades safely."""
    try:
        return feedback_service.calibration_status()
    except Exception:  # pragma: no cover - defensive; never expose internals
        return {
            "source": "fallback", "report": "candidate_calibration_status",
            "calibration_status": "unavailable", "calibrated_for_production": False,
            "deployment_recommended": False, "pii_safe": True,
        }
