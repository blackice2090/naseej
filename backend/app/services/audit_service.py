"""Append-only audit log (JSONL, hash-chained).

Every security-relevant action — scoring, pattern analysis, registry reads
and writes, rejections — is appended as one JSON line. Records carry only
metadata: node id, endpoint, action, decision, risk tier, pattern id/hash,
and a sanitized rejection reason. Raw transactions and PII are never logged;
the record schema has no field for them and callers pass enumerated
arguments, not payloads.

Tamper evidence: each record embeds ``prev`` (the SHA-256 of the previous
record line), forming a hash chain. ``verify_chain()`` walks the file and
reports the first break. This makes silent in-place edits detectable, not
impossible — the file is still mutable at the OS level.

Path to immutable storage (post-MVP): ship the same JSONL records to a
write-once target — object storage with a WORM/object-lock policy or a
managed ledger table — and anchor the rolling chain head externally (e.g.
daily head hash published to the regulator dashboard). The in-process format
does not need to change; only the sink does.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone

from ..core import config

_GENESIS = "0" * 64

_lock = threading.Lock()
# Last record hash per file path, so chains survive across calls without
# re-reading the file every append.
_chain_heads: dict[str, str] = {}


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _load_head(path) -> str:
    """Recover the chain head from the last line of an existing log file."""
    try:
        last = None
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                if raw.strip():
                    last = raw.strip()
        return _line_hash(last) if last else _GENESIS
    except FileNotFoundError:
        return _GENESIS


def record(
    *,
    node_id: str | None,
    endpoint: str,
    action: str,
    decision: str,
    risk_tier: str | None = None,
    pattern_id: str | None = None,
    pattern_hash: str | None = None,
    reason: str | None = None,
) -> dict:
    """Append one audit record and return it.

    The returned dict carries one extra, non-persisted key: ``ref`` — the
    SHA-256 of the written line (i.e. the new chain head). Callers such as
    the case service store this ref to link a case to its audit records.
    """
    path = config.audit_log_path()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "node_id": node_id,
        "endpoint": endpoint,
        "action": action,
        "decision": decision,
        "risk_tier": risk_tier,
        "pattern_id": pattern_id,
        "pattern_hash": pattern_hash,
        "reason": reason,
    }
    with _lock:
        key = str(path)
        if key not in _chain_heads:
            _chain_heads[key] = _load_head(path)
        entry["prev"] = _chain_heads[key]
        line = json.dumps(entry, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        ref = _line_hash(line)
        _chain_heads[key] = ref
    # Attached after serialization on purpose: the ref is the hash OF the
    # line, so it cannot be stored inside it.
    entry["ref"] = ref
    return entry


def verify_chain(path=None) -> tuple[bool, int, str | None]:
    """Walk the log and check hash-chain integrity.

    Returns (ok, records_checked, first_error). A missing file is a valid
    empty chain.
    """
    path = path or config.audit_log_path()
    prev = _GENESIS
    count = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    return False, count, f"line {lineno}: not valid JSON"
                if entry.get("prev") != prev:
                    return False, count, f"line {lineno}: chain break"
                prev = _line_hash(raw)
                count += 1
    except FileNotFoundError:
        return True, 0, None
    return True, count, None
