"""Case Management endpoint tests — lifecycle, transitions, notes, PII
rejection, append-only decision history, audit coverage.

Run from repo root:
    pytest backend/tests/test_cases.py -v
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
from backend.app.services.case_service import TRANSITIONS

client = TestClient(app)

KEY_A = {"X-API-Key": "dev-key-bank-a-local-only"}   # → NODE_A7C2F9E1 (default role: analyst)
KEY_B = {"X-API-Key": "dev-key-bank-b-local-only"}   # → NODE_B3D8E2F4 (default role: mlro)

# Role selection happens via header, validated against the node's
# allowed_roles — never via request bodies (see test_access_control.py).
KEY_A_SENIOR = {**KEY_A, "X-Analyst-Role": "senior_analyst"}
KEY_A_MLRO = {**KEY_A, "X-Analyst-Role": "mlro"}

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


def register_pattern(**overrides) -> str:
    """Register a fresh pattern; returns its pattern_id."""
    p = copy.deepcopy(VALID_PATTERN)
    p["pattern_id"] = str(uuid.uuid4())
    p.update(overrides)
    resp = client.post("/api/patterns", json=p, headers=KEY_A)
    assert resp.status_code == 201, resp.text
    return p["pattern_id"]


def create_case(**pattern_overrides) -> dict:
    pid = register_pattern(**pattern_overrides)
    resp = client.post(f"/api/cases/from-pattern/{pid}", headers=KEY_A)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _audit_entries() -> list[dict]:
    path = config.audit_log_path()
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Creation ───────────────────────────────────────────────────────────────


class TestCaseCreation:
    def test_create_from_valid_pattern(self):
        case = create_case()
        assert case["status"] == "open"
        assert case["typology"] == "mule_velocity"
        assert case["risk_tier"] == "critical"
        assert case["risk_score"] == 0.91
        assert case["false_positive_flag"] is False
        assert case["analyst_notes"] == []
        assert case["decision_history"] == []
        assert len(case["audit_refs"]) == 1

    def test_case_carries_pattern_link_only(self):
        case = create_case()
        assert case["pattern_id"]
        assert case["pattern_hash"].startswith("NSJ_")
        # No transaction or customer fields exist on a case.
        assert "transactions" not in case
        assert "accounts" not in case

    def test_recommended_action_critical_is_freeze(self):
        case = create_case(risk_score=0.95)
        assert case["recommended_action"] == "freeze_for_review"

    def test_recommended_action_high_cross_bank_escalates(self):
        case = create_case(risk_score=0.75)
        assert case["recommended_action"] == "escalate_to_compliance"

    def test_recommended_action_low_is_monitor(self):
        case = create_case(risk_score=0.2)
        assert case["recommended_action"] == "monitor"

    def test_missing_pattern_is_404(self):
        resp = client.post(f"/api/cases/from-pattern/{uuid.uuid4()}", headers=KEY_A)
        assert resp.status_code == 404

    def test_duplicate_open_case_is_409(self):
        pid = register_pattern()
        assert client.post(f"/api/cases/from-pattern/{pid}", headers=KEY_A).status_code == 201
        resp = client.post(f"/api/cases/from-pattern/{pid}", headers=KEY_A)
        assert resp.status_code == 409

    def test_requires_auth(self):
        assert client.post(f"/api/cases/from-pattern/{uuid.uuid4()}").status_code == 401


# ── Reads ──────────────────────────────────────────────────────────────────


class TestCaseReads:
    def test_list_cases(self):
        create_case()
        create_case()
        resp = client.get("/api/cases", headers=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_list_filters_by_status(self):
        create_case()
        resp = client.get("/api/cases", params={"status": "open"}, headers=KEY_A)
        assert resp.json()["count"] == 1
        resp = client.get("/api/cases", params={"status": "escalated"}, headers=KEY_A)
        assert resp.json()["count"] == 0

    def test_get_case(self):
        case = create_case()
        resp = client.get(f"/api/cases/{case['case_id']}", headers=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["case_id"] == case["case_id"]

    def test_get_unknown_case_404(self):
        assert client.get(f"/api/cases/{uuid.uuid4()}", headers=KEY_A).status_code == 404

    def test_reads_require_auth(self):
        assert client.get("/api/cases").status_code == 401


# ── Status transitions ─────────────────────────────────────────────────────


class TestStatusTransitions:
    def _patch(self, case_id: str, new_status: str, headers=KEY_A):
        return client.patch(
            f"/api/cases/{case_id}/status",
            json={"new_status": new_status, "reason": "routine triage step"},
            headers=headers,
        )

    def test_valid_transition_open_to_under_review(self):
        case = create_case()
        resp = self._patch(case["case_id"], "under_review")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "under_review"
        assert body["assigned_to"] == "NODE_A7C2F9E1"
        assert len(body["decision_history"]) == 1
        assert body["decision_history"][0]["previous_status"] == "open"

    def test_invalid_transition_open_to_confirmed_is_409(self):
        # Confirmation without review would defeat human-in-the-loop.
        # Even with the MLRO role, the status machine refuses the jump.
        case = create_case()
        resp = self._patch(case["case_id"], "closed_confirmed", headers=KEY_A_MLRO)
        assert resp.status_code == 409

    def test_closed_case_is_terminal(self):
        case = create_case()
        self._patch(case["case_id"], "closed_no_action")
        resp = self._patch(case["case_id"], "under_review")
        assert resp.status_code == 409

    def test_full_lifecycle_to_confirmed(self):
        case = create_case()
        assert self._patch(case["case_id"], "under_review").status_code == 200
        assert self._patch(case["case_id"], "escalated", headers=KEY_A_SENIOR).status_code == 200
        resp = self._patch(case["case_id"], "closed_confirmed", headers=KEY_A_MLRO)
        assert resp.status_code == 200
        assert len(resp.json()["decision_history"]) == 3

    def test_false_positive_flag_set_on_fp_close(self):
        case = create_case()
        self._patch(case["case_id"], "under_review")
        resp = self._patch(case["case_id"], "closed_false_positive", headers=KEY_A_SENIOR)
        assert resp.json()["false_positive_flag"] is True

    def test_transition_map_has_no_escape_from_closed(self):
        for status, targets in TRANSITIONS.items():
            if status.startswith("closed"):
                assert targets == frozenset(), f"{status} must be terminal"

    def test_pii_in_reason_rejected(self):
        case = create_case()
        resp = client.patch(
            f"/api/cases/{case['case_id']}/status",
            json={"new_status": "under_review",
                  "reason": "customer IBAN SA4420000001234567891234 verified"},
            headers=KEY_A,
        )
        assert resp.status_code == 422


# ── Analyst notes ──────────────────────────────────────────────────────────


class TestAnalystNotes:
    def test_add_note(self):
        case = create_case()
        resp = client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "Velocity pattern matches known typology; requesting peer stats."},
            headers=KEY_A_SENIOR,
        )
        assert resp.status_code == 200
        notes = resp.json()["analyst_notes"]
        assert len(notes) == 1
        assert notes[0]["node_id"] == "NODE_A7C2F9E1"
        # Role recorded from the auth context (key + validated role header).
        assert notes[0]["analyst_role"] == "senior_analyst"

    def test_notes_accumulate(self):
        case = create_case()
        for i in range(3):
            client.post(
                f"/api/cases/{case['case_id']}/notes",
                json={"note": f"observation number {chr(97 + i)} recorded"},
                headers=KEY_A,
            )
        resp = client.get(f"/api/cases/{case['case_id']}", headers=KEY_A)
        assert len(resp.json()["analyst_notes"]) == 3

    def test_pii_note_rejected_iban(self):
        case = create_case()
        resp = client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "linked to SA4420000001234567891234"},
            headers=KEY_A,
        )
        assert resp.status_code == 422
        assert any("iban-like" in r for r in resp.json()["detail"]["reasons"])

    def test_pii_note_rejected_arabic_name(self):
        case = create_case()
        resp = client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "Account holder appears to be محمد العتيبي"},
            headers=KEY_A,
        )
        assert resp.status_code == 422

    def test_pii_note_rejected_phone(self):
        case = create_case()
        resp = client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "callback number +966512345678"},
            headers=KEY_A,
        )
        assert resp.status_code == 422

    def test_rejected_note_is_not_stored(self):
        case = create_case()
        client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "IBAN SA4420000001234567891234"},
            headers=KEY_A,
        )
        resp = client.get(f"/api/cases/{case['case_id']}", headers=KEY_A)
        assert resp.json()["analyst_notes"] == []


# ── Decisions & history ────────────────────────────────────────────────────


class TestDecisions:
    def _decide(self, case_id: str, decision: str, reason: str = "documented analyst rationale"):
        # MLRO via the validated role header — body roles are ignored.
        return client.post(
            f"/api/cases/{case_id}/decision",
            json={"decision": decision, "reason": reason},
            headers=KEY_A_MLRO,
        )

    def test_decision_drives_status(self):
        case = create_case()
        resp = self._decide(case["case_id"], "take_under_review")
        assert resp.status_code == 200
        assert resp.json()["status"] == "under_review"

    def test_invalid_decision_from_open_is_409(self):
        case = create_case()
        resp = self._decide(case["case_id"], "confirm_fraud")
        assert resp.status_code == 409

    def test_decision_history_is_append_only(self):
        case = create_case()
        self._decide(case["case_id"], "take_under_review", "starting review")
        self._decide(case["case_id"], "escalate", "needs senior sign-off")
        resp = self._decide(case["case_id"], "confirm_fraud", "pattern verified at both nodes")
        history = resp.json()["decision_history"]
        assert [h["decision"] for h in history] == [
            "take_under_review", "escalate", "confirm_fraud",
        ]
        # Earlier entries are preserved verbatim — no silent overwrite.
        assert history[0]["reason"] == "starting review"
        assert history[0]["new_status"] == "under_review"
        assert history[1]["previous_status"] == "under_review"
        assert all(h["analyst_role"] == "mlro" for h in history)
        assert all(h["audit_ref"] for h in history)

    def test_history_survives_in_store_snapshots(self):
        """The JSONL store appends snapshots — reloading from disk yields the
        full history, proving nothing was overwritten in place."""
        from backend.app.services.case_service import CaseStore

        case = create_case()
        self._decide(case["case_id"], "take_under_review")
        self._decide(case["case_id"], "mark_false_positive", "legitimate payroll batch")
        reloaded = CaseStore(config.cases_path())
        loaded = reloaded.get(case["case_id"])
        assert len(loaded["decision_history"]) == 2
        assert loaded["false_positive_flag"] is True
        # Every snapshot remains on disk (1 create + 1 audit-ref attach + 2 decisions).
        lines = config.cases_path().read_text(encoding="utf-8").splitlines()
        assert len([l for l in lines if l.strip()]) == 4

    def test_pii_in_decision_reason_rejected(self):
        case = create_case()
        resp = self._decide(case["case_id"], "take_under_review",
                            reason="verified via ACC_MULE_SA_001 records")
        assert resp.status_code == 422


# ── Audit coverage ─────────────────────────────────────────────────────────


class TestCaseAudit:
    def test_every_write_creates_audit_record(self):
        case = create_case()
        client.patch(
            f"/api/cases/{case['case_id']}/status",
            json={"new_status": "under_review", "reason": "triage"},
            headers=KEY_A,
        )
        client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "reviewing velocity buckets now"},
            headers=KEY_A,
        )
        client.post(
            f"/api/cases/{case['case_id']}/decision",
            json={"decision": "escalate", "reason": "cross-bank scope"},
            headers=KEY_A_SENIOR,
        )
        actions = [e["action"] for e in _audit_entries()]
        for expected in ("case_create", "case_status_change", "case_note_add", "case_decision"):
            assert expected in actions, f"missing audit action {expected}"

    def test_rejected_writes_are_audited_too(self):
        case = create_case()
        client.post(
            f"/api/cases/{case['case_id']}/notes",
            json={"note": "IBAN SA4420000001234567891234"},
            headers=KEY_A,
        )
        rejected = [e for e in _audit_entries()
                    if e["action"] == "case_note_add" and e["decision"] == "rejected"]
        assert len(rejected) == 1
        assert "SA44" not in rejected[0]["reason"]

    def test_case_links_to_audit_refs(self):
        case = create_case()
        resp = client.patch(
            f"/api/cases/{case['case_id']}/status",
            json={"new_status": "under_review", "reason": "triage"},
            headers=KEY_A,
        )
        refs = resp.json()["audit_refs"]
        assert len(refs) == 2  # create + status change
        assert all(len(r) == 64 for r in refs)  # sha256 hex
