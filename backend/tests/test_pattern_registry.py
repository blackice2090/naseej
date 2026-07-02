"""Threat Pattern Registry endpoint tests — auth, schema gate, zero-PII
guard, duplicates, audit trail.

Run from repo root:
    pytest backend/tests/test_pattern_registry.py -v
"""

from __future__ import annotations

import copy
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.app.core import config
from backend.app.main import app

client = TestClient(app)

KEY_A = {"X-API-Key": "dev-key-bank-a-local-only"}   # → NODE_A7C2F9E1
KEY_B = {"X-API-Key": "dev-key-bank-b-local-only"}   # → NODE_B3D8E2F4

# The canonical example from docs/THREAT_PATTERN_CONTRACT.md.
VALID_PATTERN = {
    "pattern_id": "7f3c9a1e-2b4d-4e8f-9a6c-1d5e8b3f7a20",
    "pattern_hash": "NSJ_MULE_VELOCITY_8f9b2c4d1e7a3c5d",
    "typology": "mule_velocity",
    "graph_signature": {
        "node_count": 7,
        "edge_count": 6,
        "in_degree_sequence": [0, 0, 0, 0, 0, 1, 5],
        "out_degree_sequence": [0, 0, 1, 1, 1, 1, 2],
        "diameter": 2,
        "is_cross_bank": True,
    },
    "velocity_features": {
        "window_bucket": "under_1h",
        "tx_count_bucket": "2_to_5",
        "amount_bucket": "5k_to_25k",
        "burst_score_bucket": "high",
    },
    "risk_score": 0.91,
    "confidence": 0.87,
    "detection_timestamp": "2026-06-11T09:42:00Z",
    "source_node_id": "NODE_A7C2F9E1",
    "evidence_summary": (
        "Fan-in of 5 sub-threshold transfers into a single account within "
        "40 minutes, followed by an international wire sweep of the "
        "accumulated balance."
    ),
    "privacy_guarantees": {
        "zero_pii_verified": True,
        "bucketing_version": "buckets-v1",
        "hash_algorithm": "sha256-canonical-json-v1",
        "k_anonymity_floor": 5,
    },
    "governance_tags": {
        "sharing_scope": "network_all",
        "retention_days": 90,
        "requires_human_review": True,
        "regulatory_basis": "SAMA-CFF-early-warning",
    },
}


def fresh_pattern(**overrides) -> dict:
    p = copy.deepcopy(VALID_PATTERN)
    p["pattern_id"] = str(uuid.uuid4())
    p.update(overrides)
    return p


def _audit_entries() -> list[dict]:
    path = config.audit_log_path()
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Happy path ─────────────────────────────────────────────────────────────


class TestRegisterAndFetch:
    def test_valid_pattern_accepted_201(self):
        resp = client.post("/api/patterns", json=fresh_pattern(), headers=KEY_A)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["accepted"] is True
        assert "registered_at" in body

    def test_contract_doc_example_is_valid(self):
        resp = client.post("/api/patterns", json=copy.deepcopy(VALID_PATTERN), headers=KEY_A)
        assert resp.status_code == 201, resp.text

    def test_list_returns_registered_patterns(self):
        p = fresh_pattern()
        client.post("/api/patterns", json=p, headers=KEY_A)
        resp = client.get("/api/patterns", headers=KEY_B)
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["patterns"][0]["pattern"]["pattern_id"] == p["pattern_id"]
        assert body["patterns"][0]["registered_by"] == "NODE_A7C2F9E1"

    def test_list_filters_by_typology(self):
        client.post("/api/patterns", json=fresh_pattern(), headers=KEY_A)
        resp = client.get("/api/patterns", params={"typology": "fan_out"}, headers=KEY_A)
        assert resp.json()["count"] == 0
        resp = client.get("/api/patterns", params={"typology": "mule_velocity"}, headers=KEY_A)
        assert resp.json()["count"] == 1

    def test_get_by_id(self):
        p = fresh_pattern()
        client.post("/api/patterns", json=p, headers=KEY_A)
        resp = client.get(f"/api/patterns/{p['pattern_id']}", headers=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["pattern"]["pattern_hash"] == p["pattern_hash"]

    def test_get_unknown_id_404(self):
        resp = client.get(f"/api/patterns/{uuid.uuid4()}", headers=KEY_A)
        assert resp.status_code == 404

    def test_node_b_can_register_its_own_pattern(self):
        p = fresh_pattern(source_node_id="NODE_B3D8E2F4")
        resp = client.post("/api/patterns", json=p, headers=KEY_B)
        assert resp.status_code == 201, resp.text

    def test_registry_persists_across_reload(self):
        from backend.app.services.registry_service import PatternRegistry

        p = fresh_pattern()
        client.post("/api/patterns", json=p, headers=KEY_A)
        reloaded = PatternRegistry(config.registry_path())
        assert reloaded.get(p["pattern_id"]) is not None


# ── Schema gate ────────────────────────────────────────────────────────────


class TestSchemaGate:
    def test_extra_field_rejected(self):
        p = fresh_pattern()
        p["internal_note"] = "anything"
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 422
        assert any("unexpected field" in r for r in resp.json()["detail"]["reasons"])

    def test_pii_named_extra_field_rejected(self):
        for field in ("name", "iban", "account_number", "national_id",
                      "phone", "email", "raw_transaction", "device_id"):
            p = fresh_pattern()
            p[field] = "x"
            resp = client.post("/api/patterns", json=p, headers=KEY_A)
            assert resp.status_code == 422, f"'{field}' field must be rejected"

    def test_nested_extra_field_rejected(self):
        p = fresh_pattern()
        p["graph_signature"]["account_hint"] = "x"
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 422

    def test_missing_required_field_rejected(self):
        p = fresh_pattern()
        del p["privacy_guarantees"]
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 422
        assert any("privacy_guarantees" in r for r in resp.json()["detail"]["reasons"])

    def test_bad_hash_format_rejected(self):
        p = fresh_pattern(pattern_hash="0x8F9B2C_NASEEJ_PATTERN")
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 422

    def test_bad_uuid_rejected(self):
        p = fresh_pattern(pattern_id="not-a-uuid")
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 422

    def test_unknown_typology_rejected(self):
        p = fresh_pattern(typology="watering_hole")
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 422

    def test_unverified_privacy_attestation_rejected(self):
        p = fresh_pattern()
        p["privacy_guarantees"]["zero_pii_verified"] = False
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 422

    def test_rejection_reasons_never_echo_values(self):
        p = fresh_pattern(pattern_hash="SECRET_VALUE_THAT_MUST_NOT_LEAK")
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 422
        assert "SECRET_VALUE_THAT_MUST_NOT_LEAK" not in resp.text


# ── Zero-PII content guard ─────────────────────────────────────────────────


class TestZeroPiiGuard:
    def _post_with_summary(self, summary: str):
        return client.post(
            "/api/patterns", json=fresh_pattern(evidence_summary=summary), headers=KEY_A
        )

    def test_arabic_name_in_summary_rejected(self):
        resp = self._post_with_summary("Funds moved by محمد العتيبي to external account")
        assert resp.status_code == 422

    def test_iban_in_summary_rejected(self):
        resp = self._post_with_summary("Swept to SA4420000001234567891234 in one wire")
        assert resp.status_code == 422

    def test_phone_in_summary_rejected(self):
        resp = self._post_with_summary("Linked to mobile +966512345678")
        assert resp.status_code == 422

    def test_account_handle_in_summary_rejected(self):
        resp = self._post_with_summary("Pattern centred on ACC_MULE_SA_001")
        assert resp.status_code == 422

    def test_guard_reason_names_rule_not_value(self):
        resp = self._post_with_summary("Swept to SA4420000001234567891234 in one wire")
        reasons = resp.json()["detail"]["reasons"]
        assert any("iban-like" in r for r in reasons)
        assert all("SA44" not in r for r in reasons)


# ── Integrity rules ────────────────────────────────────────────────────────


class TestIntegrityRules:
    def test_spoofed_source_node_is_403(self):
        p = fresh_pattern(source_node_id="NODE_B3D8E2F4")
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 403

    def test_duplicate_pattern_id_is_409(self):
        p = fresh_pattern()
        assert client.post("/api/patterns", json=p, headers=KEY_A).status_code == 201
        resp = client.post("/api/patterns", json=p, headers=KEY_A)
        assert resp.status_code == 409


# ── Audit trail ────────────────────────────────────────────────────────────


class TestAuditTrail:
    def test_accepted_registration_is_audited(self):
        p = fresh_pattern()
        client.post("/api/patterns", json=p, headers=KEY_A)
        entries = _audit_entries()
        accepted = [e for e in entries if e["decision"] == "accepted"]
        assert len(accepted) == 1
        assert accepted[0]["node_id"] == "NODE_A7C2F9E1"
        assert accepted[0]["pattern_id"] == p["pattern_id"]
        assert accepted[0]["risk_tier"] == "critical"

    def test_rejection_is_audited_with_sanitized_reason(self):
        client.post(
            "/api/patterns",
            json=fresh_pattern(evidence_summary="IBAN SA4420000001234567891234"),
            headers=KEY_A,
        )
        rejected = [e for e in _audit_entries() if e["decision"] == "rejected"]
        assert len(rejected) == 1
        assert "iban-like" in rejected[0]["reason"]
        assert "SA44" not in rejected[0]["reason"]

    def test_reads_are_audited(self):
        client.get("/api/patterns", headers=KEY_A)
        p = fresh_pattern()
        client.post("/api/patterns", json=p, headers=KEY_A)
        client.get(f"/api/patterns/{p['pattern_id']}", headers=KEY_B)
        actions = [e["action"] for e in _audit_entries()]
        assert "pattern_list" in actions
        assert "pattern_get" in actions

    def test_unauthenticated_requests_never_reach_audit_or_registry(self):
        client.post("/api/patterns", json=fresh_pattern())
        assert _audit_entries() == []
        assert client.get("/api/patterns", headers=KEY_A).json()["count"] == 0
