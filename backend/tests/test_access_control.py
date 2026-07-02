"""Multi-bank access partitioning + role-based case governance tests.

Covers: node identity / whoami, pattern sharing scopes (local_only,
bilateral, network_all, regulator_only), case ownership and visibility,
role-based decision permissions, role-header validation, body-role
ignorance, and audit coverage of every denial.

Run from repo root:
    pytest backend/tests/test_access_control.py -v
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

KEY_A = {"X-API-Key": "dev-key-bank-a-local-only"}     # NODE_A7C2F9E1, analyst
KEY_B = {"X-API-Key": "dev-key-bank-b-local-only"}     # NODE_B3D8E2F4, mlro
KEY_REG = {"X-API-Key": "dev-key-regulator-local-only"}  # NODE_REG5C7A1, regulator

NODE_A = "NODE_A7C2F9E1"
NODE_B = "NODE_B3D8E2F4"

BASE_PATTERN = {
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
    "source_node_id": NODE_A,
    "evidence_summary": (
        "Fan-in of 5 sub-threshold transfers into a single account within "
        "40 minutes, followed by an international wire sweep."
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


def register(headers, *, scope="network_all", shared_with=None, **overrides) -> str:
    p = copy.deepcopy(BASE_PATTERN)
    p["pattern_id"] = str(uuid.uuid4())
    p["governance_tags"]["sharing_scope"] = scope
    if shared_with is not None:
        p["governance_tags"]["shared_with_node_ids"] = shared_with
    p.update(overrides)
    resp = client.post("/api/patterns", json=p, headers=headers)
    assert resp.status_code == 201, resp.text
    return p["pattern_id"]


def create_case(headers, pattern_id: str) -> dict:
    resp = client.post(f"/api/cases/from-pattern/{pattern_id}", headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _audit_entries() -> list[dict]:
    path = config.audit_log_path()
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Node identity & whoami ─────────────────────────────────────────────────


class TestWhoami:
    def test_bank_a_default_is_analyst(self):
        body = client.get("/api/auth/whoami", headers=KEY_A).json()
        assert body["node_id"] == NODE_A
        assert body["display_name"] == "Bank A"
        assert body["node_type"] == "bank"
        assert body["role"] == "analyst"
        assert "cases:take_under_review" in body["permissions"]
        assert "cases:confirm_fraud" not in body["permissions"]

    def test_bank_b_default_is_mlro(self):
        body = client.get("/api/auth/whoami", headers=KEY_B).json()
        assert body["role"] == "mlro"
        assert "cases:confirm_fraud" in body["permissions"]

    def test_regulator_is_read_only(self):
        body = client.get("/api/auth/whoami", headers=KEY_REG).json()
        assert body["node_type"] == "regulator"
        assert body["role"] == "regulator"
        assert "cases:view_all" in body["permissions"]
        assert not any(p.startswith("cases:") and p != "cases:view_all"
                       for p in body["permissions"])
        assert "patterns:publish" not in body["permissions"]

    def test_role_header_within_envelope_elevates(self):
        body = client.get("/api/auth/whoami",
                          headers={**KEY_A, "X-Analyst-Role": "mlro"}).json()
        assert body["role"] == "mlro"
        assert "cases:confirm_fraud" in body["permissions"]

    def test_role_header_outside_envelope_is_403_and_audited(self):
        resp = client.get("/api/auth/whoami",
                          headers={**KEY_REG, "X-Analyst-Role": "mlro"})
        assert resp.status_code == 403
        denied = [e for e in _audit_entries()
                  if e["action"] == "role_select" and e["decision"] == "denied"]
        assert len(denied) == 1
        # The header value itself is never echoed into the log.
        assert "mlro" not in (denied[0]["reason"] or "")

    def test_whoami_requires_auth(self):
        assert client.get("/api/auth/whoami").status_code == 401


# ── Pattern sharing scopes ─────────────────────────────────────────────────


class TestPatternScopes:
    def test_bank_b_cannot_see_bank_a_local_only(self):
        pid = register(KEY_A, scope="local_only")
        resp = client.get(f"/api/patterns/{pid}", headers=KEY_B)
        assert resp.status_code == 403
        assert client.get("/api/patterns", headers=KEY_B).json()["count"] == 0
        # Source node still sees its own pattern.
        assert client.get(f"/api/patterns/{pid}", headers=KEY_A).status_code == 200

    def test_bank_b_can_see_network_pattern(self):
        pid = register(KEY_A, scope="network_all")
        assert client.get(f"/api/patterns/{pid}", headers=KEY_B).status_code == 200
        assert client.get("/api/patterns", headers=KEY_B).json()["count"] == 1

    def test_bilateral_only_for_listed_nodes(self):
        pid = register(KEY_A, scope="bilateral", shared_with=[NODE_B])
        assert client.get(f"/api/patterns/{pid}", headers=KEY_B).status_code == 200
        assert client.get(f"/api/patterns/{pid}", headers=KEY_REG).status_code == 403

    def test_bilateral_without_recipients_fails_closed(self):
        pid = register(KEY_A, scope="bilateral")
        assert client.get(f"/api/patterns/{pid}", headers=KEY_B).status_code == 403

    def test_regulator_only_visible_to_regulator_not_banks(self):
        pid = register(KEY_A, scope="regulator_only")
        assert client.get(f"/api/patterns/{pid}", headers=KEY_REG).status_code == 200
        assert client.get(f"/api/patterns/{pid}", headers=KEY_B).status_code == 403

    def test_regulator_cannot_publish_patterns(self):
        p = copy.deepcopy(BASE_PATTERN)
        p["pattern_id"] = str(uuid.uuid4())
        resp = client.post("/api/patterns", json=p, headers=KEY_REG)
        assert resp.status_code == 403

    def test_unknown_scope_in_schema_rejected(self):
        p = copy.deepcopy(BASE_PATTERN)
        p["pattern_id"] = str(uuid.uuid4())
        p["governance_tags"]["sharing_scope"] = "everyone"
        assert client.post("/api/patterns", json=p, headers=KEY_A).status_code == 422

    def test_denied_pattern_get_is_audited(self):
        pid = register(KEY_A, scope="local_only")
        client.get(f"/api/patterns/{pid}", headers=KEY_B)
        denied = [e for e in _audit_entries()
                  if e["action"] == "pattern_get" and e["decision"] == "denied"]
        assert len(denied) == 1
        assert denied[0]["node_id"] == NODE_B


# ── Case ownership & visibility ────────────────────────────────────────────


class TestCasePartitioning:
    def test_case_records_ownership_fields(self):
        pid = register(KEY_A)
        case = create_case(KEY_A, pid)
        assert case["owner_node_id"] == NODE_A
        assert case["visible_to_node_ids"] == [NODE_A]
        assert case["sharing_scope"] == "network_all"

    def test_bank_a_cannot_see_bank_b_private_case(self):
        pid = register(KEY_B, scope="local_only", source_node_id=NODE_B)
        case = create_case(KEY_B, pid)
        resp = client.get(f"/api/cases/{case['case_id']}", headers=KEY_A)
        assert resp.status_code == 403
        assert client.get("/api/cases", headers=KEY_A).json()["count"] == 0
        assert client.get("/api/cases", headers=KEY_B).json()["count"] == 1

    def test_detecting_node_can_see_case_on_its_pattern(self):
        # B opens a case from A's network broadcast: both nodes may view it.
        pid = register(KEY_A, scope="network_all")
        case = create_case(KEY_B, pid)
        assert sorted(case["visible_to_node_ids"]) == sorted([NODE_A, NODE_B])
        assert client.get(f"/api/cases/{case['case_id']}", headers=KEY_A).status_code == 200

    def test_visible_non_owner_cannot_mutate(self):
        pid = register(KEY_A, scope="network_all")
        case = create_case(KEY_B, pid)  # owner B, visible to A
        resp = client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "trying to write into another bank's case"},
            headers=KEY_A,
        )
        assert resp.status_code == 403

    def test_cannot_open_case_on_invisible_pattern(self):
        pid = register(KEY_A, scope="local_only")
        resp = client.post(f"/api/cases/from-pattern/{pid}", headers=KEY_B)
        assert resp.status_code == 403

    def test_regulator_views_all_cases_read_only(self):
        pid_a = register(KEY_A, scope="local_only")
        pid_b = register(KEY_B, scope="local_only", source_node_id=NODE_B)
        case_a = create_case(KEY_A, pid_a)
        create_case(KEY_B, pid_b)
        assert client.get("/api/cases", headers=KEY_REG).json()["count"] == 2
        assert client.get(f"/api/cases/{case_a['case_id']}", headers=KEY_REG).status_code == 200
        # ...but every mutation is denied.
        assert client.post(
            f"/api/cases/{case_a['case_id']}/notes",
            json={"note": "regulator attempting to annotate"},
            headers=KEY_REG,
        ).status_code == 403
        assert client.post(
            f"/api/cases/{case_a['case_id']}/decision",
            json={"decision": "take_under_review", "reason": "oversight"},
            headers=KEY_REG,
        ).status_code == 403
        assert client.patch(
            f"/api/cases/{case_a['case_id']}/status",
            json={"new_status": "under_review", "reason": "oversight"},
            headers=KEY_REG,
        ).status_code == 403

    def test_regulator_cannot_create_cases(self):
        pid = register(KEY_A, scope="network_all")
        resp = client.post(f"/api/cases/from-pattern/{pid}", headers=KEY_REG)
        assert resp.status_code == 403

    def test_denied_case_get_is_audited(self):
        pid = register(KEY_B, scope="local_only", source_node_id=NODE_B)
        case = create_case(KEY_B, pid)
        client.get(f"/api/cases/{case['case_id']}", headers=KEY_A)
        denied = [e for e in _audit_entries()
                  if e["action"] == "case_get" and e["decision"] == "denied"]
        assert len(denied) == 1
        assert denied[0]["node_id"] == NODE_A


# ── Role-based decisions ───────────────────────────────────────────────────


class TestRoleBasedDecisions:
    def _case_owned_by_a(self) -> dict:
        return create_case(KEY_A, register(KEY_A))

    def _decide(self, case_id, decision, headers, reason="documented rationale"):
        return client.post(
            f"/api/cases/{case_id}/decision",
            json={"decision": decision, "reason": reason},
            headers=headers,
        )

    def test_analyst_can_take_under_review_and_close_no_action(self):
        case = self._case_owned_by_a()
        assert self._decide(case["case_id"], "take_under_review", KEY_A).status_code == 200
        case2 = self._case_owned_by_a()
        assert self._decide(case2["case_id"], "close_no_action", KEY_A).status_code == 200

    def test_analyst_cannot_confirm_fraud(self):
        case = self._case_owned_by_a()
        self._decide(case["case_id"], "take_under_review", KEY_A)
        resp = self._decide(case["case_id"], "confirm_fraud", KEY_A)
        assert resp.status_code == 403

    def test_analyst_cannot_escalate_or_mark_fp(self):
        case = self._case_owned_by_a()
        self._decide(case["case_id"], "take_under_review", KEY_A)
        assert self._decide(case["case_id"], "escalate", KEY_A).status_code == 403
        assert self._decide(case["case_id"], "mark_false_positive", KEY_A).status_code == 403

    def test_senior_analyst_can_escalate_and_mark_fp(self):
        senior = {**KEY_A, "X-Analyst-Role": "senior_analyst"}
        case = self._case_owned_by_a()
        self._decide(case["case_id"], "take_under_review", KEY_A)
        assert self._decide(case["case_id"], "escalate", senior).status_code == 200
        # senior still cannot confirm fraud.
        assert self._decide(case["case_id"], "confirm_fraud", senior).status_code == 403

    def test_mlro_can_confirm_fraud_after_review(self):
        pid = register(KEY_B, source_node_id=NODE_B)
        case = create_case(KEY_B, pid)  # owner B, default role mlro
        assert self._decide(case["case_id"], "take_under_review", KEY_B).status_code == 200
        resp = self._decide(case["case_id"], "confirm_fraud", KEY_B)
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed_confirmed"
        assert resp.json()["decision_history"][-1]["analyst_role"] == "mlro"

    def test_status_patch_gated_by_same_permissions(self):
        case = self._case_owned_by_a()
        resp = client.patch(
            f"/api/cases/{case['case_id']}/status",
            json={"new_status": "escalated", "reason": "needs senior review"},
            headers=KEY_A,  # analyst: escalate requires senior_analyst
        )
        assert resp.status_code == 403

    def test_body_analyst_role_is_ignored(self):
        case = self._case_owned_by_a()
        resp = client.post(
            f"/api/cases/{case['case_id']}/decision",
            json={"decision": "take_under_review", "reason": "starting review",
                  "analyst_role": "mlro"},  # ignored: role comes from context
            headers=KEY_A,
        )
        assert resp.status_code == 200
        assert resp.json()["decision_history"][0]["analyst_role"] == "analyst"

    def test_body_role_cannot_bypass_permissions(self):
        case = self._case_owned_by_a()
        self._decide(case["case_id"], "take_under_review", KEY_A)
        resp = client.post(
            f"/api/cases/{case['case_id']}/decision",
            json={"decision": "confirm_fraud", "reason": "trying to self-elevate",
                  "analyst_role": "mlro"},
            headers=KEY_A,
        )
        assert resp.status_code == 403

    def test_denied_decision_is_audited_without_payload(self):
        case = self._case_owned_by_a()
        self._decide(case["case_id"], "take_under_review", KEY_A)
        self._decide(case["case_id"], "confirm_fraud", KEY_A,
                     reason="UNIQUE_REASON_MARKER_993")
        denied = [e for e in _audit_entries()
                  if e["action"] == "case_decision" and e["decision"] == "denied"]
        assert len(denied) == 1
        assert "cases:confirm_fraud" in denied[0]["reason"]
        # Caller-supplied text never reaches the audit log on a denial.
        assert "UNIQUE_REASON_MARKER_993" not in json.dumps(_audit_entries())


# ── Audit hygiene across denials ───────────────────────────────────────────


class TestDenialAuditHygiene:
    def test_no_pii_or_payload_in_any_audit_record(self):
        # Drive several denials with marker content, then sweep the log.
        pid = register(KEY_B, scope="local_only", source_node_id=NODE_B)
        case = create_case(KEY_B, pid)
        client.get(f"/api/cases/{case['case_id']}", headers=KEY_A)
        client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "SECRET_NOTE_MARKER with IBAN SA4420000001234567891234"},
            headers=KEY_A,
        )
        log_text = json.dumps(_audit_entries())
        assert "SECRET_NOTE_MARKER" not in log_text
        assert "SA4420000001234567891234" not in log_text

    def test_every_denial_writes_an_audit_record(self):
        pid = register(KEY_A, scope="local_only")
        client.get(f"/api/patterns/{pid}", headers=KEY_B)          # scope denial
        client.post(f"/api/cases/from-pattern/{pid}", headers=KEY_B)  # create denial
        denied = [e for e in _audit_entries() if e["decision"] == "denied"]
        assert len(denied) == 2
        assert all(e["node_id"] == NODE_B for e in denied)
