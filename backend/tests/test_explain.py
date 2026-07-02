"""Explainability endpoint + service tests.

Covers: safe explanation structure, no PII / raw-id leakage, SHAP-missing
fallback, context-rule factors, case visibility + RBAC, audited denials, and
graceful degradation of the public model-explanation endpoint.

Run from repo root:
    pytest backend/tests/test_explain.py -v
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
from backend.app.services import explanation_service, model_service

client = TestClient(app)

KEY_A = {"X-API-Key": "dev-key-bank-a-local-only"}   # NODE_A7C2F9E1 (analyst)
KEY_B = {"X-API-Key": "dev-key-bank-b-local-only"}   # NODE_B3D8E2F4 (mlro)
KEY_REG = {"X-API-Key": "dev-key-regulator-local-only"}  # NODE_REG5C7A1 (view_all)

TX = {
    "timestamp": "2024-01-10 03:30",
    "from_bank": "101", "from_account": "SRCALPHA",
    "to_bank": "202", "to_account": "MULEZZ9",
    "amount": 88000.0, "currency": "US Dollar", "payment_format": "Wire",
}

VALID_PATTERN = {
    "pattern_id": "7f3c9a1e-2b4d-4e8f-9a6c-1d5e8b3f7a20",
    "pattern_hash": "NSJ_MULE_VELOCITY_8f9b2c4d1e7a3c5d",
    "typology": "mule_velocity",
    "graph_signature": {
        "node_count": 7, "edge_count": 6,
        "in_degree_sequence": [0, 0, 0, 0, 0, 1, 5],
        "out_degree_sequence": [0, 0, 1, 1, 1, 1, 2],
        "diameter": 2, "is_cross_bank": True,
    },
    "velocity_features": {
        "window_bucket": "under_1h", "tx_count_bucket": "2_to_5",
        "amount_bucket": "5k_to_25k", "burst_score_bucket": "high",
    },
    "risk_score": 0.91, "confidence": 0.87,
    "detection_timestamp": "2026-06-11T09:42:00Z",
    "source_node_id": "NODE_A7C2F9E1",
    "evidence_summary": (
        "Fan-in of 5 sub-threshold transfers into a single account within "
        "40 minutes, followed by an international wire sweep."
    ),
    "privacy_guarantees": {
        "zero_pii_verified": True, "bucketing_version": "buckets-v1",
        "hash_algorithm": "sha256-canonical-json-v1", "k_anonymity_floor": 5,
    },
    "governance_tags": {
        "sharing_scope": "network_all", "retention_days": 90,
        "requires_human_review": True, "regulatory_basis": "SAMA-CFF-early-warning",
    },
}


def _create_case(headers=KEY_A, **pattern_overrides) -> dict:
    p = copy.deepcopy(VALID_PATTERN)
    p["pattern_id"] = str(uuid.uuid4())
    p.update(pattern_overrides)
    r = client.post("/api/patterns", json=p, headers=headers)
    assert r.status_code == 201, r.text
    r = client.post(f"/api/cases/from-pattern/{p['pattern_id']}", headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _audit_entries() -> list[dict]:
    path = config.audit_log_path()
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# Known PII shapes that must never appear anywhere in an explanation payload.
_LEAK_TOKENS = ["SRCALPHA", "MULEZZ9", "88000", TX["from_account"], TX["to_account"]]


def _assert_no_leak(payload: dict) -> None:
    blob = json.dumps(payload)
    for token in _LEAK_TOKENS:
        assert token not in blob, f"explanation leaked raw value: {token}"


@pytest.fixture(autouse=True)
def _reset_shap():
    explanation_service.reset_shap_state()
    yield
    explanation_service.reset_shap_state()


# ── transaction explanation ──────────────────────────────────────────────────

class TestTransactionExplanation:
    def test_returns_safe_structure(self):
        r = client.post("/api/explain/transaction", json=TX, headers=KEY_A)
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ("explanation_id", "model_family", "explanation_method", "score",
                    "risk_tier", "top_factors", "contextual_factors", "typology_factors",
                    "threshold_rationale", "model_limitations", "analyst_summary", "pii_safe"):
            assert key in d, f"missing {key}"
        assert d["pii_safe"] is True
        assert d["explanation_id"]
        assert d["explanation_method"] in ("shap", "fallback")

    def test_top_factor_shape(self):
        d = client.post("/api/explain/transaction", json=TX, headers=KEY_A).json()
        assert d["top_factors"], "expected at least one top factor"
        for f in d["top_factors"]:
            assert set(f) >= {"feature_name", "direction", "contribution_level",
                              "human_label", "explanation", "value_bucket"}
            assert f["direction"] in ("increases_risk", "decreases_risk")
            assert f["contribution_level"] in ("low", "medium", "high")
            # value_bucket is a coarse label, never a raw number/identifier.
            assert not f["value_bucket"].replace(".", "").isdigit()

    def test_does_not_leak_account_ids_or_raw_amount(self):
        d = client.post("/api/explain/transaction", json=TX, headers=KEY_A).json()
        _assert_no_leak(d)

    def test_context_explanation_includes_rule_factors(self):
        # Ingest a fan-in burst + sweep so the context rule layer fires.
        node = "NODE_A7C2F9E1"
        base_ts = "2024-03-01 10:"
        for i in range(5):
            ev = {
                "transaction_id": f"FANIN{i}", "timestamp": f"{base_ts}0{i}",
                "source_node_id": node, "from_bank": "101", "from_account": f"SENDER{i}",
                "to_bank": "101", "to_account": "COLLECTOR", "amount": 2000.0,
            }
            assert client.post("/api/features/ingest-transaction", json=ev, headers=KEY_A).status_code == 201
        sweep = {
            "timestamp": "2024-03-01 10:09", "from_bank": "101", "from_account": "COLLECTOR",
            "to_bank": "202", "to_account": "OFFSHORE", "amount": 9500.0,
            "currency": "US Dollar", "payment_format": "Wire",
        }
        d = client.post("/api/explain/transaction", json=sweep, headers=KEY_A).json()
        assert d["contextual_factors"], "expected contextual rule factors with local history"
        # The standing honesty sentence belongs in model_limitations, not factors.
        assert not any(f.startswith("Adjustment is a deterministic rule layer")
                       for f in d["contextual_factors"])
        assert any("retrained" in lim for lim in d["model_limitations"])

    def test_pii_in_payload_rejected(self):
        bad = {**TX, "from_account": "SA4420000000001234567890"}  # IBAN-like
        r = client.post("/api/explain/transaction", json=bad, headers=KEY_A)
        assert r.status_code == 422
        assert r.json()["detail"]["accepted"] is False

    def test_requires_auth(self):
        assert client.post("/api/explain/transaction", json=TX).status_code == 401


# ── SHAP-missing fallback ────────────────────────────────────────────────────

class TestShapFallback:
    def test_fallback_when_shap_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "shap", None)  # force ImportError
        explanation_service.reset_shap_state()
        state = explanation_service.shap_state()
        assert state["available"] is False
        assert "fallback" in state["reason"]

        d = client.post("/api/explain/transaction", json=TX, headers=KEY_A).json()
        assert d["explanation_method"] == "fallback"
        assert "fallback" in d["method_note"]
        assert d["pii_safe"] is True
        assert d["top_factors"], "fallback must still produce factors"
        _assert_no_leak(d)


# ── case explanation: visibility + RBAC ──────────────────────────────────────

class TestCaseExplanation:
    def test_owner_can_explain_case(self):
        case = _create_case(headers=KEY_A)
        r = client.get(f"/api/explain/case/{case['case_id']}", headers=KEY_A)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["subject"] == "case"
        assert d["typology_factors"][0]["typology"] == "mule_velocity"
        assert d["risk_tier"] == "critical"
        assert d["pii_safe"] is True
        _assert_no_leak(d)

    def test_case_explanation_enriched_with_pattern_buckets(self):
        case = _create_case(headers=KEY_A)
        d = client.get(f"/api/explain/case/{case['case_id']}", headers=KEY_A).json()
        # velocity_features buckets surface as top factors (bucket labels only).
        buckets = {f["value_bucket"] for f in d["top_factors"]}
        assert "high" in buckets or "under_1h" in buckets or "2_to_5" in buckets

    def test_unauthorized_node_cannot_explain_hidden_case(self):
        case = _create_case(headers=KEY_A, source_node_id="NODE_A7C2F9E1",
                            governance_tags={**VALID_PATTERN["governance_tags"],
                                             "sharing_scope": "local_only"})
        r = client.get(f"/api/explain/case/{case['case_id']}", headers=KEY_B)
        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized for this resource or action."

    def test_denied_case_explanation_is_audited(self):
        case = _create_case(headers=KEY_A, source_node_id="NODE_A7C2F9E1",
                            governance_tags={**VALID_PATTERN["governance_tags"],
                                             "sharing_scope": "local_only"})
        before = len(_audit_entries())
        client.get(f"/api/explain/case/{case['case_id']}", headers=KEY_B)
        entries = _audit_entries()
        assert len(entries) > before
        denial = [e for e in entries if e["action"] == "explain_case" and e["decision"] == "denied"]
        assert denial, "denied case explanation must write an audit record"
        # Audit reason is static/sanitized — never the case id or any payload.
        assert case["case_id"] not in (denial[-1].get("reason") or "")

    def test_missing_case_returns_404(self):
        r = client.get(f"/api/explain/case/{uuid.uuid4()}", headers=KEY_A)
        assert r.status_code == 404

    def test_served_case_explanation_is_audited(self):
        case = _create_case(headers=KEY_A)
        before = len(_audit_entries())
        client.get(f"/api/explain/case/{case['case_id']}", headers=KEY_A)
        served = [e for e in _audit_entries()[before:]
                  if e["action"] == "explain_case" and e["decision"] == "served"]
        assert served


# ── model explanation: public + graceful degradation ─────────────────────────

class TestModelExplanation:
    def test_public_no_auth_required(self):
        r = client.get("/api/explain/model")
        assert r.status_code == 200
        d = r.json()
        assert d["subject"] == "model"
        assert "shap_available" in d
        assert d["model_limitations"]
        assert d["pii_safe"] is True

    def test_reports_present_summary(self):
        d = client.get("/api/explain/model").json()
        # With reports on disk these are populated; either way the call is safe.
        if d["source"] == "live":
            assert d.get("test_leader") is not None
            assert "analyst_summary" in d

    def test_degrades_gracefully_when_reports_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MODEL_COMPARISON_PATH", tmp_path / "nope.json")
        monkeypatch.setattr(config, "PER_TYPOLOGY_RECALL_PATH", tmp_path / "nope2.json")
        monkeypatch.setattr(config, "THRESHOLD_ANALYSIS_PATH", tmp_path / "nope3.json")
        d = client.get("/api/explain/model").json()
        assert d["source"] == "fallback"
        assert "note" in d
        assert d["model_limitations"]
        assert d["pii_safe"] is True


# ── service-level PII scrub ───────────────────────────────────────────────────

class TestPiiScrub:
    def test_scrub_redacts_flagged_strings(self):
        payload = {"analyst_summary": "contact me at evil@example.com now", "x": ["0xDEADBEEF"]}
        out = explanation_service._finalize(payload)
        assert "evil@example.com" not in json.dumps(out)
        assert "0xDEADBEEF" not in json.dumps(out)
        assert out["pii_safe"] is True
