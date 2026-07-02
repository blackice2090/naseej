"""Single-transaction feature extraction and model inference (Phase 7).

For a single arriving transaction we compute a subset of the training features
exactly (amount, time, cross-bank flag, payment type, currency, bank IDs).
History-dependent features (cumulative counts, velocity windows) are set to 0,
representing a first-time transaction with no prior account context. This is a
conservative bias — the model will score toward the base-rate, so any flag
raised at this level represents a strong signal from the computable features.

Limitations
-----------
- Categorical encoders (LabelEncoder) were fitted on training data and are not
  exported in the bundle. Unknown values default to -1, matching what the
  training code assigns to unseen categories.
- Velocity / cumulative features are 0 (no history). A production deployment
  would maintain a feature store keyed on account ID to fill these in.
- The AMLworld payment-type and currency lists below are complete for the
  HI-Small dataset. Strings outside these lists receive -1 (unknown).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ..core.schemas import ScoreOut, TransactionIn
from . import model_service, privacy_service

logger = logging.getLogger(__name__)


# ── AMLworld known categorical codes (LabelEncoder sorts alphabetically) ────

PAYMENT_TYPE_MAP: dict[str, int] = {
    "ACH": 0,
    "Bitcoin": 1,
    "Bitcoin LN": 2,
    "Cash": 3,
    "Cheque": 4,
    "Credit Card": 5,
    "Reinvestment": 6,
    "SWIFT": 7,
    "Wire": 8,
}

CURRENCY_MAP: dict[str, int] = {
    "AU Dollar": 0,
    "Bitcoin": 1,
    "Brazil Real": 2,
    "Canadian Dollar": 3,
    "Euro": 4,
    "Mexican Peso": 5,
    "Ruble": 6,
    "Rupee": 7,
    "Saudi Riyal": 8,
    "Swiss Franc": 9,
    "UK Pound": 10,
    "US Dollar": 11,
    "Yen": 12,
    "Yuan": 13,
}

# Payment types that carry higher inherent AML risk (used in explanations only).
_HIGH_RISK_PAYMENT_TYPES: frozenset[str] = frozenset({"Bitcoin", "Bitcoin LN", "Cash"})
_MEDIUM_RISK_PAYMENT_TYPES: frozenset[str] = frozenset({"Wire", "SWIFT"})

_TIMESTAMP_FORMATS: tuple[str, ...] = (
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
)


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    try:
        from dateutil.parser import parse as _du
        return _du(ts)
    except Exception:
        return None


def _enc(value: str | None, lookup: dict[str, int]) -> float:
    """Return the LabelEncoder code for a known value, or -1 for unknown."""
    if value is None:
        return -1.0
    return float(lookup.get(value, -1))


def _bank_enc(bank: str | int) -> float:
    """Stable integer for a bank ID using a hash (no LabelEncoder available)."""
    return float(int(hashlib.sha256(str(bank).encode()).hexdigest()[:8], 16) % 10_000)


def build_feature_vector(tx: TransactionIn, feature_columns: list[str]) -> pd.DataFrame:
    """Return a 1-row DataFrame whose columns match the model's training schema.

    Computable features are derived from ``tx``. History-dependent features
    (velocity windows, cumulative counts, account-pair statistics) default to
    0.0 — representing a new account with no recorded prior activity.
    """
    ts = _parse_ts(tx.timestamp)
    hour = float(ts.hour) if ts else 12.0
    dow = float(ts.weekday()) if ts else 0.0
    is_weekend = 1.0 if dow >= 5 else 0.0
    is_cross_bank = 0.0 if str(tx.from_bank) == str(tx.to_bank) else 1.0

    payment_enc = _enc(tx.payment_format, PAYMENT_TYPE_MAP)
    currency_enc = _enc(tx.currency, CURRENCY_MAP)
    source_bank_enc = _bank_enc(tx.from_bank)
    target_bank_enc = _bank_enc(tx.to_bank)

    # Account IDs: -1 matches what LabelEncoder assigns to unseen accounts.
    # A production feature-store would look up trained codes instead.
    source_account_enc = -1.0
    target_account_enc = -1.0

    # sweep_ratio = amount / (avg_historical_outflow + ε).
    # No history → treat as account's first transaction (ratio = 1.0).
    sweep_ratio = 1.0

    feature_map: dict[str, float] = {
        # ── base ─────────────────────────────────────────────────────────────
        "amount":               float(tx.amount),
        "currency_enc":         currency_enc,
        "payment_type_enc":     payment_enc,
        "source_bank_enc":      source_bank_enc,
        "target_bank_enc":      target_bank_enc,
        "source_account_enc":   source_account_enc,
        "target_account_enc":   target_account_enc,
        "is_cross_bank":        is_cross_bank,
        "cross_bank_flow_flag": is_cross_bank,
        "hour":                 hour,
        "day_of_week":          dow,
        "is_weekend":           is_weekend,
        # ── cumulative history (0 = first-time context) ───────────────────
        "source_out_tx_count_total_before":   0.0,
        "source_out_amount_sum_total_before":  0.0,
        "source_unique_targets_total_before":  0.0,
        "target_in_tx_count_total_before":     0.0,
        "target_in_amount_sum_total_before":   0.0,
        "target_unique_sources_total_before":  0.0,
        "account_pair_tx_count_before":        0.0,
        "account_pair_amount_sum_before":      0.0,
        # ── velocity windows (0 = no prior activity in window) ────────────
        "source_out_tx_count_1h":   0.0,
        "source_out_amount_sum_1h":  0.0,
        "target_in_tx_count_1h":     0.0,
        "target_in_amount_sum_1h":   0.0,
        "source_out_tx_count_24h":   0.0,
        "source_out_amount_sum_24h":  0.0,
        "target_in_tx_count_24h":    0.0,
        "target_in_amount_sum_24h":   0.0,
        # ── mule-pattern derived ─────────────────────────────────────────
        "fan_in_score":        0.0,
        "fan_out_score":       0.0,
        "sweep_ratio":         sweep_ratio,
        "rapid_movement_flag": 0.0,
        # ── graph_features.py schema aliases (if model trained on those) ──
        "hour_of_day":            hour,
        "same_bank_transfer":     1.0 - is_cross_bank,
        "cross_bank_transfer":    is_cross_bank,
        "from_bank_id":           source_bank_enc,
        "to_bank_id":             target_bank_enc,
        "payment_format_code":    payment_enc,
        "payment_currency_code":  currency_enc,
        "source_out_degree":      0.0,
        "source_in_degree":       0.0,
        "target_out_degree":      0.0,
        "target_in_degree":       0.0,
        "source_total_sent":      0.0,
        "source_total_received":  0.0,
        "target_total_sent":      0.0,
        "target_total_received":  0.0,
        "velocity_count_1h":      0.0,
        "velocity_amount_1h":     0.0,
        "unique_targets_24h":     0.0,
        "unique_sources_24h":     0.0,
        "fan_in_score_ratio":     0.0,
        "fan_out_score_ratio":    0.0,
        "gather_scatter_score":   0.0,
        "scatter_gather_score":   0.0,
    }

    row = {col: feature_map.get(col, 0.0) for col in feature_columns}
    return pd.DataFrame([row], dtype="float64")


def _amount_label(amount: float) -> str:
    if amount > 200_000:
        return "XLarge (>200k)"
    if amount > 50_000:
        return "Large (>50k)"
    if amount > 10_000:
        return "Medium (>10k)"
    if amount > 1_000:
        return "Small (>1k)"
    return "Micro (<1k)"


def _explain(
    tx: TransactionIn,
    risk: float,
    features: dict[str, float],
    threshold: float,
) -> list[str]:
    """Produce PII-free, human-readable explanations for the risk score.

    Account IDs are never included. Reasons reference only structural features.
    """
    reasons: list[str] = []

    amt = tx.amount
    amt_label = _amount_label(amt)
    if amt > 10_000:
        reasons.append(f"Transaction amount: {amt_label}")

    if features.get("is_cross_bank", 0.0) > 0:
        reasons.append("Cross-bank transfer (source and destination bank differ)")

    hour = int(features.get("hour", features.get("hour_of_day", 12.0)))
    if hour < 6 or hour >= 22:
        reasons.append(f"Off-hours transaction (hour {hour:02d}:xx)")

    if features.get("is_weekend", 0.0) > 0:
        reasons.append("Weekend transaction")

    pmt = tx.payment_format or ""
    if pmt in _HIGH_RISK_PAYMENT_TYPES:
        reasons.append(f"High-risk payment type: {pmt}")
    elif pmt in _MEDIUM_RISK_PAYMENT_TYPES:
        reasons.append(f"Medium-risk payment type: {pmt} (common in cross-border layering)")

    if risk >= threshold:
        reasons.append(
            f"Risk score {risk:.4f} meets or exceeds detection threshold {threshold:.4f}"
        )

    reasons.append(
        "Velocity and cumulative features unavailable (no account history provided); "
        "model scored from transaction attributes only — result may be conservative"
    )
    return reasons


def score(tx: TransactionIn) -> ScoreOut:
    """Run real model inference for a single transaction.

    Falls back to the heuristic scorer if the model bundle is unavailable.
    Response never contains raw account IDs or PII.
    """
    bundle = model_service.get_bundle()

    if bundle is None:
        risk = min(1.0, tx.amount / 50_000)
        prediction = "block" if risk > 0.9 else "suspicious" if risk > 0.5 else "benign"
        return ScoreOut(
            risk_score=round(risk, 4),
            prediction=prediction,
            reasons=["Fallback heuristic — model bundle not loaded"],
            pattern_hash=None,
            zero_pii=True,
            source="fallback",
        )

    model = bundle["model"]
    feature_columns: list[str] = bundle.get("feature_columns") or []
    threshold = float(bundle.get("threshold", 0.5))

    if not feature_columns:
        logger.warning("Bundle has no feature_columns — heuristic fallback.")
        risk = min(1.0, tx.amount / 50_000)
        prediction = "block" if risk > 0.9 else "suspicious" if risk > 0.5 else "benign"
        return ScoreOut(
            risk_score=round(risk, 4),
            prediction=prediction,
            reasons=["Fallback heuristic — feature schema missing from bundle"],
            pattern_hash=None,
            zero_pii=True,
            source="fallback",
        )

    X = build_feature_vector(tx, feature_columns)

    try:
        if hasattr(model, "predict_proba"):
            raw_risk = float(model.predict_proba(X.to_numpy())[0, 1])
        else:
            raw_risk = float(model.decision_function(X.to_numpy())[0])
            raw_risk = float(1.0 / (1.0 + np.exp(-raw_risk)))
    except Exception as exc:
        logger.exception("Model inference failed: %s", exc)
        risk = min(1.0, tx.amount / 50_000)
        return ScoreOut(
            risk_score=round(risk, 4),
            prediction="suspicious" if risk > 0.5 else "benign",
            reasons=[f"Model inference error ({type(exc).__name__}) — heuristic fallback"],
            pattern_hash=None,
            zero_pii=True,
            source="fallback",
        )

    risk = float(np.clip(raw_risk, 0.0, 1.0))
    prediction: str
    if risk >= threshold:
        prediction = "block"
    elif risk >= threshold * 0.5:
        prediction = "suspicious"
    else:
        prediction = "benign"

    features_dict = dict(zip(feature_columns, X.iloc[0].tolist()))
    reasons = _explain(tx, risk, features_dict, threshold)

    # Zero-PII pattern hash for this single transaction's topology.
    finding: dict[str, Any] = {
        "pattern_type": "single_transaction",
        "risk_score": risk,
        "features": {
            "amount": tx.amount,
            "is_cross_bank": int(features_dict.get("is_cross_bank", 0.0)),
            "payment_format": tx.payment_format or "unknown",
        },
    }
    normalized = privacy_service.normalize_pattern_features(finding)
    ph = privacy_service.generate_pattern_hash(normalized)

    return ScoreOut(
        risk_score=round(risk, 6),
        prediction=prediction,
        reasons=reasons,
        pattern_hash=ph,
        zero_pii=True,
        source="model",
    )
