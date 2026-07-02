"""Explainable-AI / "Why flagged?" engine.

Turns model scores, contextual rule adjustments, and pattern typologies into
analyst-readable, PII-safe explanations for the Investigator Dashboard.

Three subjects:
  * transaction — explains a /api/features/score-with-context decision
    (base model SHAP/fallback attribution + contextual rule layer).
  * case — explains a registered-pattern case (typology + bucketed evidence).
  * model — summarizes the offline evaluation reports (best/test-leader model,
    weakest typology, threshold policy, limitations).

Attribution method:
  * SHAP TreeExplainer when shap is installed AND the deployed model is a
    supported tree model (XGBoost / LightGBM / RandomForest). Raw feature
    values are NEVER exposed — every factor carries a coarse ``value_bucket``.
  * Otherwise a deterministic fallback using the model's global feature
    importance + computable transaction signals + the contextual rule hits.
    The response records ``explanation_method`` and a note so the UI can say
    which path produced it.

PII contract: explanations contain only feature *names*, bucket labels, and
templated text. A final guard (``_scrub``) runs every assembled explanation
through ``pii_guard.find_pii`` and redacts anything that slips through, so
``pii_safe`` is always truthful. No raw account/transaction ids, IBANs,
names, national ids, phones, emails, or payloads ever appear.

Honesty: explanations are decision-support, NOT a legal/regulatory
sufficiency statement; typology labels are heuristic; the deployed model has
not been retrained on context features. These caveats ship in every payload's
``model_limitations``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ..core import config
from . import model_service, pii_guard, scoring_service
from ..core.schemas import TransactionIn

logger = logging.getLogger(__name__)


# ── SHAP availability (probed once, lazily) ──────────────────────────────────

_SHAP_STATE: dict[str, Any] | None = None
_SUPPORTED_TREE_MODELS = ("XGBClassifier", "LGBMClassifier", "RandomForestClassifier")


def shap_state() -> dict[str, Any]:
    """Return {available, reason, library} for the SHAP path. Probed once."""
    global _SHAP_STATE
    if _SHAP_STATE is not None:
        return _SHAP_STATE
    try:
        import shap  # type: ignore

        _SHAP_STATE = {"available": True, "library": f"shap {shap.__version__}", "reason": None}
    except Exception as exc:  # pragma: no cover - env dependent
        _SHAP_STATE = {
            "available": False,
            "library": None,
            "reason": f"shap import failed ({exc}); using deterministic feature/rule attribution fallback.",
        }
        logger.info("SHAP unavailable: %s", exc)
    return _SHAP_STATE


def reset_shap_state() -> None:
    """Test hook: clear the cached probe so monkeypatching shap takes effect."""
    global _SHAP_STATE
    _SHAP_STATE = None


# ── human labels & bucketers (no raw values ever leave this module) ──────────

FEATURE_LABELS: dict[str, str] = {
    "amount": "Transaction amount",
    "currency_enc": "Currency",
    "payment_type_enc": "Payment type",
    "source_bank_enc": "Originating bank",
    "target_bank_enc": "Destination bank",
    "source_account_enc": "Source account familiarity",
    "target_account_enc": "Beneficiary account familiarity",
    "is_cross_bank": "Cross-bank transfer",
    "cross_bank_flow_flag": "Cross-bank flow",
    "hour": "Time of day",
    "day_of_week": "Day of week",
    "is_weekend": "Weekend timing",
    "source_out_tx_count_total_before": "Source historical send count",
    "source_out_amount_sum_total_before": "Source historical sent volume",
    "source_unique_targets_total_before": "Source distinct beneficiaries",
    "target_in_tx_count_total_before": "Beneficiary historical receive count",
    "target_in_amount_sum_total_before": "Beneficiary historical received volume",
    "target_unique_sources_total_before": "Beneficiary distinct senders",
    "account_pair_tx_count_before": "Prior transfers between this pair",
    "account_pair_amount_sum_before": "Prior volume between this pair",
    "source_out_tx_count_1h": "Source sends in last 1h",
    "source_out_amount_sum_1h": "Source sent volume in last 1h",
    "target_in_tx_count_1h": "Beneficiary inflows in last 1h",
    "target_in_amount_sum_1h": "Beneficiary inflow volume in last 1h",
    "source_out_tx_count_24h": "Source sends in last 24h",
    "source_out_amount_sum_24h": "Source sent volume in last 24h",
    "target_in_tx_count_24h": "Beneficiary inflows in last 24h",
    "target_in_amount_sum_24h": "Beneficiary inflow volume in last 24h",
    "fan_in_score": "Fan-in concentration",   # offline bundle feature (24h count)
    "fan_out_score": "Fan-out dispersion",     # offline bundle feature (24h count)
    "fan_in_normalized_1h": "Fan-in intensity (1h)",   # online normalised score
    "fan_out_normalized_1h": "Fan-out intensity (1h)", # online normalised score
    "sweep_ratio": "Sweep ratio (amount vs baseline)",
    "rapid_movement_flag": "Rapid in-out movement",
}


# ── canonical feature contract (decoupled: missing file → graceful fallback) ─

_CONTRACT_INDEX: dict[str, Any] | None = None


def _contract_index() -> dict[str, Any]:
    """Load the canonical feature contract indexed by offline_name. Cached.

    Decoupled via the JSON report loader so a missing contract simply yields an
    empty index and the service falls back to the built-in FEATURE_LABELS — the
    explanation engine keeps working without the contract.
    """
    global _CONTRACT_INDEX
    if _CONTRACT_INDEX is not None:
        return _CONTRACT_INDEX
    index: dict[str, Any] = {"by_offline": {}, "loaded": False}
    data = model_service.load_json_report(config.FEATURE_CONTRACT_PATH)
    if isinstance(data, dict) and isinstance(data.get("features"), list):
        for f in data["features"]:
            off = f.get("offline_name")
            if off:
                index["by_offline"][off] = f
        index["loaded"] = bool(index["by_offline"])
    _CONTRACT_INDEX = index
    return _CONTRACT_INDEX


def reset_contract_cache() -> None:
    """Test hook: clear the cached contract so a monkeypatched path re-loads."""
    global _CONTRACT_INDEX
    _CONTRACT_INDEX = None


def _contract_entry(feature_name: str) -> dict[str, Any] | None:
    return _contract_index()["by_offline"].get(feature_name)


def _humanize(feature_name: str) -> str:
    if feature_name in FEATURE_LABELS:
        return FEATURE_LABELS[feature_name]
    # Fall back to the contract's canonical name when not curated locally.
    entry = _contract_entry(feature_name)
    if entry and entry.get("canonical_name"):
        return entry["canonical_name"].replace("_", " ").strip().capitalize()
    return feature_name.replace("_enc", "").replace("_", " ").strip().capitalize()


def _amount_bucket(v: float) -> str:
    if v > 200_000:
        return "xlarge"
    if v > 50_000:
        return "large"
    if v > 10_000:
        return "medium"
    if v > 1_000:
        return "small"
    return "micro"


def _count_bucket(v: float) -> str:
    if v <= 0:
        return "none"
    if v <= 3:
        return "low"
    if v <= 10:
        return "moderate"
    return "high"


def _magnitude_bucket(v: float) -> str:
    a = abs(v)
    if a == 0:
        return "zero"
    if a < 1:
        return "low"
    if a < 10:
        return "moderate"
    return "high"


def _bucket_by_contract_type(bucket_type: str, v: float) -> str | None:
    """Dispatch bucketing by the contract's declared bucket type. Returns None
    for types better handled by the name-based logic below."""
    if bucket_type == "amount":
        return _amount_bucket(v)
    if bucket_type == "count":
        return _count_bucket(v)
    if bucket_type == "account_familiarity":
        return "unseen_account" if v < 0 else "known_account"
    if bucket_type == "category":
        return "unknown_category" if v < 0 else "known_category"
    if bucket_type == "cross_bank":
        return "cross_bank" if v > 0 else "same_bank"
    if bucket_type == "is_weekend":
        return "weekend" if v > 0 else "weekday"
    if bucket_type == "flag":
        return "flagged" if v > 0 else "not_flagged"
    if bucket_type == "score":
        return _magnitude_bucket(v)
    return None


def value_bucket(feature_name: str, value: Any) -> str:
    """Coarse, PII-safe bucket for a raw feature value. Never returns the
    underlying number/identifier. Bucket logic comes from the feature contract
    where it declares a bucket type; otherwise falls back to name-based rules."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "unknown"

    entry = _contract_entry(feature_name)
    if entry and entry.get("bucket"):
        by_contract = _bucket_by_contract_type(entry["bucket"], v)
        if by_contract is not None:
            return by_contract

    name = feature_name
    if name == "amount" or name.endswith("_amount_sum_before") or name.endswith("_amount_sum_1h") \
            or name.endswith("_amount_sum_24h") or name.endswith("_amount_sum_total_before"):
        return _amount_bucket(v)
    if name in ("source_account_enc", "target_account_enc"):
        # -1 is the LabelEncoder code for an account unseen in training.
        return "unseen_account" if v < 0 else "known_account"
    if name in ("currency_enc", "payment_type_enc", "source_bank_enc", "target_bank_enc"):
        return "unknown_category" if v < 0 else "known_category"
    if name in ("is_cross_bank", "cross_bank_flow_flag"):
        return "cross_bank" if v > 0 else "same_bank"
    if name == "is_weekend":
        return "weekend" if v > 0 else "weekday"
    if name == "rapid_movement_flag":
        return "flagged" if v > 0 else "not_flagged"
    if name == "hour":
        h = int(v)
        if h < 6 or h >= 22:
            return "off_hours"
        if 6 <= h < 9 or 17 <= h < 22:
            return "fringe_hours"
        return "business_hours"
    if name == "day_of_week":
        return "weekend" if int(v) >= 5 else "weekday"
    if "count" in name or "unique" in name or "degree" in name:
        return _count_bucket(v)
    if name == "sweep_ratio":
        if v <= 1.2:
            return "baseline"
        if v <= 3:
            return "elevated"
        return "extreme"
    return _magnitude_bucket(v)


def risk_tier(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.9:
        return "critical"
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


# ── typology AML explanations ────────────────────────────────────────────────

_TYPOLOGY_INFO: dict[str, dict[str, Any]] = {
    "fan_in": {
        "what": "Multiple distinct sources funnelled funds into a single account.",
        "why": "Fan-in is the collection stage of a mule operation — sub-threshold deposits aggregated before a single cash-out.",
        "evidence": ["multiple_distinct_senders", "sub_threshold_amounts", "short_collection_window"],
    },
    "fan_out": {
        "what": "One account rapidly distributed funds to many recipients.",
        "why": "Fan-out is the dispersal stage of layering — splitting value across accounts to break the audit trail.",
        "evidence": ["many_distinct_beneficiaries", "rapid_dispersal", "even_amount_splits"],
    },
    "rapid_sweep": {
        "what": "An accumulated balance left in a single large transfer shortly after collection.",
        "why": "A sweep is the cash-out step — funds are not held, they exit once aggregated.",
        "evidence": ["high_sweep_ratio", "short_dwell_time", "outflow_matches_recent_inflow"],
    },
    "mule_velocity": {
        "what": "An account received a burst of inflows and forwarded the balance almost immediately.",
        "why": "Mule accounts park money for minutes, not days — high in-out velocity with little net balance is a strong signal.",
        "evidence": ["inflow_burst_in_window", "rapid_forwarding", "low_net_balance"],
    },
    "cross_bank_pass_through": {
        "what": "Funds entered from one institution and exited to another with minimal dwell time.",
        "why": "Pass-through uses the bank as a corridor; cross-bank hops frustrate single-institution monitoring.",
        "evidence": ["cross_bank_in_and_out", "short_dwell_time", "corridor_shape"],
    },
    "scatter_gather": {
        "what": "Funds split across many accounts then reconverged at a new destination.",
        "why": "Split-and-merge layering obscures the one-to-one link between origin and destination.",
        "evidence": ["outbound_split", "downstream_reconvergence", "consistent_amount_buckets"],
    },
    "gather_scatter": {
        "what": "Funds converged into one account then split outward to many.",
        "why": "The inverse staging pattern — collection followed by dispersal through a single hub.",
        "evidence": ["inbound_convergence", "hub_account", "outbound_dispersal"],
    },
    "simple_cycle": {
        "what": "Funds travelled a closed loop of accounts and returned near the origin.",
        "why": "Circular layering manufactures transaction history to disguise the provenance of funds.",
        "evidence": ["closed_loop", "short_cycle_length", "value_returns_to_origin"],
    },
}

_TYPOLOGY_LIMITATION = (
    "Heuristic typology label from the pattern library, not ground-truth classification; "
    "confirm against the full case record before acting."
)


def _confidence_bucket(v: float | None) -> str:
    if v is None:
        return "unknown"
    if v >= 0.8:
        return "high"
    if v >= 0.5:
        return "moderate"
    return "low"


def typology_factor(typology: str | None, *, tier: str | None, confidence: float | None,
                    extra_evidence: list[str] | None = None) -> dict[str, Any] | None:
    if not typology:
        return None
    info = _TYPOLOGY_INFO.get(typology)
    if info is None:
        return {
            "typology": typology,
            "what_detected": "Pattern matched a registered network typology.",
            "why_it_matters": "Flagged by a Naseej typology detector; see the case evidence summary.",
            "evidence_buckets": list(extra_evidence or []),
            "risk_tier": tier or "unknown",
            "confidence_bucket": _confidence_bucket(confidence),
            "limitations": _TYPOLOGY_LIMITATION,
        }
    evidence = list(info["evidence"])
    for e in (extra_evidence or []):
        if e not in evidence:
            evidence.append(e)
    return {
        "typology": typology,
        "what_detected": info["what"],
        "why_it_matters": info["why"],
        "evidence_buckets": evidence,
        "risk_tier": tier or "unknown",
        "confidence_bucket": _confidence_bucket(confidence),
        "limitations": _TYPOLOGY_LIMITATION,
    }


# ── model limitations (always shipped) ──────────────────────────────────────

def _model_limitations(*, context: bool) -> list[str]:
    items = [
        "Decision-support only — NOT a legal or regulatory sufficiency statement; a human analyst decides.",
        "Trained and evaluated on synthetic AMLworld data; not validated on real banking transactions.",
        "Feature values are bucketed for privacy; explanations show direction and magnitude, not exact figures.",
        "Account-identity features can reflect memorisation and may not generalise to unseen accounts.",
    ]
    if context:
        items.append(
            "Context adjustment is a deterministic rule layer; the deployed model has NOT been retrained "
            "on context features, and context can escalate but never soften the base score."
        )
    return items


def _contract_factor_limitations(factors: list[dict[str, Any]]) -> list[str]:
    """Per-feature limitations sourced from the feature contract for the
    surfaced top factors (e.g. identity-memorisation flags). Empty when the
    contract is unavailable — the explanation still works without it."""
    notes: list[str] = []
    seen: set[str] = set()
    for f in factors:
        entry = _contract_entry(f.get("feature_name", ""))
        if not entry:
            continue
        if entry.get("identity_memorization_risk") and "memorisation" not in seen:
            seen.add("memorisation")
            notes.append(
                f"Factor '{f['human_label']}' is an identity feature flagged in the feature contract "
                "as a memorisation risk — excluded from the approved retraining set and may not generalise."
            )
        if entry.get("parity_status") == "definition_mismatch" and "parity" not in seen:
            seen.add("parity")
            notes.append(
                "One or more surfaced features have an offline/online definition mismatch in the feature "
                "contract; see /api/model/feature-parity. Treat their attribution as indicative."
            )
    return notes


# ── threshold rationale (from the evaluation reports, with fallback) ─────────

def _threshold_rationale() -> dict[str, Any]:
    threshold = model_service.get_threshold()
    report = model_service.load_json_report(config.THRESHOLD_ANALYSIS_PATH)
    modes: list[dict[str, Any]] = []
    if isinstance(report, dict) and isinstance(report.get("thresholds"), list):
        for row in report["thresholds"]:
            modes.append({
                "mode": row.get("mode"),
                "recommended_use": row.get("recommended_use"),
            })
    rationale: dict[str, Any] = {
        "active_threshold_bucket": (
            "very_low_precision_threshold"
            if (threshold is not None and threshold < 0.1)
            else "tuned_threshold"
        ),
        "policy": (
            "The score is compared against an operating threshold tuned on a validation split. "
            "High-precision mode suits compliance escalation; balanced mode suits the analyst queue; "
            "high-recall mode is monitoring-only."
        ),
        "modes": modes or [
            {"mode": "high_precision", "recommended_use": "Compliance escalation"},
            {"mode": "balanced", "recommended_use": "Analyst queue"},
            {"mode": "high_recall", "recommended_use": "Monitoring only"},
        ],
        "note": "Thresholds are illustrative operating points on a synthetic benchmark, not production cut-offs.",
    }
    return rationale


# ── SHAP / fallback attribution ──────────────────────────────────────────────

_RISK_RAISING_DEFAULT = frozenset({
    "amount", "is_cross_bank", "cross_bank_flow_flag", "fan_in_score", "fan_out_score",
    "sweep_ratio", "rapid_movement_flag",
})


def _factor(feature_name: str, *, direction: str, level: str, raw_value: Any) -> dict[str, Any]:
    bucket = value_bucket(feature_name, raw_value)
    label = _humanize(feature_name)
    phrase = "raised" if direction == "increases_risk" else "lowered"
    return {
        "feature_name": feature_name,
        "direction": direction,
        "contribution_level": level,
        "human_label": label,
        "explanation": f"{label} ({bucket}) {phrase} the model's risk for this transaction.",
        "value_bucket": bucket,
    }


def _shap_factors(model: Any, X, feature_columns: list[str], top_k: int) -> list[dict[str, Any]] | None:
    """TreeExplainer attribution for one row. Returns None on any failure so
    the caller can fall back."""
    try:
        import shap  # type: ignore
        import numpy as np

        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(X.to_numpy())
        arr = np.asarray(values)
        # Binary classifiers may return a list/3D array (per class) — take the
        # positive class contributions.
        if arr.ndim == 3:
            arr = arr[..., 1] if arr.shape[-1] == 2 else arr[..., -1]
        row = np.asarray(arr).reshape(-1)
        if row.shape[0] != len(feature_columns):
            return None
        order = np.argsort(np.abs(row))[::-1]
        total = float(np.sum(np.abs(row))) or 1.0
        raw = X.iloc[0].tolist()
        factors: list[dict[str, Any]] = []
        for idx in order:
            contrib = float(row[idx])
            if abs(contrib) < 1e-9:
                continue
            share = abs(contrib) / total
            level = "high" if share >= 0.25 else "medium" if share >= 0.10 else "low"
            direction = "increases_risk" if contrib > 0 else "decreases_risk"
            factors.append(_factor(feature_columns[idx], direction=direction, level=level, raw_value=raw[idx]))
            if len(factors) >= top_k:
                break
        return factors
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("SHAP attribution failed, falling back: %s", exc)
        return None


def _fallback_factors(feature_columns: list[str], X, top_k: int) -> list[dict[str, Any]]:
    """Deterministic attribution: global feature importance × whether the
    feature carries a non-default signal for this transaction. Direction comes
    from a small, documented rules table (no raw values exposed)."""
    importances: dict[str, float] = {}
    report = model_service.load_json_report(config.FEATURE_IMPORTANCE_PATH)
    if isinstance(report, dict):
        for item in report.get("features", []):
            if "feature" in item:
                importances[item["feature"]] = float(item.get("importance", 0.0))
    raw = dict(zip(feature_columns, X.iloc[0].tolist()))

    scored: list[tuple[float, str, Any]] = []
    for name, val in raw.items():
        try:
            fv = float(val)
        except (TypeError, ValueError):
            continue
        # A feature only "contributes" if it departs from its neutral default
        # (0, or -1 for encoded ids) — otherwise the model saw no signal.
        neutral = fv == 0.0 or (name.endswith("_enc") and fv < 0)
        if neutral and name not in ("source_account_enc", "target_account_enc"):
            continue
        weight = importances.get(name, 0.0)
        scored.append((weight, name, val))

    scored.sort(key=lambda t: t[0], reverse=True)
    factors: list[dict[str, Any]] = []
    for i, (weight, name, val) in enumerate(scored[:top_k]):
        level = "high" if weight >= 0.08 else "medium" if weight >= 0.03 else "low"
        if name in ("source_account_enc", "target_account_enc"):
            direction = "decreases_risk" if float(val) >= 0 else "increases_risk"
        else:
            direction = "increases_risk" if name in _RISK_RAISING_DEFAULT else "increases_risk"
        factors.append(_factor(name, direction=direction, level=level, raw_value=val))
    return factors


def _attribution(tx: TransactionIn, top_k: int = 5) -> tuple[list[dict[str, Any]], str, str, str]:
    """Return (top_factors, method, method_note, model_family) for a single
    transaction's base-model score."""
    bundle = model_service.get_bundle()
    if bundle is None or not bundle.get("feature_columns"):
        return (
            [],
            "fallback",
            "Model bundle unavailable; explanation derives from contextual rules and typology only.",
            "heuristic",
        )
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]
    model_family = type(model).__name__
    X = scoring_service.build_feature_vector(tx, feature_columns)

    state = shap_state()
    is_tree = model_family in _SUPPORTED_TREE_MODELS
    if state["available"] and is_tree:
        factors = _shap_factors(model, X, feature_columns, top_k)
        if factors is not None:
            return factors, "shap", f"SHAP TreeExplainer attribution ({state['library']}).", model_family
        note = "SHAP attribution failed at runtime; used deterministic feature/rule attribution fallback."
    elif not state["available"]:
        note = state["reason"]
    else:
        note = (
            f"Model family '{model_family}' is not a supported tree model for SHAP; "
            "used deterministic feature/rule attribution fallback."
        )
    return _fallback_factors(feature_columns, X, top_k), "fallback", note, model_family


# ── PII final guard ──────────────────────────────────────────────────────────

_REDACTION = "[redacted-for-privacy]"


def _scrub(obj: Any) -> Any:
    """Recursively redact any string that the PII guard flags. Belt-and-braces
    over controlled templates so ``pii_safe`` is always truthful."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    if isinstance(obj, str):
        # Reuse the content rules only (key-name rules don't apply to a bare
        # string); a flagged value is replaced wholesale.
        return _REDACTION if pii_guard.find_pii({"_": obj}) else obj
    return obj


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    scrubbed = _scrub(payload)
    scrubbed["pii_safe"] = pii_guard.verify_zero_pii(scrubbed)
    return scrubbed


# ── public: transaction explanation ──────────────────────────────────────────

def explain_transaction(
    tx: TransactionIn,
    *,
    context_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain a (context) score for one pseudonymous transaction.

    ``context_result`` is the dict form of ContextScoreOut (base score,
    adjustment, final score, rule explanation, context_features). When absent
    the explanation covers the base model score only.
    """
    top_factors, method, method_note, model_family = _attribution(tx)

    contextual_factors: list[str] = []
    typology_extra: list[str] = []
    inferred_typology: str | None = None
    score: float | None = None

    if context_result is not None:
        score = context_result.get("final_contextual_score")
        feats = context_result.get("context_features", {}) or {}
        raw_expl = context_result.get("explanation", []) or []
        # Drop the standing honesty sentence (it lives in model_limitations).
        contextual_factors = [
            e for e in raw_expl
            if not e.startswith("Adjustment is a deterministic rule layer")
        ]
        if feats.get("sweep_after_fan_in_flag"):
            inferred_typology = "rapid_sweep"
            typology_extra = ["sweep_after_fan_in", "short_dwell_time"]
        elif feats.get("fan_in_normalized_1h", 0) and float(feats.get("fan_in_normalized_1h", 0)) > 0:
            inferred_typology = "fan_in"
            typology_extra = ["fan_in_window"]
        if feats.get("tx_is_cross_bank"):
            typology_extra.append("cross_bank_in_and_out")
    else:
        base = scoring_service.score(tx)
        score = base.risk_score

    tier = risk_tier(score)
    typ = typology_factor(inferred_typology, tier=tier, confidence=None, extra_evidence=typology_extra)

    summary = _transaction_summary(score, tier, top_factors, contextual_factors, method)

    payload = {
        "explanation_id": str(uuid.uuid4()),
        "subject": "transaction",
        "model_family": model_family,
        "explanation_method": method,
        "method_note": method_note,
        "score": round(score, 6) if isinstance(score, (int, float)) else None,
        "risk_tier": tier,
        "top_factors": top_factors,
        "contextual_factors": contextual_factors,
        "typology_factors": [typ] if typ else [],
        "threshold_rationale": _threshold_rationale(),
        "model_limitations": _model_limitations(context=context_result is not None)
        + _contract_factor_limitations(top_factors),
        "analyst_summary": summary,
        "pii_safe": True,
    }
    return _finalize(payload)


def _transaction_summary(score, tier, top_factors, contextual_factors, method) -> str:
    drivers = ", ".join(f["human_label"].lower() for f in top_factors[:3]) or "transaction attributes"
    base = (
        f"Risk assessed {tier or 'unknown'}"
        + (f" (score {score:.3f})" if isinstance(score, (int, float)) else "")
        + f". Top model drivers: {drivers} ({method} attribution)."
    )
    if contextual_factors:
        base += f" Context added {len(contextual_factors)} velocity/counterparty signal(s)."
    return base


# ── public: case explanation ─────────────────────────────────────────────────

def explain_case(case: dict[str, Any], *, pattern: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explain a registered-pattern case for the investigator UI.

    ``pattern`` (optional) is the registry envelope's bucketed pattern object;
    its velocity_features / graph_signature buckets enrich the factors. Only
    bucketed, zero-PII-by-contract fields are read from it.
    """
    typology = case.get("typology")
    tier = case.get("risk_tier") or risk_tier(case.get("risk_score"))
    confidence = case.get("confidence")

    top_factors: list[dict[str, Any]] = []
    evidence_extra: list[str] = []
    if pattern is not None:
        vel = pattern.get("velocity_features", {}) or {}
        for k, v in vel.items():
            if isinstance(v, str):
                evidence_extra.append(f"{k}:{v}")
                top_factors.append({
                    "feature_name": k,
                    "direction": "increases_risk",
                    "contribution_level": "high" if "high" in str(v) else "medium",
                    "human_label": k.replace("_", " ").capitalize(),
                    "explanation": f"{k.replace('_', ' ').capitalize()} bucket '{v}' supported the typology match.",
                    "value_bucket": str(v),
                })
        sig = pattern.get("graph_signature", {}) or {}
        if sig.get("is_cross_bank"):
            evidence_extra.append("cross_bank_in_and_out")

    typ = typology_factor(typology, tier=tier, confidence=confidence, extra_evidence=evidence_extra)

    summary = (
        f"Case flagged as {(typology or 'pattern').replace('_', ' ')} at {tier or 'unknown'} risk "
        f"({_confidence_bucket(confidence)} confidence). "
        + (typ["why_it_matters"] if typ else "")
    )

    payload = {
        "explanation_id": str(uuid.uuid4()),
        "subject": "case",
        "case_id": case.get("case_id"),
        "model_family": "pattern_detector",
        "explanation_method": "rule",
        "method_note": (
            "Case-level explanation derived from the registered typology and bucketed pattern evidence. "
            "Transaction-level SHAP/feature attribution is available via /api/explain/transaction at scoring time."
        ),
        "score": case.get("risk_score"),
        "risk_tier": tier,
        "top_factors": top_factors,
        "contextual_factors": [],
        "typology_factors": [typ] if typ else [],
        "threshold_rationale": _threshold_rationale(),
        "model_limitations": _model_limitations(context=False),
        "analyst_summary": summary.strip(),
        "pii_safe": True,
    }
    return _finalize(payload)


# ── public: model explanation (report-derived, public) ───────────────────────

def explain_model() -> dict[str, Any]:
    """Summarize the offline evaluation reports. Degrades gracefully when any
    report is missing."""
    comparison = model_service.load_json_report(config.MODEL_COMPARISON_PATH)
    typology = model_service.load_json_report(config.PER_TYPOLOGY_RECALL_PATH)
    thresholds = model_service.load_json_report(config.THRESHOLD_ANALYSIS_PATH)
    state = shap_state()

    payload: dict[str, Any] = {
        "source": "live" if comparison else "fallback",
        "subject": "model",
        "explanation_method": "shap_capable" if state["available"] else "fallback_only",
        "shap_available": state["available"],
        "pii_safe": True,
    }

    if isinstance(comparison, dict):
        payload["selected_model"] = comparison.get("best_model")
        payload["test_leader"] = comparison.get("test_leader")
        payload["test_leader_pr_auc"] = comparison.get("test_leader_pr_auc")
        payload["selection_note"] = comparison.get("selection_note")
        payload["lightgbm_evaluated"] = (
            comparison.get("availability", {}).get("lightgbm", {}).get("available")
        )
    else:
        payload["note"] = "model_comparison.json not generated yet — run the evaluation suite."

    if isinstance(typology, dict):
        payload["weakest_typology"] = typology.get("weakest_typology")
        payload["typology_label_method"] = typology.get("label_method")

    payload["threshold_rationale"] = _threshold_rationale()
    payload["model_limitations"] = _model_limitations(context=False)

    leader = payload.get("test_leader") or payload.get("selected_model") or "the baseline model"
    weak = payload.get("weakest_typology")
    summary = f"Best held-out PR-AUC: {leader}."
    if weak:
        summary += f" Weakest detected typology: {weak.replace('_', ' ')} (heuristic label)."
    summary += " Explanations use SHAP when available, deterministic fallback otherwise."
    payload["analyst_summary"] = summary

    return _finalize(payload)
