"""Tests for POST /api/model/candidate/score-shadow (comparison-only).

Verifies auth, PII guard, source-node match, approved-features-only vectors,
missing-feature safety, no case creation, no impact on deployed scoring, and
audit coverage. Runs under conftest isolation (fresh feature store, temp
audit/cases/registry files, dev keys active).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient

from backend.app.core import config
from backend.app.main import app
from backend.app.services import candidate_service

client = TestClient(app)

KEY_A = {"X-API-Key": "dev-key-bank-a-local-only"}   # NODE_A7C2F9E1
KEY_B = {"X-API-Key": "dev-key-bank-b-local-only"}   # NODE_B3D8E2F4
NODE_A = "NODE_A7C2F9E1"

TX = {
    "timestamp": "2024-05-01T10:30:00", "from_bank": "101", "from_account": "MULEBB",
    "to_bank": "202", "to_account": "OFFSHORE", "amount": 9000.0,
    "currency": "US Dollar", "payment_format": "Wire", "source_node_id": NODE_A,
}


@pytest.fixture(autouse=True)
def _reset_candidate():
    candidate_service.reset_candidate_cache()
    yield
    candidate_service.reset_candidate_cache()


def _ingest_history(n=5, target="MULEBB"):
    for i in range(n):
        r = client.post("/api/features/ingest-transaction", headers=KEY_A, json={
            "transaction_id": f"IN{i}", "timestamp": f"2024-05-01T10:0{i}:00",
            "source_node_id": NODE_A, "from_bank": "101", "from_account": f"SENDER{i}",
            "to_bank": "101", "to_account": target, "amount": 2000.0,
        })
        assert r.status_code == 201, r.text


def _audit_entries():
    path = config.audit_log_path()
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── auth / guard ─────────────────────────────────────────────────────────────

class TestAuthAndGuard:
    def test_requires_node_auth(self):
        assert client.post("/api/model/candidate/score-shadow", json=TX).status_code == 401

    def test_source_node_mismatch_403(self):
        bad = {**TX, "source_node_id": "NODE_SOMEONE_ELSE"}
        r = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=bad)
        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized for this resource or action."

    def test_pii_payload_rejected(self):
        bad = {**TX, "from_account": "SA4420000000001234567890"}  # IBAN-like
        r = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=bad)
        assert r.status_code == 422
        assert r.json()["detail"]["accepted"] is False


# ── candidate availability / missing feature ─────────────────────────────────

class TestAvailability:
    def test_missing_candidate_artifact_safe_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "CANDIDATE_MODEL_PATH", tmp_path / "nope.joblib")
        candidate_service.reset_candidate_cache()
        _ingest_history()
        d = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX).json()
        assert d["candidate_available"] is False
        assert d["feature_vector_status"] == "candidate_unavailable"
        assert d["shadow_only"] is True
        assert d["pii_safe"] is True

    def test_missing_feature_when_no_history(self):
        # No ingestion → node has no window state → missing_feature, not scored.
        d = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX).json()
        assert d["candidate_available"] is False
        assert d["feature_vector_status"] == "missing_feature"
        assert "missing_features" in d
        assert d["candidate_score"] is None

    def test_unparseable_timestamp_missing_feature(self):
        _ingest_history()
        bad = {**TX, "timestamp": "not-a-timestamp"}
        # Pydantic min_length on timestamp is satisfied; the parser rejects it.
        r = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=bad)
        # Either a 422 PII/shape rejection or a safe missing_feature — both safe.
        if r.status_code == 200:
            assert r.json()["feature_vector_status"] == "missing_feature"
        else:
            assert r.status_code in (422,)


# ── scored flow ──────────────────────────────────────────────────────────────

class TestScoredFlow:
    def test_scored_uses_only_15_approved_features(self):
        _ingest_history()
        d = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX).json()
        assert d["candidate_available"] is True
        assert d["shadow_only"] is True
        assert d["feature_vector_status"] == "complete"
        assert len(d["used_features"]) == 15
        # canonical approved names only — no identity/bank/account encodings
        used = set(d["used_features"])
        assert "amount" in used and "source_outflow_count_1h" in used
        forbidden = {"source_account_code", "target_account_code",
                     "source_bank_code", "target_bank_code"}
        assert used.isdisjoint(forbidden)

    def test_excluded_identity_features_confirmed(self):
        _ingest_history()
        d = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX).json()
        excluded = set(d["excluded_features_confirmed"])
        assert {"source_account_code", "target_account_code",
                "source_bank_code", "target_bank_code"} <= excluded
        # none of the excluded features appear in used
        assert set(d["used_features"]).isdisjoint(excluded)

    def test_baseline_comparison_present(self):
        _ingest_history()
        d = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX).json()
        assert d["candidate_score"] is not None
        assert d["baseline_score"] is not None
        assert d["score_delta"] is not None
        assert d["agreement_with_baseline"] in ("agree", "disagree")
        assert d["candidate_threshold_mode"] == "balanced"
        assert d["candidate_risk_tier"] in ("minimal", "low", "medium", "high")

    def test_response_is_pii_safe_no_raw_values(self):
        _ingest_history()
        d = client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX).json()
        blob = json.dumps(d)
        assert d["pii_safe"] is True
        for token in ("MULEBB", "OFFSHORE", "SENDER0"):
            assert token not in blob


# ── isolation: no cases, deployed scoring unchanged ──────────────────────────

class TestIsolation:
    def test_does_not_create_a_case(self):
        _ingest_history()
        before = client.get("/api/cases", headers=KEY_A).json()["count"]
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        after = client.get("/api/cases", headers=KEY_A).json()["count"]
        assert after == before

    def test_does_not_change_deployed_scoring(self):
        _ingest_history()
        # Deployed scoring still works and still uses the baseline bundle.
        before = client.post("/api/score-transaction", headers=KEY_A, json={
            "from_bank": "1", "from_account": "X", "to_bank": "2", "to_account": "Y", "amount": 5000.0,
        }).json()
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        after = client.post("/api/score-transaction", headers=KEY_A, json={
            "from_bank": "1", "from_account": "X", "to_bank": "2", "to_account": "Y", "amount": 5000.0,
        }).json()
        assert before["risk_score"] == after["risk_score"]
        assert after["source"] in ("model", "fallback")

    def test_candidate_bundle_is_not_deployed_baseline(self):
        # The candidate loader refuses anything flagged deployed, and the live
        # baseline bundle is a different model_name path.
        b = candidate_service.get_candidate_bundle()
        if b is not None:
            assert b.get("deployed") is not True
            assert b.get("candidate") is True


# ── audit coverage ───────────────────────────────────────────────────────────

class TestAudit:
    def test_audit_scored(self):
        _ingest_history()
        before = len(_audit_entries())
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        entries = [e for e in _audit_entries()[before:] if e["action"] == "candidate_shadow_score"]
        assert entries and entries[-1]["decision"] == "scored"

    def test_audit_unavailable(self):
        # No history → unavailable (missing_feature) → audited as unavailable.
        before = len(_audit_entries())
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        entries = [e for e in _audit_entries()[before:] if e["action"] == "candidate_shadow_score"]
        assert entries and entries[-1]["decision"] == "unavailable"

    def test_audit_rejected_on_mismatch(self):
        before = len(_audit_entries())
        client.post("/api/model/candidate/score-shadow", headers=KEY_A,
                    json={**TX, "source_node_id": "NODE_X"})
        entries = [e for e in _audit_entries()[before:] if e["action"] == "candidate_shadow_score"]
        assert entries and entries[-1]["decision"] == "rejected"

    def test_audit_has_no_raw_values(self):
        _ingest_history()
        before = len(_audit_entries())
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        for e in _audit_entries()[before:]:
            blob = json.dumps(e)
            for token in ("MULEBB", "OFFSHORE", "9000"):
                assert token not in blob
