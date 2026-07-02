"""Shadow candidate scoring — comparison-only, never deployed.

Runs the shadow candidate model (``ml/models/candidate_model.joblib``) beside
the deployed baseline for comparison. It builds the candidate's 15 approved,
parity-clean features from the ONLINE feature path (transaction payload +
node-local windows), scores them, and reports the candidate score next to the
baseline score. It NEVER influences a decision, creates a case, or touches the
deployed model / ``/api/score-transaction``.

Hard rules enforced here:
- The candidate bundle is OPTIONAL. Missing → safe "unavailable" response.
- Only the 15 approved features are built. Identity encodings
  (account/bank), all-time cumulatives, account-pair features, and serve-only
  online features are HARD-BLOCKED (assertion + bundle-column allow-list).
- No raw account/transaction ids, IBANs, names, or raw feature values leave
  this module; the response carries scores, tiers, and bucketed status only.
- Point-in-time only: windowed features come from the node's window state as
  of its latest observed event; no future transaction is used.
"""

from __future__ import annotations

import logging
from typing import Any

from ..core import config
from ..core.schemas import TransactionIn
from . import feature_store_service, model_service, scoring_service

logger = logging.getLogger(__name__)

# ── approved candidate feature columns (offline names in the bundle) ─────────
# Each maps to an ONLINE source: the transaction payload (intrinsic), or a
# node-local window read for a specific account (source = from_account,
# target = to_account).
INTRINSIC = ("amount", "is_cross_bank", "hour", "day_of_week", "is_weekend",
             "currency_enc", "payment_type_enc")
SOURCE_WINDOW = {
    "source_out_tx_count_1h": "source_out_degree_1h",
    "source_out_tx_count_24h": "source_out_degree_24h",
    "source_out_amount_sum_1h": "amount_sent_1h",
    "source_out_amount_sum_24h": "amount_sent_24h",
}
TARGET_WINDOW = {
    "target_in_tx_count_1h": "target_in_degree_1h",
    "target_in_tx_count_24h": "target_in_degree_24h",
    "target_in_amount_sum_1h": "amount_received_1h",
    "target_in_amount_sum_24h": "amount_received_24h",
}
APPROVED_OFFLINE = INTRINSIC + tuple(SOURCE_WINDOW) + tuple(TARGET_WINDOW)

# Canonical names (for the response), keyed by offline name.
CANONICAL = {
    "amount": "amount", "is_cross_bank": "is_cross_bank", "hour": "hour_of_day",
    "day_of_week": "day_of_week", "is_weekend": "is_weekend",
    "currency_enc": "currency_code", "payment_type_enc": "payment_type_code",
    "source_out_tx_count_1h": "source_outflow_count_1h",
    "source_out_tx_count_24h": "source_outflow_count_24h",
    "target_in_tx_count_1h": "target_inflow_count_1h",
    "target_in_tx_count_24h": "target_inflow_count_24h",
    "source_out_amount_sum_1h": "source_outflow_amount_1h",
    "source_out_amount_sum_24h": "source_outflow_amount_24h",
    "target_in_amount_sum_1h": "target_inflow_amount_1h",
    "target_in_amount_sum_24h": "target_inflow_amount_24h",
}

# Confirmed-excluded canonical features (never built or scored).
EXCLUDED_CONFIRMED = (
    "source_account_code", "target_account_code", "source_bank_code", "target_bank_code",
    "source_outflow_count_all_time", "target_inflow_count_all_time",
    "account_pair_count_all_time", "fan_in_count_24h", "fan_out_count_24h",
    "fan_in_normalized_1h", "fan_out_normalized_1h", "scatter_gather_score",
    "simple_cycle_score", "account_velocity_zscore", "sweep_after_fan_in_flag",
)

# Defense in depth: names that must never appear in the candidate matrix.
_FORBIDDEN_SUBSTR = ("account_enc", "bank_enc", "_total_before", "account_pair_")
_FORBIDDEN_EXACT = frozenset({
    "fan_in_score", "fan_out_score", "fan_in_normalized_1h", "fan_out_normalized_1h",
    "scatter_gather_score", "simple_cycle_score", "account_velocity_zscore",
    "sweep_after_fan_in_flag", "sweep_ratio", "rapid_movement_flag",
})

_LIMITATIONS = [
    "Shadow comparison only — does NOT drive decisions, create cases, or affect /api/score-transaction.",
    "Synthetic AMLworld benchmark; candidate not deployed and not production-validated.",
    "Candidate features are point-in-time online windows; baseline single-tx score uses no history (its deployed behaviour).",
    "Bucketed/aggregate values only — no raw identifiers or raw feature values are exposed.",
]


# ── candidate bundle (lazy, optional) ────────────────────────────────────────

_CANDIDATE: dict[str, Any] | None = None
_CANDIDATE_ATTEMPTED = False


def get_candidate_bundle() -> dict[str, Any] | None:
    """Load the candidate bundle lazily. Returns None if absent/unreadable."""
    global _CANDIDATE, _CANDIDATE_ATTEMPTED
    if _CANDIDATE_ATTEMPTED:
        return _CANDIDATE
    _CANDIDATE_ATTEMPTED = True
    path = config.CANDIDATE_MODEL_PATH
    if not path.exists():
        logger.info("Candidate model not found at %s — shadow scoring unavailable.", path)
        return None
    try:
        import joblib

        raw = joblib.load(path)
        if isinstance(raw, dict) and "model" in raw and raw.get("deployed") is not True:
            _assert_no_forbidden(raw.get("feature_columns", []))
            _CANDIDATE = raw
        else:
            logger.warning("Candidate bundle malformed or flagged deployed — refusing to use.")
            _CANDIDATE = None
    except Exception as exc:  # pragma: no cover - degraded mode
        logger.exception("Failed to load candidate model: %s", exc)
        _CANDIDATE = None
    return _CANDIDATE


def reset_candidate_cache() -> None:
    """Test hook: re-probe the candidate bundle after monkeypatching the path."""
    global _CANDIDATE, _CANDIDATE_ATTEMPTED
    _CANDIDATE, _CANDIDATE_ATTEMPTED = None, False


def _assert_no_forbidden(columns: list[str]) -> None:
    bad = [c for c in columns if c in _FORBIDDEN_EXACT or any(s in c for s in _FORBIDDEN_SUBSTR)]
    if bad:
        raise AssertionError(f"Candidate bundle contains HARD-BLOCKED features: {bad}")


# ── feature vector from the online path ──────────────────────────────────────

def build_candidate_vector(node_id: str, body: Any) -> tuple[dict[str, float] | None, str, list[str]]:
    """Build the 15 approved features from the online path.

    Returns (vector_by_offline_name | None, status, missing). ``status`` is
    "complete" or "missing_feature". Windowed features for an account never
    seen locally are a valid 0 (matching offline first-transaction semantics);
    a node with NO window history at all is a genuine missing_feature.
    """
    # Time features require a parseable timestamp (3 of the 15 depend on it).
    ts = scoring_service._parse_ts(body.timestamp) if getattr(body, "timestamp", None) else None
    if ts is None:
        return None, "missing_feature", ["timestamp (required for hour_of_day/day_of_week/is_weekend)"]

    status = feature_store_service.node_status(node_id)
    if status.get("latest_event_ts") is None:
        # No local window state → windowed features cannot be produced point-in-time.
        return None, "missing_feature", [
            "node has no local window history; windowed features cannot be produced online"
        ]

    cross_bank = 1.0 if str(body.from_bank) != str(body.to_bank) else 0.0
    vec: dict[str, float] = {
        "amount": float(body.amount),
        "is_cross_bank": cross_bank,
        "hour": float(ts.hour),
        "day_of_week": float(ts.weekday()),
        "is_weekend": 1.0 if ts.weekday() >= 5 else 0.0,
        "currency_enc": scoring_service._enc(body.currency, scoring_service.CURRENCY_MAP),
        "payment_type_enc": scoring_service._enc(body.payment_format, scoring_service.PAYMENT_TYPE_MAP),
    }

    # Window reads: source side from from_account, target side from to_account.
    # account_features returns None for an unseen account → 0.0 (valid point-in-time).
    src = feature_store_service.account_features(node_id, body.from_account) or {}
    tgt = feature_store_service.account_features(node_id, body.to_account) or {}
    for off_name, store_key in SOURCE_WINDOW.items():
        vec[off_name] = float(src.get(store_key, 0.0))
    for off_name, store_key in TARGET_WINDOW.items():
        vec[off_name] = float(tgt.get(store_key, 0.0))

    # Defense in depth: confirm exactly the approved set, nothing forbidden.
    _assert_no_forbidden(list(vec))
    assert set(vec) == set(APPROVED_OFFLINE), "candidate vector must be exactly the 15 approved features"
    return vec, "complete", []


# ── thresholds / tiers ───────────────────────────────────────────────────────

def _threshold_modes() -> dict[str, float]:
    report = model_service.load_json_report(config.CANDIDATE_THRESHOLDS_PATH)
    modes: dict[str, float] = {}
    if isinstance(report, dict):
        for r in report.get("thresholds", []):
            if "mode" in r and "threshold" in r:
                modes[r["mode"]] = float(r["threshold"])
    return modes


def _tier_and_action(score: float, modes: dict[str, float], bundle_threshold: float) -> tuple[str, str, str]:
    hp = modes.get("high_precision")
    bal = modes.get("balanced", bundle_threshold)
    hr = modes.get("high_recall")
    if hp is not None and score >= hp:
        return "high", "balanced", "escalate_review (shadow)"
    if score >= bal:
        return "medium", "balanced", "analyst_queue (shadow)"
    if hr is not None and score >= hr:
        return "low", "balanced", "monitor (shadow)"
    return "minimal", "balanced", "no_alert (shadow)"


# ── shadow score ─────────────────────────────────────────────────────────────

def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "candidate_available": False,
        "shadow_only": True,
        "feature_vector_status": reason,
        "candidate_model_name": None,
        "candidate_score": None,
        "candidate_risk_tier": None,
        "candidate_threshold_mode": None,
        "candidate_recommended_action": None,
        "baseline_score": None,
        "score_delta": None,
        "agreement_with_baseline": "unknown",
        "used_features": [],
        "excluded_features_confirmed": list(EXCLUDED_CONFIRMED),
        "limitations": _LIMITATIONS,
        "pii_safe": True,
    }


def score_shadow(node_id: str, body: Any) -> dict[str, Any]:
    """Score the transaction with the shadow candidate beside the baseline.

    Never raises on degraded state — returns a safe ``candidate_available:
    False`` payload instead so the caller can audit "unavailable".
    """
    bundle = get_candidate_bundle()
    if bundle is None:
        return _unavailable("candidate_unavailable")

    vec, status, missing = build_candidate_vector(node_id, body)
    if vec is None:
        out = _unavailable("missing_feature")
        out["candidate_model_name"] = bundle.get("model_name")
        out["missing_features"] = missing
        return out

    import numpy as np

    feature_columns = bundle["feature_columns"]
    _assert_no_forbidden(feature_columns)
    try:
        row = np.array([[vec[c] for c in feature_columns]], dtype="float64")
        model = bundle["model"]
        score = float(model.predict_proba(row)[0, 1])
    except Exception as exc:  # pragma: no cover - degraded mode
        logger.warning("Candidate inference failed: %s", exc)
        out = _unavailable("candidate_unavailable")
        out["candidate_model_name"] = bundle.get("model_name")
        return out

    modes = _threshold_modes()
    bundle_threshold = float(bundle.get("threshold", 0.5))
    tier, threshold_mode, action = _tier_and_action(score, modes, bundle_threshold)
    candidate_alerts = score >= modes.get("balanced", bundle_threshold)

    # Baseline comparison (read-only call into the deployed scorer; unchanged).
    baseline_score = None
    agreement = "baseline_unavailable"
    score_delta = None
    baseline_risk_tier = None
    baseline_action = None
    try:
        base = scoring_service.score(TransactionIn(
            timestamp=body.timestamp, from_bank=body.from_bank, from_account=body.from_account,
            to_bank=body.to_bank, to_account=body.to_account, amount=body.amount,
            currency=body.currency, payment_format=body.payment_format,
        ))
        baseline_score = round(base.risk_score, 6)
        score_delta = round(score - base.risk_score, 6)
        baseline_alerts = base.prediction in ("suspicious", "block")
        agreement = "agree" if baseline_alerts == candidate_alerts else "disagree"
        # Baseline tier/action surfaced for monitoring (bucketed downstream).
        baseline_risk_tier = {"block": "high", "suspicious": "medium", "benign": "minimal"}.get(
            base.prediction, "minimal")
        baseline_action = base.prediction
    except Exception as exc:  # pragma: no cover - baseline is best-effort
        logger.warning("Baseline comparison unavailable: %s", exc)

    return {
        "candidate_available": True,
        "shadow_only": True,
        "candidate_model_name": bundle.get("model_name"),
        "candidate_score": round(score, 6),
        "candidate_risk_tier": tier,
        "candidate_threshold_mode": threshold_mode,
        "candidate_recommended_action": action,
        "baseline_score": baseline_score,
        "baseline_risk_tier": baseline_risk_tier,
        "baseline_action": baseline_action,
        "score_delta": score_delta,
        "agreement_with_baseline": agreement,
        "feature_vector_status": status,
        "used_features": [CANONICAL[c] for c in feature_columns],
        "excluded_features_confirmed": list(EXCLUDED_CONFIRMED),
        "limitations": _LIMITATIONS,
        "pii_safe": True,
    }


# ── readiness report ─────────────────────────────────────────────────────────

def shadow_readiness() -> dict[str, Any]:
    """Assess whether shadow scoring can run: artifacts, features, endpoint."""
    from datetime import datetime, timezone

    bundle = get_candidate_bundle()
    metrics = model_service.load_json_report(config.CANDIDATE_METRICS_PATH)
    thresholds = model_service.load_json_report(config.CANDIDATE_THRESHOLDS_PATH)
    contract = model_service.load_json_report(config.FEATURE_CONTRACT_PATH)
    manifest = model_service.load_json_report(config.TRAINING_FEATURE_MANIFEST_PATH)

    return {
        "source": "live",
        "report": "candidate_shadow_readiness",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "shadow_only": True,
        "deployed": False,
        "deployment_recommended": False,
        "artifact_availability": {
            "candidate_model_joblib": bundle is not None,
            "candidate_model_metrics": metrics is not None,
            "candidate_thresholds": thresholds is not None,
            "feature_contract": contract is not None,
            "training_feature_manifest": manifest is not None,
        },
        "feature_availability": {
            "approved_feature_count": len(APPROVED_OFFLINE),
            "intrinsic_from_payload": list(INTRINSIC),
            "windowed_from_online_store": list(SOURCE_WINDOW) + list(TARGET_WINDOW),
            "excluded_confirmed": list(EXCLUDED_CONFIRMED),
            "missing_feature_behaviour": "no node window history or unparseable timestamp → missing_feature, not scored",
        },
        "endpoint": {
            "path": "POST /api/model/candidate/score-shadow",
            "auth": "node API key; source_node_id must match the authenticated node",
            "pii_guard": "same find_transaction_pii guard as /api/features/score-with-context",
            "audited": True,
            "creates_cases": False,
            "affects_deployed_scoring": False,
        },
        "known_limitations": _LIMITATIONS,
        "why_not_deployed": (
            "Synthetic-benchmark candidate; comparison-only. Needs out-of-time validation on real "
            "supervised data under SAMA governance, calibration, drift monitoring, and sign-off."
        ),
        "needed_before_deployment": [
            "Out-of-time validation on real (non-synthetic) data under SAMA governance.",
            "Online/offline parity confirmed on the live serving path at scale (not just the replay harness).",
            "Calibration + drift monitoring + alerting.",
            "A documented rollback and human-in-the-loop governance plan.",
        ],
        "pii_safe": True,
    }
