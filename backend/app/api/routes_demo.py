"""Demo-aggregate + cross-bank + governance-evidence endpoints.

The /api/demo/* evidence endpoints are public read-only: they expose only
aggregate/structural governance facts (no raw transactions, identifiers, or
PII) and never change scoring behaviour.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..core import config
from ..services import demo_evidence_service, demo_service, model_service

router = APIRouter(prefix="/api", tags=["demo"])


@router.get("/cross-bank/results")
def cross_bank_results() -> dict:
    data = model_service.load_json_report(config.CROSS_BANK_RESULTS_PATH)
    if data is None:
        return demo_service.fallback_cross_bank()
    data.setdefault("source", "live")
    return data


@router.get("/demo/research-summary")
def research_summary() -> dict:
    return demo_service.research_summary()


# ── demo readiness + governance evidence pack (public read-only) ──────────────

@router.get("/demo/health")
def demo_health() -> dict:
    """End-to-end demo readiness check. Always returns safely (failed probes
    become 'unavailable' checks, not errors)."""
    try:
        return demo_evidence_service.demo_health()
    except Exception:  # pragma: no cover - never break the health endpoint
        return {"source": "fallback", "report": "demo_health", "status": "unavailable",
                "checks": [], "warnings": ["health check failed to run"],
                "demo_safe": False, "production_ready": False}


@router.get("/demo/governance-evidence")
def governance_evidence() -> dict:
    try:
        return demo_evidence_service.governance_evidence()
    except Exception:  # pragma: no cover
        return {"source": "fallback", "report": "governance_evidence",
                "evidence": [], "known_limitations": [], "production_ready": False}


@router.get("/demo/judge-summary")
def judge_summary() -> dict:
    try:
        return demo_evidence_service.judge_summary()
    except Exception:  # pragma: no cover
        return {"source": "fallback", "report": "judge_summary", "production_ready": False}
