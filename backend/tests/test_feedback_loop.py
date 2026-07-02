"""Analyst feedback loop + calibration dataset tests.

Closed-case → label, node-scoping/RBAC, PII-safe storage, safe duplicate
behaviour, insufficient-vs-prototype calibration, audit coverage, and isolation
(no cases created; deployed scoring / shadow scoring unchanged).
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

import pytest
from fastapi.testclient import TestClient

from backend.app.core import config
from backend.app.main import app
from backend.app.services import feedback_service

client = TestClient(app)

KEY_A = {"X-API-Key": "dev-key-bank-a-local-only"}        # NODE_A7C2F9E1 (analyst)
KEY_A_MLRO = {**KEY_A, "X-Analyst-Role": "mlro"}          # can confirm fraud
KEY_A_SENIOR = {**KEY_A, "X-Analyst-Role": "senior_analyst"}
KEY_B = {"X-API-Key": "dev-key-bank-b-local-only"}        # NODE_B3D8E2F4
KEY_REG = {"X-API-Key": "dev-key-regulator-local-only"}   # view_all

VALID_PATTERN = {
    "pattern_id": "7f3c9a1e-2b4d-4e8f-9a6c-1d5e8b3f7a20",
    "pattern_hash": "NSJ_MULE_VELOCITY_8f9b2c4d1e7a3c5d",
    "typology": "mule_velocity",
    "graph_signature": {"node_count": 7, "edge_count": 6,
                        "in_degree_sequence": [0, 0, 0, 0, 0, 1, 5],
                        "out_degree_sequence": [0, 0, 1, 1, 1, 1, 2],
                        "diameter": 2, "is_cross_bank": True},
    "velocity_features": {"window_bucket": "under_1h", "tx_count_bucket": "2_to_5",
                         "amount_bucket": "5k_to_25k", "burst_score_bucket": "high"},
    "risk_score": 0.91, "confidence": 0.87,
    "detection_timestamp": "2026-06-11T09:42:00Z", "source_node_id": "NODE_A7C2F9E1",
    "evidence_summary": "Fan-in of 5 sub-threshold transfers into a single account.",
    "privacy_guarantees": {"zero_pii_verified": True, "bucketing_version": "buckets-v1",
                          "hash_algorithm": "sha256-canonical-json-v1", "k_anonymity_floor": 5},
    "governance_tags": {"sharing_scope": "network_all", "retention_days": 90,
                       "requires_human_review": True, "regulatory_basis": "SAMA-CFF-early-warning"},
}


def _open_case(headers=KEY_A, **overrides) -> str:
    p = copy.deepcopy(VALID_PATTERN)
    p["pattern_id"] = str(uuid.uuid4())
    p.update(overrides)
    assert client.post("/api/patterns", json=p, headers=headers).status_code == 201
    r = client.post(f"/api/cases/from-pattern/{p['pattern_id']}", headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["case_id"]


def _decide(case_id, decision, headers, reason="analyst rationale here"):
    return client.post(f"/api/cases/{case_id}/decision", headers=headers,
                       json={"decision": decision, "reason": reason})


def _close_confirmed(headers=KEY_A_MLRO) -> str:
    cid = _open_case()
    _decide(cid, "take_under_review", KEY_A)
    assert _decide(cid, "confirm_fraud", headers).status_code == 200
    return cid


def _close_false_positive() -> str:
    cid = _open_case()
    _decide(cid, "take_under_review", KEY_A)
    assert _decide(cid, "mark_false_positive", KEY_A_SENIOR).status_code == 200
    return cid


def _close_no_action() -> str:
    cid = _open_case()
    assert _decide(cid, "close_no_action", KEY_A).status_code == 200
    return cid


def _audit_entries():
    path = config.audit_log_path()
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _feedback_rows():
    path = config.feedback_labels_path()
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── label mapping per closed status ──────────────────────────────────────────

class TestFeedbackFromClosedCase:
    def test_confirmed_fraud_label(self):
        cid = _close_confirmed()
        r = client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A_MLRO)
        assert r.status_code == 201
        assert r.json()["feedback_label"] == "confirmed_fraud"

    def test_false_positive_label(self):
        cid = _close_false_positive()
        r = client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        assert r.status_code == 201
        assert r.json()["feedback_label"] == "false_positive"

    def test_no_action_label(self):
        cid = _close_no_action()
        r = client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        assert r.status_code == 201
        assert r.json()["feedback_label"] == "no_action"

    def test_open_case_cannot_create_final_label(self):
        cid = _open_case()
        r = client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        assert r.status_code == 409
        assert "not closed" in r.json()["detail"]

    def test_under_review_cannot_create_final_label(self):
        cid = _open_case()
        _decide(cid, "take_under_review", KEY_A)
        r = client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        assert r.status_code == 409


# ── visibility / node-scoping ────────────────────────────────────────────────

class TestVisibilityAndScoping:
    def test_missing_case_404(self):
        r = client.post(f"/api/feedback/from-case/{uuid.uuid4()}", headers=KEY_A)
        assert r.status_code == 404

    def test_cannot_create_feedback_for_hidden_case(self):
        # Local-only pattern owned by A → not visible to B.
        cid = _open_case(headers=KEY_A, source_node_id="NODE_A7C2F9E1",
                        governance_tags={**VALID_PATTERN["governance_tags"], "sharing_scope": "local_only"})
        _decide(cid, "close_no_action", KEY_A)
        r = client.post(f"/api/feedback/from-case/{cid}", headers=KEY_B)
        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized for this resource or action."

    def test_summary_is_node_scoped(self):
        cid = _close_no_action()
        client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        # A sees its label; B sees none of A's feedback.
        assert client.get("/api/feedback", headers=KEY_A).json()["labeled_count"] >= 1
        assert client.get("/api/feedback", headers=KEY_B).json()["labeled_count"] == 0

    def test_cross_node_calibration_denied_without_view_all(self):
        r = client.get("/api/feedback/calibration-dataset?node_id=NODE_A7C2F9E1", headers=KEY_B)
        assert r.status_code == 403

    def test_regulator_may_view_all_calibration(self):
        r = client.get("/api/feedback/calibration-dataset?node_id=NODE_A7C2F9E1", headers=KEY_REG)
        assert r.status_code == 200

    def test_requires_auth(self):
        assert client.post(f"/api/feedback/from-case/{uuid.uuid4()}").status_code == 401
        assert client.get("/api/feedback").status_code == 401


# ── privacy of the store ─────────────────────────────────────────────────────

class TestPrivacy:
    def test_feedback_store_has_no_pii_or_feature_values(self):
        cid = _close_confirmed()
        client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A_MLRO)
        blob = json.dumps(_feedback_rows())
        # no raw identifiers / amounts / feature values
        for token in ("MULEBB", "OFFSHORE", "9000", "SENDER", "0x", "ACC_"):
            assert token not in blob, token

    def test_feedback_record_schema(self):
        cid = _close_no_action()
        client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        rec = _feedback_rows()[-1]
        expected = {
            "feedback_id", "case_id", "node_id", "final_case_status", "analyst_decision",
            "false_positive_flag", "linked_pattern_id", "linked_shadow_observation_id",
            "candidate_risk_tier_bucket", "baseline_risk_tier_bucket", "agreement_with_baseline",
            "feedback_label", "created_at", "pii_safe",
        }
        assert set(rec) == expected
        assert rec["pii_safe"] is True


# ── duplicate behaviour ──────────────────────────────────────────────────────

class TestDuplicateSafe:
    def test_duplicate_appends_but_counts_once(self):
        cid = _close_no_action()
        r1 = client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        r2 = client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        assert r1.status_code == 201 and r2.status_code == 201
        # two snapshots written, but the case is counted once in the summary
        assert len(_feedback_rows()) == 2
        summary = client.get("/api/feedback", headers=KEY_A).json()
        assert summary["total_feedback_records"] == 1
        assert summary["no_action_count"] == 1


# ── calibration dataset ──────────────────────────────────────────────────────

class TestCalibrationDataset:
    def test_insufficient_labels(self):
        cid = _close_no_action()
        client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        d = client.get("/api/feedback/calibration-dataset", headers=KEY_A).json()
        assert d["minimum_label_threshold_met"] is False
        assert d["status"] == "insufficient_labels"
        assert d["candidate_precision_proxy"] is None
        assert "insufficient labels" in d["message"]
        assert d["calibrated_for_production"] is False

    def test_summary_computes_with_synthetic_labels(self):
        # Pure-function check with a synthetic labeled set (no real threshold).
        recs = []
        for i in range(4):
            recs.append({"case_id": f"c{i}", "feedback_label": "confirmed_fraud",
                         "candidate_risk_tier_bucket": "high", "baseline_risk_tier_bucket": "medium",
                         "agreement_with_baseline": "agree"})
        for i in range(2):
            recs.append({"case_id": f"f{i}", "feedback_label": "false_positive",
                         "candidate_risk_tier_bucket": "medium", "baseline_risk_tier_bucket": "minimal",
                         "agreement_with_baseline": "disagree"})
        agg = feedback_service.calibration_dataset.__wrapped__ if hasattr(
            feedback_service.calibration_dataset, "__wrapped__") else None
        # Use the pure helpers directly.
        tier_outcome = feedback_service._tier_vs_outcome(recs, "candidate_risk_tier_bucket")
        assert tier_outcome["high"]["confirmed_fraud"] == 4
        assert tier_outcome["medium"]["false_positive"] == 2
        prec = feedback_service._precision_proxy(recs, "candidate_risk_tier_bucket")
        # 4 confirmed of 6 alerting (high+medium) = 0.6667
        assert prec == round(4 / 6, 4)

    def test_prototype_ready_when_threshold_met(self, monkeypatch):
        monkeypatch.setenv("NASEEJ_CALIBRATION_MIN_LABELS", "2")
        for _ in range(2):
            cid = _close_confirmed()
            client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A_MLRO)
        d = client.get("/api/feedback/calibration-dataset", headers=KEY_A).json()
        assert d["minimum_label_threshold_met"] is True
        assert d["status"] == "prototype_ready"
        assert "metrics_note" in d  # prototype label present


class TestPublicCalibrationStatus:
    def test_public_no_auth(self):
        r = client.get("/api/model/candidate/calibration-status")
        assert r.status_code == 200
        d = r.json()
        assert d["calibration_status"] in ("insufficient_labels", "prototype_ready", "unavailable")
        assert d["calibrated_for_production"] is False
        assert d["deployment_recommended"] is False

    def test_status_no_per_node_counts(self):
        d = client.get("/api/model/candidate/calibration-status").json()
        # exposes the enum + threshold, never raw counts
        assert "labeled_count" not in d and "confirmed_fraud_count" not in d


# ── audit + isolation ────────────────────────────────────────────────────────

class TestAuditAndIsolation:
    def test_audit_written_on_create(self):
        cid = _close_no_action()
        before = len(_audit_entries())
        client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        accepted = [e for e in _audit_entries()[before:]
                    if e["action"] == "feedback_create" and e["decision"] == "accepted"]
        assert accepted

    def test_audit_written_on_denied(self):
        cid = _open_case(headers=KEY_A, source_node_id="NODE_A7C2F9E1",
                        governance_tags={**VALID_PATTERN["governance_tags"], "sharing_scope": "local_only"})
        _decide(cid, "close_no_action", KEY_A)
        before = len(_audit_entries())
        client.post(f"/api/feedback/from-case/{cid}", headers=KEY_B)
        denied = [e for e in _audit_entries()[before:]
                  if e["action"] == "feedback_create" and e["decision"] == "denied"]
        assert denied

    def test_feedback_does_not_create_cases(self):
        cid = _close_no_action()
        before = client.get("/api/cases", headers=KEY_A).json()["count"]
        client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        client.get("/api/feedback", headers=KEY_A)
        after = client.get("/api/cases", headers=KEY_A).json()["count"]
        assert after == before

    def test_score_transaction_unchanged(self):
        payload = {"from_bank": "1", "from_account": "X", "to_bank": "2", "to_account": "Y", "amount": 5000.0}
        before = client.post("/api/score-transaction", headers=KEY_A, json=payload).json()
        cid = _close_no_action()
        client.post(f"/api/feedback/from-case/{cid}", headers=KEY_A)
        after = client.post("/api/score-transaction", headers=KEY_A, json=payload).json()
        assert before["risk_score"] == after["risk_score"]
