"""Shadow monitoring — bucketed observation store + aggregation + drift.

Turns live shadow-scoring results into SAFE aggregate monitoring evidence:
baseline-vs-candidate agreement, score-distribution buckets, alert-rate impact,
threshold behaviour, and prototype drift signals — **without** storing raw
transactions, raw identifiers, or raw feature values.

What is stored (per observation, JSONL at NASEEJ_SHADOW_OBSERVATIONS_PATH):
    timestamp, node_id, candidate_model_name,
    baseline_score_bucket, candidate_score_bucket, score_delta_bucket,
    baseline_risk_tier, candidate_risk_tier, agreement_with_baseline,
    threshold_mode, candidate_action, baseline_action,
    feature_vector_status, shadow_only=true, pii_safe=true

What is NEVER stored: raw transaction payloads, account/bank ids, names,
IBANs, phones, emails, national ids, or exact feature/score values. Scores are
coarse buckets only. A PII guard double-checks every record before it is
written (defense in depth).

Monitoring is aggregate and node-scoped: a bank node sees only its own
observations. This is prototype monitoring — NOT production drift monitoring,
NOT calibration, NOT a deployment signal.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core import config
from . import pii_guard

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# Minimum observations in a window before drift is meaningful at all.
_DRIFT_MIN_OBS = 8
# Absolute-rate jump that flips a prototype drift signal to "watch".
_DRIFT_RATE_JUMP = 0.20
_HIGH_MISSING_RATE = 0.50
_HIGH_DISAGREEMENT_RATE = 0.50

_NO_ALERT_ACTION = "no_alert (shadow)"
_BASELINE_ALERT_ACTIONS = frozenset({"suspicious", "block"})


# ── bucketers (coarse — never raw values) ────────────────────────────────────

def _score_bucket(s: Any) -> str:
    if s is None:
        return "none"
    try:
        v = float(s)
    except (TypeError, ValueError):
        return "none"
    if v < 0.01:
        return "lt_0.01"
    if v < 0.05:
        return "0.01_0.05"
    if v < 0.10:
        return "0.05_0.10"
    if v < 0.25:
        return "0.10_0.25"
    if v < 0.50:
        return "0.25_0.50"
    return "0.50_1.00"


def _delta_bucket(d: Any) -> str:
    if d is None:
        return "none"
    try:
        v = float(d)
    except (TypeError, ValueError):
        return "none"
    a = abs(v)
    if a < 0.01:
        return "approx_equal"
    if v > 0:
        return "candidate_higher" if a < 0.10 else "candidate_much_higher"
    return "candidate_lower" if a < 0.10 else "candidate_much_lower"


_HIGHER = frozenset({"candidate_higher", "candidate_much_higher"})
_LOWER = frozenset({"candidate_lower", "candidate_much_lower"})


# ── observation construction + storage ───────────────────────────────────────

def observation_from_result(
    node_id: str, result: dict[str, Any], *,
    audit_ref: str | None = None, pattern_id: str | None = None,
) -> dict[str, Any]:
    """Build the bucketed, PII-safe observation from a score_shadow result.

    Reads only categorical/bucketable fields; raw scores become buckets. Each
    observation carries a generated ``shadow_observation_id`` and may OPTIONALLY
    carry ``audit_ref`` and ``pattern_id`` so a case opened later from the same
    pattern can be linked to it (analyst feedback loop). ``case_id`` is always
    None at write time — observations precede cases; the link is recorded on the
    feedback record, not by rewriting the (append-only) observation.
    """
    return {
        "shadow_observation_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "node_id": node_id,
        "candidate_model_name": result.get("candidate_model_name"),
        "baseline_score_bucket": _score_bucket(result.get("baseline_score")),
        "candidate_score_bucket": _score_bucket(result.get("candidate_score")),
        "score_delta_bucket": _delta_bucket(result.get("score_delta")),
        "baseline_risk_tier": result.get("baseline_risk_tier"),
        "candidate_risk_tier": result.get("candidate_risk_tier"),
        "agreement_with_baseline": result.get("agreement_with_baseline", "unknown"),
        "threshold_mode": result.get("candidate_threshold_mode"),
        "candidate_action": result.get("candidate_recommended_action"),
        "baseline_action": result.get("baseline_action"),
        "feature_vector_status": result.get("feature_vector_status"),
        "audit_ref": audit_ref,
        "pattern_id": pattern_id,
        "case_id": None,
        "shadow_only": True,
        "pii_safe": True,
    }


def record(node_id: str, result: dict[str, Any], *,
           audit_ref: str | None = None, pattern_id: str | None = None) -> dict[str, Any] | None:
    """Append one bucketed observation. Best-effort: never raises into the
    request path. Returns the written observation (or None on guard failure)."""
    obs = observation_from_result(node_id, result, audit_ref=audit_ref, pattern_id=pattern_id)
    # Defense in depth: refuse to write anything the PII guard flags. The
    # server-generated UUID/SHA-ref id fields (and the node-private pattern_id
    # link) are format-pinned, so they are exempt from CONTENT rules only —
    # key-name rules still apply, and every bucket/enum field is still scanned.
    violations = pii_guard.find_pii(obs, extra_exempt_paths={
        "$.shadow_observation_id", "$.audit_ref", "$.pattern_id",
        "$.case_id", "$.timestamp",
    })
    if violations:
        logger.error("Shadow observation blocked by PII guard (%s) — not writing.", violations[:3])
        return None
    path = config.shadow_observations_path()
    try:
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(obs, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n")
    except OSError as exc:  # storage is best-effort; scoring must not break
        logger.warning("Shadow observation append failed: %s", exc)
        return None
    return obs


def _load(node_id: str | None = None) -> list[dict[str, Any]]:
    path = config.shadow_observations_path()
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obs = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if node_id is None or obs.get("node_id") == node_id:
                    out.append(obs)
    except FileNotFoundError:
        return []
    return out


def latest_observation_for(node_id: str, pattern_id: str | None) -> dict[str, Any] | None:
    """Most recent observation for (node_id, pattern_id), used to link a case's
    feedback to the shadow observation that scored its transaction. Returns None
    when pattern_id is absent or no observation carried it."""
    if not pattern_id:
        return None
    matches = [o for o in _load(node_id) if o.get("pattern_id") == pattern_id]
    return matches[-1] if matches else None


def reset() -> None:
    """Test hook: delete the observation file for the active path."""
    path = config.shadow_observations_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


# ── aggregation (pure over an observation list) ──────────────────────────────

def _rate(numer: int, denom: int) -> float | None:
    return round(numer / denom, 4) if denom else None


def compute_aggregate(obs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics over a list of observations. Pure (no time/IO)."""
    total = len(obs)
    scored = [o for o in obs if o.get("feature_vector_status") == "complete"]
    unavailable = [o for o in obs if o.get("feature_vector_status") == "candidate_unavailable"]
    missing = [o for o in obs if o.get("feature_vector_status") == "missing_feature"]
    scored_count = len(scored)

    agree = sum(1 for o in scored if o.get("agreement_with_baseline") == "agree")
    disagree = sum(1 for o in scored if o.get("agreement_with_baseline") == "disagree")
    agree_denom = agree + disagree

    higher = sum(1 for o in scored if o.get("score_delta_bucket") in _HIGHER)
    lower = sum(1 for o in scored if o.get("score_delta_bucket") in _LOWER)

    cand_alerts = sum(1 for o in scored
                      if o.get("candidate_action") not in (None, _NO_ALERT_ACTION))
    base_known = [o for o in scored if o.get("baseline_action") is not None]
    base_alerts = sum(1 for o in base_known if o.get("baseline_action") in _BASELINE_ALERT_ACTIONS)

    candidate_alert_rate = _rate(cand_alerts, scored_count)
    baseline_alert_rate = _rate(base_alerts, len(base_known)) if base_known else None
    alert_delta = (round(candidate_alert_rate - baseline_alert_rate, 4)
                   if candidate_alert_rate is not None and baseline_alert_rate is not None else None)

    transition: dict[str, dict[str, int]] = {}
    for o in scored:
        b = o.get("baseline_risk_tier") or "unknown"
        c = o.get("candidate_risk_tier") or "unknown"
        transition.setdefault(b, {})
        transition[b][c] = transition[b].get(c, 0) + 1

    return {
        "total_shadow_requests": total,
        "scored_count": scored_count,
        "unavailable_count": len(unavailable),
        "missing_feature_count": len(missing),
        "agreement_rate": _rate(agree, agree_denom),
        "disagreement_rate": _rate(disagree, agree_denom),
        "candidate_higher_risk_rate": _rate(higher, scored_count),
        "candidate_lower_risk_rate": _rate(lower, scored_count),
        "candidate_alert_rate": candidate_alert_rate,
        "baseline_alert_rate": baseline_alert_rate,
        "alert_delta": alert_delta,
        "missing_feature_rate": _rate(len(missing), total),
        "score_delta_distribution_buckets": dict(Counter(o.get("score_delta_bucket", "none") for o in scored)),
        "risk_tier_transition_matrix": transition,
        "threshold_mode_distribution": dict(Counter(
            o.get("threshold_mode") for o in scored if o.get("threshold_mode"))),
        "feature_vector_status_distribution": dict(Counter(
            o.get("feature_vector_status", "unknown") for o in obs)),
    }


# ── drift (pure over two aggregates) ─────────────────────────────────────────

def compute_drift(recent: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Prototype drift signal comparing a recent aggregate to a baseline one.

    Returns {signal: normal|watch|unavailable, reasons: [...], note}. This is a
    PROTOTYPE signal on bucketed synthetic data — it is NOT statistical
    production monitoring and requires real-data validation.
    """
    note = ("Prototype drift signal on bucketed synthetic observations — "
            "NOT statistical production monitoring; requires real-data validation.")
    if recent.get("total_shadow_requests", 0) < _DRIFT_MIN_OBS:
        return {"signal": "unavailable", "reasons": ["insufficient observations in window"], "note": note}

    reasons: list[str] = []

    def _jump(metric: str) -> None:
        r, b = recent.get(metric), baseline.get(metric)
        if r is not None and b is not None and (r - b) >= _DRIFT_RATE_JUMP:
            reasons.append(f"{metric} rose by >= {_DRIFT_RATE_JUMP:.2f} vs baseline ({b} → {r})")

    # Missing-feature rate spike (absolute or vs baseline).
    mr = recent.get("missing_feature_rate")
    if mr is not None and mr >= _HIGH_MISSING_RATE:
        reasons.append(f"missing_feature_rate high ({mr})")
    _jump("missing_feature_rate")

    # Disagreement-rate spike.
    dr = recent.get("disagreement_rate")
    if dr is not None and dr >= _HIGH_DISAGREEMENT_RATE:
        reasons.append(f"disagreement_rate high ({dr})")
    _jump("disagreement_rate")

    # Alert-rate shift (either direction is worth a look).
    rc, bc = recent.get("candidate_alert_rate"), baseline.get("candidate_alert_rate")
    if rc is not None and bc is not None and abs(rc - bc) >= _DRIFT_RATE_JUMP:
        reasons.append(f"candidate_alert_rate shifted by >= {_DRIFT_RATE_JUMP:.2f} ({bc} → {rc})")

    return {"signal": "watch" if reasons else "normal", "reasons": reasons, "note": note}


# ── time-windowed node-scoped monitoring ─────────────────────────────────────

def _within(obs: dict[str, Any], cutoff: datetime | None) -> bool:
    if cutoff is None:
        return True
    try:
        ts = datetime.strptime(obs["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return False
    return ts >= cutoff


def monitoring(node_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Node-scoped aggregate monitoring across 1h / 24h / all windows + drift."""
    now = now or datetime.now(timezone.utc)
    obs = _load(node_id)
    if not obs:
        return empty_monitoring(node_id)
    last_1h = [o for o in obs if _within(o, now - timedelta(hours=1))]
    last_24h = [o for o in obs if _within(o, now - timedelta(hours=24))]

    agg_1h = compute_aggregate(last_1h)
    agg_24h = compute_aggregate(last_24h)
    agg_all = compute_aggregate(obs)

    # Recent (24h) vs all-history baseline; the 1h window is shown for context.
    drift = compute_drift(agg_24h, agg_all)

    return {
        "source": "live",
        "report": "candidate_shadow_monitoring",
        "node_id": node_id,
        "shadow_only": True,
        "deployment_decision": "none — prototype monitoring only",
        "windows": {"last_1h": agg_1h, "last_24h": agg_24h, "all": agg_all},
        "drift": drift,
        "note": ("Aggregate, node-scoped, bucketed monitoring of shadow scores. No raw transactions, "
                 "identifiers, or feature values are stored or exposed. Not a deployment signal."),
        "pii_safe": True,
    }


def empty_monitoring(node_id: str) -> dict[str, Any]:
    """Safe empty state when no observations exist for the node."""
    empty = compute_aggregate([])
    return {
        "source": "live",
        "report": "candidate_shadow_monitoring",
        "node_id": node_id,
        "shadow_only": True,
        "deployment_decision": "none — prototype monitoring only",
        "windows": {"last_1h": empty, "last_24h": empty, "all": empty},
        "drift": {"signal": "unavailable", "reasons": ["no observations yet"],
                  "note": "Prototype drift signal; requires real-data validation."},
        "note": "No shadow observations recorded for this node yet.",
        "pii_safe": True,
    }
