"""Analyst feedback loop + calibration dataset builder.

Turns human case outcomes into a SAFE, append-only calibration dataset: each
closed case yields one bucketed feedback record linking the analyst's verdict
to the shadow model's (bucketed) risk tiers — so Naseej can, over time, build a
labeled dataset to *eventually* calibrate the candidate, without ever storing
PII, raw transactions, raw identifiers, or raw feature values.

Storage: append-only JSONL at NASEEJ_FEEDBACK_LABELS_PATH. Reads are
node-scoped. Duplicate feedback for a case appends a NEW snapshot; aggregation
takes the latest snapshot per case_id (so a case is never double-counted).

Honesty: this builds the dataset for calibration — it does NOT calibrate the
model, deploy it, or claim production readiness. Calibration metrics are only
computed once a minimum label count exists, and are clearly labelled prototype.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from ..core import config
from . import pii_guard, shadow_monitoring_service

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# Closed case status → final calibration label. Non-closed statuses are
# "unresolved" and the route refuses to persist a final label for them.
_STATUS_TO_LABEL = {
    "closed_confirmed": "confirmed_fraud",
    "closed_false_positive": "false_positive",
    "closed_no_action": "no_action",
}
FINAL_LABELS = frozenset(_STATUS_TO_LABEL.values())
_CLOSED_STATUSES = frozenset(_STATUS_TO_LABEL)

# Candidate "alerts" at tiers at/above medium (balanced-threshold semantics).
_ALERT_TIERS = frozenset({"medium", "high", "critical"})


def feedback_label_for(status: str) -> str:
    """Map any case status to a feedback label. Non-closed → 'unresolved'."""
    return _STATUS_TO_LABEL.get(status, "unresolved")


def is_closed(status: str) -> bool:
    return status in _CLOSED_STATUSES


def min_labels() -> int:
    """Minimum labeled records before any calibration metric is computed."""
    try:
        return max(1, int(os.environ.get("NASEEJ_CALIBRATION_MIN_LABELS", "30")))
    except ValueError:
        return 30


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── record construction ──────────────────────────────────────────────────────

def _last_decision(case: dict[str, Any]) -> str | None:
    hist = case.get("decision_history") or []
    return hist[-1].get("decision") if hist else None


def build_feedback(case: dict[str, Any], node_id: str, *,
                   linked_observation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a bucketed, PII-safe feedback record from a (closed) case.

    Only safe references are stored: case_id, pattern_id, audit-style ids, and
    bucketed risk tiers from the linked shadow observation. No raw transaction
    ids, account/bank ids, amounts, or feature values.
    """
    obs = linked_observation or {}
    return {
        "feedback_id": str(uuid.uuid4()),
        "case_id": case.get("case_id"),
        "node_id": node_id,
        "final_case_status": case.get("status"),
        "analyst_decision": _last_decision(case),
        "false_positive_flag": bool(case.get("false_positive_flag", False)),
        "linked_pattern_id": case.get("pattern_id"),
        "linked_shadow_observation_id": obs.get("shadow_observation_id"),
        # Bucketed tiers come from the linked shadow observation (already coarse).
        "candidate_risk_tier_bucket": obs.get("candidate_risk_tier"),
        "baseline_risk_tier_bucket": obs.get("baseline_risk_tier"),
        "agreement_with_baseline": obs.get("agreement_with_baseline"),
        "feedback_label": feedback_label_for(case.get("status", "")),
        "created_at": _now(),
        "pii_safe": True,
    }


def record(case: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    """Append one feedback snapshot for a closed case. Best-effort write;
    returns the record, or None if the PII guard blocks it (defense in depth)."""
    linked = shadow_monitoring_service.latest_observation_for(node_id, case.get("pattern_id"))
    rec = build_feedback(case, node_id, linked_observation=linked)
    # Server-/case-generated UUID & ref fields are format-pinned: exempt them
    # from CONTENT rules (they can contain digit runs) but keep key-name rules.
    violations = pii_guard.find_pii(rec, extra_exempt_paths={
        "$.feedback_id", "$.case_id", "$.linked_pattern_id",
        "$.linked_shadow_observation_id", "$.created_at",
    })
    if violations:
        logger.error("Feedback record blocked by PII guard (%s) — not writing.", violations[:3])
        return None
    path = config.feedback_labels_path()
    try:
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n")
    except OSError as exc:  # storage is best-effort
        logger.warning("Feedback append failed: %s", exc)
        return None
    return rec


def _load(node_id: str | None = None) -> list[dict[str, Any]]:
    path = config.feedback_labels_path()
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if node_id is None or rec.get("node_id") == node_id:
                    out.append(rec)
    except FileNotFoundError:
        return []
    return out


def _latest_per_case(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe append-only snapshots: the last record per case_id wins."""
    by_case: dict[str, dict[str, Any]] = {}
    for r in records:
        cid = r.get("case_id")
        if cid:
            by_case[cid] = r
    return list(by_case.values())


def reset() -> None:
    """Test hook: delete the feedback file for the active path."""
    path = config.feedback_labels_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


# ── aggregate summary (node-scoped) ──────────────────────────────────────────

def summary(node_id: str | None = None) -> dict[str, Any]:
    """Aggregate feedback counts (latest-per-case). No raw rows exposed."""
    recs = _latest_per_case(_load(node_id))
    labels = Counter(r.get("feedback_label") for r in recs)
    labeled = sum(labels[l] for l in FINAL_LABELS)
    return {
        "source": "live",
        "report": "feedback_summary",
        "node_id": node_id,
        "total_feedback_records": len(recs),
        "labeled_count": labeled,
        "unresolved_count": labels.get("unresolved", 0),
        "confirmed_fraud_count": labels.get("confirmed_fraud", 0),
        "false_positive_count": labels.get("false_positive", 0),
        "no_action_count": labels.get("no_action", 0),
        "shadow_only": True,
        "pii_safe": True,
        "note": "Aggregate, node-scoped feedback counts. No raw cases, transactions, or feature values.",
    }


# ── calibration dataset summary (node-scoped) ────────────────────────────────

def _precision_proxy(recs: list[dict[str, Any]], tier_key: str) -> float | None:
    """Among records where this model 'alerted' (tier >= medium), the fraction
    confirmed_fraud — a PROXY for precision, not a calibrated metric."""
    alerted = [r for r in recs if (r.get(tier_key) or "") in _ALERT_TIERS
               and r.get("feedback_label") in FINAL_LABELS]
    if not alerted:
        return None
    hits = sum(1 for r in alerted if r.get("feedback_label") == "confirmed_fraud")
    return round(hits / len(alerted), 4)


def _tier_vs_outcome(recs: list[dict[str, Any]], tier_key: str) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in recs:
        if r.get("feedback_label") not in FINAL_LABELS:
            continue
        tier = r.get(tier_key) or "unknown"
        matrix[tier][r["feedback_label"]] += 1
    return {k: dict(v) for k, v in matrix.items()}


def calibration_dataset(node_id: str | None = None) -> dict[str, Any]:
    """Safe calibration-dataset summary. Computes prototype proxies only when
    the minimum label threshold is met; otherwise says so plainly."""
    recs = _latest_per_case(_load(node_id))
    labeled = [r for r in recs if r.get("feedback_label") in FINAL_LABELS]
    threshold = min_labels()
    met = len(labeled) >= threshold

    out: dict[str, Any] = {
        "source": "live",
        "report": "candidate_calibration_dataset",
        "node_id": node_id,
        "total_feedback_records": len(recs),
        "labeled_count": len(labeled),
        "unresolved_count": sum(1 for r in recs if r.get("feedback_label") == "unresolved"),
        "confirmed_fraud_count": sum(1 for r in labeled if r["feedback_label"] == "confirmed_fraud"),
        "false_positive_count": sum(1 for r in labeled if r["feedback_label"] == "false_positive"),
        "no_action_count": sum(1 for r in labeled if r["feedback_label"] == "no_action"),
        "minimum_label_threshold": threshold,
        "minimum_label_threshold_met": met,
        "candidate_risk_tier_vs_outcome": _tier_vs_outcome(recs, "candidate_risk_tier_bucket"),
        "baseline_risk_tier_vs_outcome": _tier_vs_outcome(recs, "baseline_risk_tier_bucket"),
        "calibrated_for_production": False,
        "deployment_recommended": False,
        "shadow_only": True,
        "pii_safe": True,
        "note": ("CALIBRATION DATASET — NOT PRODUCTION CALIBRATION. Built from analyst case outcomes; "
                 "labels are sparse synthetic-benchmark outcomes. Proxies are prototype only."),
    }

    if not met:
        out["status"] = "insufficient_labels"
        out["message"] = (f"insufficient labels for calibration "
                          f"({len(labeled)}/{threshold}); proxies not computed")
        out["candidate_precision_proxy"] = None
        out["baseline_precision_proxy"] = None
        out["disagreement_outcome_breakdown"] = {}
        return out

    # Enough labels → prototype proxies (clearly labelled, not production ECE/Brier).
    disagree = [r for r in labeled if r.get("agreement_with_baseline") == "disagree"]
    out["status"] = "prototype_ready"
    out["candidate_precision_proxy"] = _precision_proxy(recs, "candidate_risk_tier_bucket")
    out["baseline_precision_proxy"] = _precision_proxy(recs, "baseline_risk_tier_bucket")
    out["false_positive_rate_proxy"] = round(out["false_positive_count"] / len(labeled), 4)
    out["disagreement_outcome_breakdown"] = dict(
        Counter(r.get("feedback_label") for r in disagree))
    out["candidate_vs_baseline_outcome_agreement"] = dict(
        Counter(r.get("agreement_with_baseline") for r in labeled if r.get("agreement_with_baseline")))
    out["metrics_note"] = ("Prototype precision/FP-rate PROXIES from bucketed risk tiers and analyst "
                           "outcomes — NOT production-grade ECE/Brier (no real probabilities/labels).")
    return out


def calibration_status() -> dict[str, Any]:
    """Public-safe overall status: enum + threshold only, no per-node counts."""
    recs = _latest_per_case(_load(None))
    labeled = sum(1 for r in recs if r.get("feedback_label") in FINAL_LABELS)
    threshold = min_labels()
    if not recs:
        status = "unavailable"
    elif labeled >= threshold:
        status = "prototype_ready"
    else:
        status = "insufficient_labels"
    return {
        "source": "live",
        "report": "candidate_calibration_status",
        "calibration_status": status,
        "minimum_label_threshold": threshold,
        "calibrated_for_production": False,
        "deployment_recommended": False,
        "shadow_only": True,
        "pii_safe": True,
        "note": ("Overall calibration status (enum + threshold only — no per-node counts exposed). "
                 "CALIBRATION DATASET — NOT PRODUCTION CALIBRATION; candidate is not deployed."),
    }
