"""Append-only audit log tests — JSONL records, hash chain, no PII.

Run from repo root:
    pytest backend/tests/test_audit_service.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core import config
from backend.app.services import audit_service


def _read_lines() -> list[dict]:
    path = config.audit_log_path()
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _record(**overrides) -> dict:
    base = dict(
        node_id="NODE_A7C2F9E1",
        endpoint="/api/patterns",
        action="pattern_register",
        decision="accepted",
        risk_tier="high",
        pattern_id="7f3c9a1e-2b4d-4e8f-9a6c-1d5e8b3f7a20",
        pattern_hash="NSJ_MULE_VELOCITY_8f9b2c4d1e7a3c5d",
    )
    base.update(overrides)
    return audit_service.record(**base)


class TestRecordWriting:
    def test_record_is_appended_as_jsonl(self):
        _record()
        lines = _read_lines()
        assert len(lines) == 1
        assert lines[0]["action"] == "pattern_register"
        assert lines[0]["decision"] == "accepted"

    def test_records_accumulate_append_only(self):
        _record()
        _record(decision="rejected", reason="x")
        _record(action="pattern_list", decision="served")
        assert len(_read_lines()) == 3

    def test_record_fields_are_metadata_only(self):
        _record(reason="$.evidence_summary: contains iban-like token")
        entry = _read_lines()[0]
        # The record schema is closed: only these fields can ever appear,
        # so raw transactions / PII have no place to live.
        assert set(entry.keys()) == {
            "ts", "node_id", "endpoint", "action", "decision",
            "risk_tier", "pattern_id", "pattern_hash", "reason", "prev",
        }

    def test_timestamp_is_utc_iso(self):
        entry = _record()
        assert entry["ts"].endswith("+00:00") or entry["ts"].endswith("Z")


class TestHashChain:
    def test_first_record_links_to_genesis(self):
        _record()
        assert _read_lines()[0]["prev"] == "0" * 64

    def test_chain_verifies_clean(self):
        for _ in range(3):
            _record()
        ok, count, err = audit_service.verify_chain()
        assert ok and count == 3 and err is None

    def test_missing_file_is_valid_empty_chain(self):
        ok, count, err = audit_service.verify_chain()
        assert ok and count == 0

    def test_tampered_line_breaks_chain(self):
        for _ in range(3):
            _record()
        path = config.audit_log_path()
        lines = path.read_text(encoding="utf-8").splitlines()
        doctored = json.loads(lines[1])
        doctored["decision"] = "accepted-after-the-fact"
        lines[1] = json.dumps(doctored, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, count, err = audit_service.verify_chain()
        assert not ok
        assert "chain break" in err

    def test_chain_survives_across_head_cache_reset(self):
        """Simulates a process restart: head is recovered from the file."""
        _record()
        audit_service._chain_heads.clear()
        _record()
        ok, count, err = audit_service.verify_chain()
        assert ok and count == 2, err
