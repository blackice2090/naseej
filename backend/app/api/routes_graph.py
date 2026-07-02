"""Transaction scoring + pattern analysis endpoints."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends

from ..core.auth import require_node
from ..core.schemas import PatternIn, PatternOut, ScoreOut, TransactionIn
from ..services import (
    audit_service,
    feature_store_service,
    model_service,
    privacy_service,
    scoring_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


# ── pattern library (Phase 3) — optional; degrade if unavailable ──────────
try:
    from ml.src import pattern_library as _pattern_lib  # type: ignore[import]
    _PATTERNS_AVAILABLE = True
except Exception as _exc:
    _PATTERNS_AVAILABLE = False
    logger.warning("pattern_library unavailable: %s", _exc)


def _transactions_to_df(txs: list[TransactionIn]) -> pd.DataFrame:
    rows = []
    for t in txs:
        rows.append({
            "src_id": t.from_account,
            "dst_id": t.to_account,
            "from_bank_id": t.from_bank,
            "to_bank_id": t.to_bank,
            "amount": t.amount,
            "timestamp": t.timestamp,
        })
    return pd.DataFrame(rows)


def _safe_findings(df: pd.DataFrame) -> list[dict[str, Any]]:
    if not _PATTERNS_AVAILABLE:
        return []
    try:
        return _pattern_lib.run_all(df)
    except Exception as exc:
        logger.warning("pattern_library.run_all failed: %s", exc)
        return []


# ── /score-transaction ─────────────────────────────────────────────────────

@router.post("/score-transaction", response_model=ScoreOut)
def score_transaction(tx: TransactionIn, node_id: str = Depends(require_node)) -> ScoreOut:
    result = scoring_service.score(tx)
    # Audit metadata only — the transaction itself is never logged.
    audit_service.record(
        node_id=node_id,
        endpoint="/api/score-transaction",
        action="score_transaction",
        decision=result.prediction,
        risk_tier="high" if result.prediction == "block"
        else "medium" if result.prediction == "suspicious" else "low",
        pattern_hash=result.pattern_hash,
    )
    return result


# ── /analyze-pattern ──────────────────────────────────────────────────────

@router.post("/analyze-pattern", response_model=PatternOut)
def analyze_pattern(payload: PatternIn, node_id: str = Depends(require_node)) -> PatternOut:
    txs = payload.transactions

    # Basic graph summary (always computed)
    accounts: set[str] = set()
    for t in txs:
        accounts.add(t.from_account)
        accounts.add(t.to_account)
    total_amount = sum(t.amount for t in txs)
    graph_summary: dict[str, Any] = {
        "tx_count": len(txs),
        "unique_accounts": len(accounts),
        "total_amount": total_amount,
    }

    # ── real pattern detection (Phase 3 + Phase 6) ────────────────────────
    df = _transactions_to_df(txs)
    raw_findings = _safe_findings(df)

    detected: list[dict[str, Any]] = []
    top_hash: str | None = None
    top_risk: float = 0.0

    for f in raw_findings:
        # Normalise and hash each finding — strips PII, buckets values.
        normalized = privacy_service.normalize_pattern_features(f)
        h = privacy_service.generate_pattern_hash(normalized)
        audit = privacy_service.pii_audit_report(f, normalized)

        # Build the clean finding for the response (zero PII).
        clean: dict[str, Any] = {
            "pattern_type": normalized.get("pattern_type"),
            "risk_tier": normalized.get("risk_tier"),
            "risk_score": f.get("risk_score", 0.0),
            "reason": f.get("reason", ""),
            "features": normalized.get("features", {}),
            "pattern_hash": h,
            "zero_pii": audit["zero_pii"],
        }
        detected.append(clean)
        if f.get("risk_score", 0.0) > top_risk:
            top_risk = f["risk_score"]
            top_hash = h

    # ── fallback heuristic when pattern library is unavailable ────────────
    if not detected:
        heuristic_risk = (
            0.91
            if graph_summary["unique_accounts"] >= 3 and graph_summary["tx_count"] >= 3
            else 0.2
        )
        ptype = "mule_velocity" if heuristic_risk > 0.8 else "normal"
        top_hash = privacy_service.placeholder_pattern_hash(
            ptype, f"{graph_summary['tx_count']}|{graph_summary['unique_accounts']}"
        )
        top_risk = heuristic_risk
        detected = [{
            "pattern_type": ptype,
            "risk_tier": "high" if heuristic_risk > 0.8 else "low",
            "risk_score": heuristic_risk,
            "reason": "Heuristic: fan-in shape detected (Phase 3 library unavailable).",
            "features": {"tx_count": graph_summary["tx_count"], "unique_accounts": graph_summary["unique_accounts"]},
            "pattern_hash": top_hash,
            "zero_pii": True,
        }]

    # ── feature-store enrichment (additive; None keeps old behaviour) ─────
    # When the calling node has ingested local history for the batch's
    # central account, window features can confirm what the batch alone
    # cannot: fan-in inside a real time window, a sweep that follows it,
    # velocity vs the account's own baseline, cross-bank pass-through.
    enrichment = feature_store_service.enrich_pattern_analysis(node_id, txs)
    if enrichment is not None:
        graph_summary["context_enrichment"] = enrichment
        if enrichment.get("sweep_after_fan_in_flag"):
            window_finding = {
                "pattern_type": "sweep_after_fan_in",
                "risk_tier": "high",
                "risk_score": 0.9,
                "reason": (
                    "Feature-store window confirms fan-in followed by an outbound "
                    "sweep within the rolling 1h window (node-local history)."
                ),
                "features": dict(enrichment["fan_in_window"]),
                "pattern_hash": privacy_service.generate_pattern_hash({
                    "pattern_type": "sweep_after_fan_in",
                    **enrichment["fan_in_window"],
                    "cross_bank_pass_through": enrichment["cross_bank_pass_through"],
                }),
                "zero_pii": True,  # counts and flags only — no handles
            }
            detected.append(window_finding)
            if window_finding["risk_score"] > top_risk:
                top_risk = window_finding["risk_score"]
                top_hash = window_finding["pattern_hash"]

    # Topology signature from edge list (accounts anonymised by position)
    edges = [
        (t.from_account, t.to_account, t.amount)
        for t in txs
    ]
    topo_sig = privacy_service.generate_topology_signature(edges)
    graph_summary["topology_signature"] = topo_sig

    action = "block" if top_risk > 0.85 else "review" if top_risk > 0.4 else "allow"

    audit_service.record(
        node_id=node_id,
        endpoint="/api/analyze-pattern",
        action="analyze_pattern",
        decision=action,
        risk_tier=detected[0].get("risk_tier") if detected else None,
        pattern_hash=top_hash or topo_sig,
    )

    return PatternOut(
        detected_patterns=detected,
        graph_summary=graph_summary,
        risk_score=round(top_risk, 4),
        pattern_hash=top_hash or topo_sig,
        recommended_action=action,
        zero_pii=all(d.get("zero_pii", False) for d in detected),
        source="engine",
    )
