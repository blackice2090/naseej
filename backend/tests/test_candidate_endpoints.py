"""Backend tests for the read-only shadow-candidate endpoints.

Public, no node auth, no sensitive data, graceful fallback when reports are
absent. Run from repo root:
    pytest backend/tests/test_candidate_endpoints.py -v
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

client = TestClient(app)

ENDPOINTS = {
    "/api/model/candidate/metrics": ("CANDIDATE_METRICS_PATH", "candidate_model_metrics"),
    "/api/model/candidate/comparison": ("CANDIDATE_COMPARISON_PATH", "candidate_model_comparison"),
    "/api/model/candidate/thresholds": ("CANDIDATE_THRESHOLDS_PATH", "candidate_thresholds"),
    "/api/model/candidate/explainability-check": ("CANDIDATE_EXPLAINABILITY_PATH", "candidate_explainability_check"),
}


class TestPublicReadOnly:
    def test_no_auth_required(self):
        for ep in ENDPOINTS:
            assert client.get(ep).status_code == 200

    def test_post_not_allowed(self):
        for ep in ENDPOINTS:
            assert client.post(ep).status_code == 405


class TestFallback:
    @pytest.mark.parametrize("endpoint,attr,name", [
        (ep, a, n) for ep, (a, n) in ENDPOINTS.items()
    ])
    def test_missing_file_returns_fallback(self, endpoint, attr, name, tmp_path, monkeypatch):
        monkeypatch.setattr(config, attr, tmp_path / "absent.json")
        d = client.get(endpoint).json()
        assert d["source"] == "fallback"
        assert d["report"] == name
        assert "train_candidate_model" in d["note"]


class TestLiveServedShadowOnly:
    def _serve(self, monkeypatch, tmp_path, attr, payload):
        path = tmp_path / "r.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(config, attr, path)

    def test_metrics_served_marks_shadow(self, tmp_path, monkeypatch):
        self._serve(monkeypatch, tmp_path, "CANDIDATE_METRICS_PATH", {
            "source": "live", "deployed": False, "shadow_only": True,
            "selected_model": "lightgbm", "deployment_recommended": False,
            "selected_test_metrics": {"pr_auc": 0.55, "f1": 0.5},
        })
        d = client.get("/api/model/candidate/metrics").json()
        assert d["deployed"] is False
        assert d["deployment_recommended"] is False
        assert d["selected_model"] == "lightgbm"

    def test_comparison_served(self, tmp_path, monkeypatch):
        self._serve(monkeypatch, tmp_path, "CANDIDATE_COMPARISON_PATH",
                    {"source": "live", "leaderboard": [{"model": "rf"}], "excluded_features": []})
        d = client.get("/api/model/candidate/comparison").json()
        assert d["leaderboard"][0]["model"] == "rf"

    def test_thresholds_served(self, tmp_path, monkeypatch):
        self._serve(monkeypatch, tmp_path, "CANDIDATE_THRESHOLDS_PATH",
                    {"source": "live", "thresholds": [{"mode": "balanced"}]})
        d = client.get("/api/model/candidate/thresholds").json()
        assert d["thresholds"][0]["mode"] == "balanced"

    def test_explainability_served_pii_safe(self, tmp_path, monkeypatch):
        self._serve(monkeypatch, tmp_path, "CANDIDATE_EXPLAINABILITY_PATH",
                    {"source": "live", "pii_safe": True, "top_factors": [
                        {"feature_name": "amount", "value_bucket": "large", "direction": "increases_risk"}]})
        d = client.get("/api/model/candidate/explainability-check").json()
        assert d["pii_safe"] is True
        assert "raw_value" not in d["top_factors"][0]


def test_candidate_endpoints_do_not_expose_baseline_path():
    # Sanity: the candidate metrics endpoint never returns the deployed model's
    # metrics report (different file). When live on disk it is the candidate.
    d = client.get("/api/model/candidate/metrics").json()
    # Either fallback, or a candidate report flagged shadow_only — never the
    # deployed xgboost metrics shape (which has no 'shadow_only').
    if d.get("source") == "live":
        assert d.get("shadow_only") is True
