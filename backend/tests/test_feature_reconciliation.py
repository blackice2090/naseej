"""Backend tests for the feature-reconciliation endpoints + contract-aware
explanations.

Run from repo root:
    pytest backend/tests/test_feature_reconciliation.py -v
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
from backend.app.services import explanation_service, model_service

client = TestClient(app)

ENDPOINTS = {
    "/api/model/feature-contract": ("FEATURE_CONTRACT_PATH", "feature_contract"),
    "/api/model/feature-parity": ("FEATURE_PARITY_PATH", "feature_parity"),
    "/api/model/training-feature-manifest": ("TRAINING_FEATURE_MANIFEST_PATH", "training_feature_manifest"),
}


class TestEndpointsArePublicReadOnly:
    def test_no_auth_required(self):
        for ep in ENDPOINTS:
            assert client.get(ep).status_code == 200

    def test_post_not_allowed(self):
        for ep in ENDPOINTS:
            assert client.post(ep).status_code == 405


class TestLiveAndFallback:
    @pytest.mark.parametrize("endpoint,attr,name", [
        (ep, a, n) for ep, (a, n) in ENDPOINTS.items()
    ])
    def test_missing_file_returns_fallback(self, endpoint, attr, name, tmp_path, monkeypatch):
        monkeypatch.setattr(config, attr, tmp_path / "absent.json")
        d = client.get(endpoint).json()
        assert d["source"] == "fallback"
        assert d["report"] == name
        assert "ml.src" in d["note"]

    def test_contract_served_has_features(self):
        d = client.get("/api/model/feature-contract").json()
        # When generated, the contract carries its feature list; fallback is
        # also acceptable (degrades safely), so accept either.
        assert d["source"] in ("live", "fallback")
        if d["source"] == "live":
            assert d["feature_count"] >= 1
            assert any(f["canonical_name"] == "source_outflow_count_1h" for f in d["features"])

    def test_parity_served_or_fallback(self):
        d = client.get("/api/model/feature-parity").json()
        assert d["source"] in ("live", "fallback")
        if d["source"] == "live":
            assert "result_counts" in d

    def test_manifest_flags_memorization(self):
        d = client.get("/api/model/training-feature-manifest").json()
        assert d["source"] in ("live", "fallback")
        if d["source"] == "live":
            approved = {r["canonical_name"] for r in d["approved_training_features"]}
            assert approved.isdisjoint(set(d["identity_memorization_flagged"]))


class TestContractAwareExplanations:
    def setup_method(self):
        explanation_service.reset_contract_cache()
        explanation_service.reset_shap_state()

    def teardown_method(self):
        explanation_service.reset_contract_cache()
        explanation_service.reset_shap_state()

    def test_every_explainable_feature_has_human_label(self):
        # Each contract feature surfaced in an explanation must resolve to a
        # non-trivial human label (curated or contract-derived).
        contract = model_service.load_json_report(config.FEATURE_CONTRACT_PATH)
        assert contract is not None, "contract must be generated for this test"
        for f in contract["features"]:
            if not f["explainable"]:
                continue
            offline = f["offline_name"]
            online = f["online_name"]
            name = offline or online
            label = explanation_service._humanize(name)
            assert isinstance(label, str) and len(label) > 1

    def test_explanation_uses_contract_bucket_and_limitation(self):
        from backend.app.core.schemas import TransactionIn
        tx = TransactionIn(timestamp="2024-01-10 03:30", from_bank="101",
                           from_account="SRCAA", to_bank="202", to_account="MULEBB",
                           amount=88000.0, currency="US Dollar", payment_format="Wire")
        out = explanation_service.explain_transaction(tx)
        assert out["pii_safe"] is True
        # account-id factors must surface a memorisation limitation from the contract.
        has_account_factor = any(
            f["feature_name"] in ("source_account_enc", "target_account_enc")
            for f in out["top_factors"]
        )
        if has_account_factor:
            assert any("memorisation" in lim for lim in out["model_limitations"])

    def test_explanation_works_without_contract(self, tmp_path, monkeypatch):
        # Contract missing → explanation still works via built-in labels.
        monkeypatch.setattr(config, "FEATURE_CONTRACT_PATH", tmp_path / "gone.json")
        explanation_service.reset_contract_cache()
        from backend.app.core.schemas import TransactionIn
        tx = TransactionIn(timestamp="2024-01-10 12:00", from_bank="101",
                           from_account="SRCCC", to_bank="101", to_account="DSTDD",
                           amount=500.0, currency="US Dollar", payment_format="ACH")
        out = explanation_service.explain_transaction(tx)
        assert out["pii_safe"] is True
        assert out["model_limitations"]
        assert explanation_service._contract_index()["loaded"] is False
