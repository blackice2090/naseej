"""Privacy-preserving pattern hash engine (Phase 6).

A pattern hash is a deterministic, PII-free fingerprint of an AML behavioural
topology. Different banks observing the same underlying laundering scheme will
produce matching hashes — enabling cross-institution detection without
exchanging raw transaction rows or account identifiers.

Hash format
-----------
    NSJ_<PATTERN_TYPE>_<16-hex-chars>

Design invariants
-----------------
1. **No raw identifiers** — account IDs, names, IBANs, phones are stripped.
2. **Bucketed continuous values** — amounts and tx-counts are mapped to ordered
   tiers so minor bank-to-bank differences don't split a matching hash.
3. **Canonical serialisation** — sorted JSON keys ensure identical payloads
   produce identical bytes before hashing.
4. **Topology-only** — the hash encodes structural shape (node count, edge
   count, degree sequence, pattern type) not the identities of the parties.

Usage
-----
    from ml.src import privacy_hash, pattern_library

    findings = pattern_library.run_all(df)
    for f in findings:
        clean = privacy_hash.normalize_pattern_features(f)
        h = privacy_hash.generate_pattern_hash(clean)
        assert privacy_hash.verify_zero_pii(clean)
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

# ---------------------------------------------------------------------------
# PII field registry — any key matching these (case-insensitive) is stripped.
# ---------------------------------------------------------------------------

PII_FIELDS: frozenset[str] = frozenset({
    "name", "full_name", "first_name", "last_name",
    "iban", "bban", "sort_code", "routing_number",
    "national_id", "national_number", "ssn", "tin",
    "phone", "mobile", "telephone",
    "email", "email_address",
    "account_id", "from_account", "to_account", "raw_id",
    "src_id", "dst_id",
    "passport", "driver_license",
    "ip_address", "device_id", "mac_address",
    "dob", "date_of_birth",
})

# ---------------------------------------------------------------------------
# Value bucketing helpers
# ---------------------------------------------------------------------------

_AMOUNT_TIERS: list[tuple[float, str]] = [
    (1_000.0,   "micro"),    # 0 – 1 k
    (10_000.0,  "small"),    # 1 k – 10 k
    (50_000.0,  "medium"),   # 10 k – 50 k
    (200_000.0, "large"),    # 50 k – 200 k
    (math.inf,  "xlarge"),   # > 200 k
]

_COUNT_TIERS: list[tuple[int, str]] = [
    (2,   "single"),     # 1–2 transactions / nodes
    (5,   "few"),        # 3–5
    (15,  "moderate"),   # 6–15
    (50,  "high"),       # 16–50
    (999_999, "extreme"),# > 50
]

_TIME_TIERS: list[tuple[float, str]] = [
    (60.0,        "rapid"),     # ≤ 1 min
    (3_600.0,     "within_1h"), # ≤ 1 h
    (86_400.0,    "same_day"),  # ≤ 24 h
    (604_800.0,   "weekly"),    # ≤ 7 d
    (math.inf,    "extended"),  # > 7 d
]

_RISK_TIERS: list[tuple[float, str]] = [
    (0.4, "low"),
    (0.7, "medium"),
    (0.9, "high"),
    (1.0, "critical"),
]


def _bucket(value: float, tiers: list[tuple[float, str]]) -> str:
    for threshold, label in tiers:
        if value <= threshold:
            return label
    return tiers[-1][1]


def bucket_amount(amount: float) -> str:
    return _bucket(float(amount), _AMOUNT_TIERS)


def bucket_count(n: int) -> str:
    return _bucket(float(n), _COUNT_TIERS)


def bucket_time_seconds(seconds: float) -> str:
    return _bucket(float(seconds), _TIME_TIERS)


def bucket_risk(score: float) -> str:
    return _bucket(float(score), _RISK_TIERS)


# ---------------------------------------------------------------------------
# PII removal
# ---------------------------------------------------------------------------

def remove_pii_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of *payload* with all PII-keyed entries removed.

    Keys are matched case-insensitively against `PII_FIELDS`.  Values that are
    themselves dicts are cleaned recursively; list elements that are dicts are
    cleaned element-wise.
    """
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if k.lower() in PII_FIELDS:
            continue
        if isinstance(v, dict):
            v = remove_pii_fields(v)
        elif isinstance(v, list):
            v = [remove_pii_fields(i) if isinstance(i, dict) else i for i in v]
        out[k] = v
    return out


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_FEATURE_ID_KEYS: frozenset[str] = frozenset({
    "target", "source", "account", "collector",
    "hub", "node", "entity", "actor",
})


def normalize_pattern_features(finding: dict[str, Any]) -> dict[str, Any]:
    """Convert a pattern-library finding into a canonical, PII-free descriptor.

    Continuous values are bucketed so that structurally equivalent patterns
    from different banks (with different absolute amounts) hash identically.

    Input format (from ``pattern_library``):
        {
            "pattern_type": str,
            "risk_score": float,
            "reason": str,
            "accounts_involved": list,   # ← stripped (raw IDs)
            "features": {…}              # bucketed; id-keys stripped
        }

    Returns a dict suitable for ``generate_pattern_hash``.
    """
    finding = remove_pii_fields(finding)
    ptype = str(finding.get("pattern_type", "unknown"))
    risk_score = float(finding.get("risk_score", 0.0))
    raw_feats: dict[str, Any] = finding.get("features", {})

    bucketed_feats: dict[str, Any] = {}
    for key, val in raw_feats.items():
        # Strip PII field names and known account-ID semantic keys.
        if key.lower() in PII_FIELDS or key.lower() in _FEATURE_ID_KEYS:
            continue
        if isinstance(val, float) and ("amount" in key or "total" in key or "sum" in key):
            bucketed_feats[key] = bucket_amount(val)
        elif isinstance(val, (int, float)) and (
            "count" in key or "degree" in key or "n_" in key
            or "sources" in key or "targets" in key or "inflows" in key
            or "legs" in key or "length" in key
        ):
            bucketed_feats[key] = bucket_count(int(val))
        elif isinstance(val, (int, float)) and "minute" in key:
            bucketed_feats[key] = bucket_time_seconds(float(val) * 60)
        elif isinstance(val, (int, float)) and "ratio" in key:
            # Keep ratios as two-decimal rounded floats — low entropy but useful.
            bucketed_feats[key] = round(float(val), 2)
        elif isinstance(val, list):
            # Bank ID lists (in_banks, out_banks) are non-PII topology info.
            bucketed_feats[key] = sorted(int(b) for b in val if isinstance(b, (int, float)))
        else:
            # Non-numeric or unknown fields: stringify safely.
            bucketed_feats[key] = val if isinstance(val, (str, bool)) else str(val)

    # accounts_involved and id-keyed features are excluded; only shape remains.
    normalized = {
        "pattern_type": ptype,
        "risk_tier": bucket_risk(risk_score),
        "features": bucketed_feats,
    }
    return normalized


# ---------------------------------------------------------------------------
# Hash generation
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes with sorted keys."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def generate_pattern_hash(
    pattern_features: dict[str, Any],
    *,
    salt: str = "naseej-v1",
) -> str:
    """Produce a deterministic NSJ pattern hash from normalised features.

    Two calls with structurally equivalent (bucketed, PII-free) dicts will
    return the same hash string, regardless of which bank's raw data produced
    them.

    Parameters
    ----------
    pattern_features:
        Output of ``normalize_pattern_features``.
    salt:
        Version-pinned salt so hashes from different Naseej protocol versions
        don't accidentally collide.  Change this when the normalisation schema
        changes.

    Returns
    -------
    str
        Format: ``NSJ_<PATTERN_TYPE_UPPER>_<16-hex-chars>``
    """
    ptype = str(pattern_features.get("pattern_type", "unknown")).upper()
    payload = dict(pattern_features)
    payload["_salt"] = salt
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()[:16]
    return f"NSJ_{ptype}_{digest}"


def generate_topology_signature(
    edges: list[tuple[Any, Any, float]],
    *,
    salt: str = "naseej-topo-v1",
) -> str:
    """Hash a graph's structural topology without encoding node identities.

    Parameters
    ----------
    edges:
        List of (src, dst, amount) tuples.  Node labels are anonymised —
        only the degree sequence and bucketed edge weights are hashed.

    Returns
    -------
    str
        Format: ``NSJ_TOPO_<16-hex-chars>``
    """
    # Build degree sequences from edge list — no node IDs retained.
    out_degree: dict[Any, int] = {}
    in_degree: dict[Any, int] = {}
    for src, dst, _ in edges:
        out_degree[src] = out_degree.get(src, 0) + 1
        in_degree[dst] = in_degree.get(dst, 0) + 1

    all_nodes = set(out_degree) | set(in_degree)
    degree_seq = sorted(
        (out_degree.get(n, 0), in_degree.get(n, 0)) for n in all_nodes
    )
    bucketed_amounts = sorted(bucket_amount(a) for _, _, a in edges)

    topo = {
        "n_nodes": bucket_count(len(all_nodes)),
        "n_edges": bucket_count(len(edges)),
        "degree_sequence": degree_seq,
        "amount_buckets": bucketed_amounts,
        "_salt": salt,
    }
    digest = hashlib.sha256(_canonical_json(topo)).hexdigest()[:16]
    return f"NSJ_TOPO_{digest}"


# ---------------------------------------------------------------------------
# Zero-PII verification
# ---------------------------------------------------------------------------

def verify_zero_pii(payload: dict[str, Any], *, _depth: int = 0) -> bool:
    """Return True iff *payload* (recursively) contains no PII-keyed fields.

    Raises ``ValueError`` if the recursion depth exceeds 10 (guards against
    circular or pathologically deep structures).
    """
    if _depth > 10:
        raise ValueError("verify_zero_pii: payload nesting exceeds depth limit (10).")
    for k, v in payload.items():
        if k.lower() in PII_FIELDS:
            return False
        if isinstance(v, dict) and not verify_zero_pii(v, _depth=_depth + 1):
            return False
        if isinstance(v, list):
            for item in v:
                if isinstance(item, dict) and not verify_zero_pii(item, _depth=_depth + 1):
                    return False
    return True


# ---------------------------------------------------------------------------
# Zero-PII report (for the dashboard explainability panel)
# ---------------------------------------------------------------------------

def pii_audit_report(
    original: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any]:
    """Return a human-readable audit comparing the original finding to the
    normalised, PII-free version — useful for the Phase 8 explainability panel.
    """
    stripped_keys: list[str] = []
    bucketed_fields: list[dict[str, Any]] = []

    # Keys present in original but absent in normalised
    def _collect(orig: dict, norm: dict, prefix: str = "") -> None:
        for k in orig:
            fk = f"{prefix}{k}" if prefix else k
            if k not in norm:
                if k.lower() in PII_FIELDS:
                    stripped_keys.append(fk)
            else:
                if (
                    isinstance(orig[k], (int, float))
                    and isinstance(norm.get(k), str)
                ):
                    bucketed_fields.append(
                        {"field": fk, "original": orig[k], "bucketed": norm[k]}
                    )
                elif isinstance(orig[k], dict) and isinstance(norm.get(k), dict):
                    _collect(orig[k], norm[k], prefix=f"{fk}.")

    _collect(original, normalized)

    return {
        "zero_pii": verify_zero_pii(normalized),
        "stripped_pii_keys": stripped_keys,
        "bucketed_fields": bucketed_fields,
        "pattern_hash": generate_pattern_hash(normalized) if "pattern_type" in normalized else None,
        "note": (
            "accounts_involved removed; continuous values bucketed into tiers. "
            "The pattern hash encodes topology shape, not individual identities."
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "PII_FIELDS",
    "bucket_amount",
    "bucket_count",
    "bucket_time_seconds",
    "bucket_risk",
    "remove_pii_fields",
    "normalize_pattern_features",
    "generate_pattern_hash",
    "generate_topology_signature",
    "verify_zero_pii",
    "pii_audit_report",
]
