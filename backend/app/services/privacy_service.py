"""Privacy / zero-PII pattern hash service (Phase 6).

Wraps ``ml.src.privacy_hash`` for use by FastAPI endpoints.  If the ML package
is unavailable for any reason the service degrades to the lightweight
placeholder so the backend never raises a 500.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── try importing the real Phase 6 engine ──────────────────────────────────
try:
    from ml.src.privacy_hash import (  # type: ignore[import]
        generate_pattern_hash as _gen_hash,
        generate_topology_signature as _gen_topo,
        normalize_pattern_features as _normalize,
        pii_audit_report as _audit,
        remove_pii_fields as _strip,
        verify_zero_pii as _verify,
    )
    _REAL_ENGINE = True
    logger.info("privacy_service: using Phase 6 ml.src.privacy_hash engine.")
except Exception as exc:
    _REAL_ENGINE = False
    logger.warning("privacy_service: ml.src.privacy_hash unavailable (%s) — using fallback.", exc)


# ── public surface used by routes ─────────────────────────────────────────


def strip_pii(payload: dict[str, Any]) -> dict[str, Any]:
    """Return *payload* with all PII-keyed entries removed (recursive)."""
    if _REAL_ENGINE:
        return _strip(payload)
    _PII = {
        "name", "iban", "national_id", "phone", "email",
        "from_account", "to_account", "account_id", "src_id", "dst_id", "raw_id",
    }
    return {k: v for k, v in payload.items() if k.lower() not in _PII}


def normalize_pattern_features(finding: dict[str, Any]) -> dict[str, Any]:
    """Return a bucketed, PII-free descriptor of a pattern-library finding."""
    if _REAL_ENGINE:
        return _normalize(finding)
    # Minimal fallback
    clean = strip_pii(finding)
    clean.pop("accounts_involved", None)
    return clean


def generate_pattern_hash(pattern: dict[str, Any]) -> str:
    """Return a deterministic NSJ pattern hash (NSJ_TYPE_<hex>)."""
    if _REAL_ENGINE:
        return _gen_hash(pattern)
    ptype = str(pattern.get("pattern_type", "unknown")).upper()
    digest = hashlib.sha256(str(sorted(pattern.items())).encode()).hexdigest()[:16]
    return f"NSJ_{ptype}_{digest}"


def generate_topology_signature(
    edges: list[tuple[Any, Any, float]],
) -> str:
    """Return a topology-only hash for a graph (no node identities)."""
    if _REAL_ENGINE:
        return _gen_topo(edges)
    digest = hashlib.sha256(str(sorted(edges)).encode()).hexdigest()[:16]
    return f"NSJ_TOPO_{digest}"


def verify_zero_pii(payload: dict[str, Any]) -> bool:
    """Return True iff *payload* contains no PII-keyed fields (recursive)."""
    if _REAL_ENGINE:
        return _verify(payload)
    _PII = {
        "name", "iban", "national_id", "phone", "email",
        "from_account", "to_account", "account_id", "src_id", "dst_id", "raw_id",
    }
    return not (_PII & {k.lower() for k in payload.keys()})


def pii_audit_report(
    original: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any]:
    """Return a human-readable audit dict for the explainability panel."""
    if _REAL_ENGINE:
        return _audit(original, normalized)
    return {
        "zero_pii": verify_zero_pii(normalized),
        "stripped_pii_keys": [],
        "bucketed_fields": [],
        "pattern_hash": generate_pattern_hash(normalized) if "pattern_type" in normalized else None,
        "note": "Phase 6 engine unavailable; fallback audit.",
    }


# ── backward-compat shim (used by routes_graph.py Phase 1 stub) ───────────

def placeholder_pattern_hash(pattern_type: str, signal: str) -> str:
    """Retained for Phase 1 callers; wraps the real engine."""
    if _REAL_ENGINE:
        return _gen_hash({"pattern_type": pattern_type, "signal_bucket": signal})
    digest = hashlib.sha256(f"{pattern_type}|{signal}".encode()).hexdigest()[:6].upper()
    return f"NSJ_{pattern_type.upper()}_{digest}"
