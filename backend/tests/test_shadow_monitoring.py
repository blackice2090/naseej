"""Tests for shadow monitoring: bucketed observations, node-scoped aggregates,
drift signals, and calibration-readiness — all PII-safe, comparison-only.

Runs under conftest isolation (fresh feature store, temp audit/cases/registry
+ shadow-observation files, dev keys active).
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
from backend.app.services import candidate_service, shadow_monitoring_service as sm

client = TestClient(app)

KEY_A = {"X-API-Key": "dev-key-bank-a-local-only"}   # NODE_A7C2F9E1
KEY_B = {"X-API-Key": "dev-key-bank-b-local-only"}   # NODE_B3D8E2F4
KEY_REG = {"X-API-Key": "dev-key-regulator-local-only"}  # view_all
NODE_A = "NODE_A7C2F9E1"

TX = {
    "timestamp": "2024-05-01T10:30:00", "from_bank": "101", "from_account": "MULEBB",
    "to_bank": "202", "to_account": "OFFSHORE", "amount": 9000.0,
    "currency": "US Dollar", "payment_format": "Wire", "source_node_id": NODE_A,
}


@pytest.fixture(autouse=True)
def _reset():
    candidate_service.reset_candidate_cache()
    sm.reset()
    yield
    candidate_service.reset_candidate_cache()
    sm.reset()


def _ingest_history(headers=KEY_A, node=NODE_A, target="MULEBB", n=5):
    for i in range(n):
        r = client.post("/api/features/ingest-transaction", headers=headers, json={
            "transaction_id": f"IN{i}", "timestamp": f"2024-05-01T10:0{i}:00",
            "source_node_id": node, "from_bank": "101", "from_account": f"SENDER{i}",
            "to_bank": "101", "to_account": target, "amount": 2000.0,
        })
        assert r.status_code == 201, r.text


def _observations():
    path = config.shadow_observations_path()
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── observation write + privacy ──────────────────────────────────────────────

class TestObservationWritten:
    def test_scored_writes_observation(self):
        _ingest_history()
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        obs = _observations()
        assert obs, "expected a shadow observation"
        o = obs[-1]
        assert o["shadow_only"] is True and o["pii_safe"] is True
        assert o["feature_vector_status"] == "complete"
        assert o["node_id"] == NODE_A

    def test_missing_feature_writes_unavailable_observation(self):
        # No history → missing_feature → still writes a safe observation.
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        obs = _observations()
        assert obs and obs[-1]["feature_vector_status"] == "missing_feature"
        assert obs[-1]["candidate_score_bucket"] == "none"

    def test_observation_has_no_raw_payload_or_values(self):
        _ingest_history()
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        blob = json.dumps(_observations())
        # no raw account/bank ids, amounts, or counterparties
        for token in ("MULEBB", "OFFSHORE", "SENDER0", "9000", "US Dollar", "Wire"):
            assert token not in blob, token

    def test_observation_schema_is_bucketed(self):
        _ingest_history()
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        o = _observations()[-1]
        expected = {
            "shadow_observation_id", "timestamp", "node_id", "candidate_model_name",
            "baseline_score_bucket", "candidate_score_bucket", "score_delta_bucket",
            "baseline_risk_tier", "candidate_risk_tier", "agreement_with_baseline",
            "threshold_mode", "candidate_action", "baseline_action",
            "feature_vector_status", "audit_ref", "pattern_id", "case_id",
            "shadow_only", "pii_safe",
        }
        assert set(o) == expected
        # buckets are labels, not raw numbers
        assert not o["candidate_score_bucket"].replace(".", "").replace("_", "").isdigit()

    def test_only_bucketed_fields_no_account_or_bank(self):
        _ingest_history()
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        o = _observations()[-1]
        # no field carries an account/bank id; node_id is a pseudonymous node label
        for key in o:
            assert "account" not in key and "iban" not in key.lower()


# ── node-scoped aggregation ──────────────────────────────────────────────────

class TestNodeScopedMonitoring:
    def test_monitoring_is_node_scoped(self):
        _ingest_history(headers=KEY_A, node=NODE_A)
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        d = client.get("/api/model/candidate/shadow-monitoring", headers=KEY_A).json()
        assert d["node_id"] == NODE_A
        assert d["windows"]["all"]["total_shadow_requests"] >= 1

    def test_other_bank_sees_only_own_empty_data(self):
        _ingest_history(headers=KEY_A, node=NODE_A)
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        # Bank B has no observations of its own.
        d = client.get("/api/model/candidate/shadow-monitoring", headers=KEY_B).json()
        assert d["node_id"] == "NODE_B3D8E2F4"
        assert d["windows"]["all"]["total_shadow_requests"] == 0

    def test_cross_node_query_denied_without_view_all(self):
        r = client.get(f"/api/model/candidate/shadow-monitoring?node_id={NODE_A}", headers=KEY_B)
        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized for this resource or action."

    def test_regulator_may_view_all(self):
        _ingest_history(headers=KEY_A, node=NODE_A)
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        r = client.get(f"/api/model/candidate/shadow-monitoring?node_id={NODE_A}", headers=KEY_REG)
        assert r.status_code == 200
        assert r.json()["node_id"] == NODE_A

    def test_requires_node_auth(self):
        assert client.get("/api/model/candidate/shadow-monitoring").status_code == 401


# ── aggregation correctness (pure) ───────────────────────────────────────────

class TestAggregateCorrectness:
    def _obs(self, **kw):
        base = {"feature_vector_status": "complete", "agreement_with_baseline": "agree",
                "score_delta_bucket": "approx_equal", "candidate_action": "no_alert (shadow)",
                "baseline_action": "benign", "threshold_mode": "balanced",
                "baseline_risk_tier": "minimal", "candidate_risk_tier": "minimal"}
        base.update(kw)
        return base

    def test_agreement_and_alert_rates(self):
        obs = [
            self._obs(agreement_with_baseline="agree"),
            self._obs(agreement_with_baseline="agree"),
            self._obs(agreement_with_baseline="disagree", candidate_action="analyst_queue (shadow)",
                      candidate_risk_tier="medium", score_delta_bucket="candidate_higher"),
            self._obs(feature_vector_status="missing_feature"),
        ]
        agg = sm.compute_aggregate(obs)
        assert agg["total_shadow_requests"] == 4
        assert agg["scored_count"] == 3
        assert agg["missing_feature_count"] == 1
        assert agg["agreement_rate"] == round(2 / 3, 4)
        assert agg["disagreement_rate"] == round(1 / 3, 4)
        assert agg["candidate_alert_rate"] == round(1 / 3, 4)
        assert agg["baseline_alert_rate"] == 0.0
        assert agg["candidate_higher_risk_rate"] == round(1 / 3, 4)
        assert agg["risk_tier_transition_matrix"]["minimal"]["minimal"] == 2

    def test_empty_aggregate_is_safe(self):
        agg = sm.compute_aggregate([])
        assert agg["total_shadow_requests"] == 0
        assert agg["agreement_rate"] is None
        assert agg["candidate_alert_rate"] is None


# ── drift signals ────────────────────────────────────────────────────────────

class TestDrift:
    def _agg(self, n, **kw):
        obs = [{"feature_vector_status": "complete", "agreement_with_baseline": "agree",
                "score_delta_bucket": "approx_equal", "candidate_action": "no_alert (shadow)",
                "baseline_action": "benign", "threshold_mode": "balanced",
                "baseline_risk_tier": "minimal", "candidate_risk_tier": "minimal"} for _ in range(n)]
        agg = sm.compute_aggregate(obs)
        agg.update(kw)
        return agg

    def test_normal_when_stable(self):
        recent = self._agg(20)
        baseline = self._agg(40)
        assert sm.compute_drift(recent, baseline)["signal"] == "normal"

    def test_unavailable_when_sparse(self):
        assert sm.compute_drift(self._agg(2), self._agg(40))["signal"] == "unavailable"

    def test_watch_on_missing_feature_spike(self):
        recent = self._agg(20, missing_feature_rate=0.7)
        baseline = self._agg(40, missing_feature_rate=0.05)
        d = sm.compute_drift(recent, baseline)
        assert d["signal"] == "watch"
        assert any("missing_feature" in r for r in d["reasons"])

    def test_watch_on_disagreement_spike(self):
        recent = self._agg(20, disagreement_rate=0.6)
        baseline = self._agg(40, disagreement_rate=0.1)
        d = sm.compute_drift(recent, baseline)
        assert d["signal"] == "watch"
        assert any("disagreement" in r for r in d["reasons"])


# ── calibration readiness ────────────────────────────────────────────────────

class TestCalibrationReadiness:
    def test_live_report_states_not_calibrated(self):
        d = client.get("/api/model/candidate/calibration-readiness").json()
        if d["source"] == "live":
            assert d["calibrated_for_production"] is False
            assert d["deployment_recommended"] is False
            assert d["needed_for_calibration"]

    def test_public_no_auth(self):
        assert client.get("/api/model/candidate/calibration-readiness").status_code == 200

    def test_missing_report_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "CANDIDATE_CALIBRATION_PATH", tmp_path / "absent.json")
        d = client.get("/api/model/candidate/calibration-readiness").json()
        assert d["source"] == "fallback"
        assert "candidate_calibration_readiness" in d["report"]


# ── isolation: no cases, deployed scoring unchanged ──────────────────────────

class TestIsolation:
    def test_monitoring_does_not_create_cases(self):
        _ingest_history()
        before = client.get("/api/cases", headers=KEY_A).json()["count"]
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        client.get("/api/model/candidate/shadow-monitoring", headers=KEY_A)
        after = client.get("/api/cases", headers=KEY_A).json()["count"]
        assert after == before

    def test_score_transaction_unchanged(self):
        payload = {"from_bank": "1", "from_account": "X", "to_bank": "2", "to_account": "Y", "amount": 5000.0}
        before = client.post("/api/score-transaction", headers=KEY_A, json=payload).json()
        _ingest_history()
        client.post("/api/model/candidate/score-shadow", headers=KEY_A, json=TX)
        after = client.post("/api/score-transaction", headers=KEY_A, json=payload).json()
        assert before["risk_score"] == after["risk_score"]
