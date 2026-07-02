"""ML evaluation report endpoints (read-only, public, degrade gracefully).

Run from repo root:
    pytest backend/tests/test_model_reports.py -v
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

from backend.app.main import app
from backend.app.core import config
from backend.app.services import model_service

client = TestClient(app)

ENDPOINTS = {
    "/api/model/comparison": ("MODEL_COMPARISON_PATH", "model_comparison"),
    "/api/model/per-typology-recall": ("PER_TYPOLOGY_RECALL_PATH", "per_typology_recall"),
    "/api/model/threshold-analysis": ("THRESHOLD_ANALYSIS_PATH", "threshold_analysis"),
    "/api/model/ablation-report": ("ABLATION_REPORT_PATH", "ablation_report"),
}


class TestMissingReportsFallBackSafely:
    @pytest.mark.parametrize("endpoint,config_attr,report_name", [
        (ep, attr, name) for ep, (attr, name) in ENDPOINTS.items()
    ])
    def test_missing_file_returns_fallback(self, endpoint, config_attr, report_name, tmp_path, monkeypatch):
        monkeypatch.setattr(config, config_attr, tmp_path / "does-not-exist.json")
        resp = client.get(endpoint)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "fallback"
        assert data["report"] == report_name
        assert "evaluation_suite" in data["note"]

    def test_unreadable_file_returns_fallback(self, tmp_path, monkeypatch):
        bad = tmp_path / "model_comparison.json"
        bad.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(config, "MODEL_COMPARISON_PATH", bad)
        data = client.get("/api/model/comparison").json()
        assert data["source"] == "fallback"


class TestLiveReportsAreServed:
    def _serve(self, monkeypatch, tmp_path, config_attr, payload):
        path = tmp_path / "report.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(config, config_attr, path)

    def test_comparison_served_verbatim(self, tmp_path, monkeypatch):
        payload = {
            "source": "live",
            "best_model": "lightgbm",
            "primary_metric": "pr_auc",
            "availability": {"lightgbm": {"available": True}},
            "models": [],
        }
        self._serve(monkeypatch, tmp_path, "MODEL_COMPARISON_PATH", payload)
        data = client.get("/api/model/comparison").json()
        assert data["best_model"] == "lightgbm"
        assert data["source"] == "live"

    def test_typology_recall_served(self, tmp_path, monkeypatch):
        payload = {"weakest_typology": "scatter_gather", "typologies": [], "label_method": "HEURISTIC"}
        self._serve(monkeypatch, tmp_path, "PER_TYPOLOGY_RECALL_PATH", payload)
        data = client.get("/api/model/per-typology-recall").json()
        assert data["weakest_typology"] == "scatter_gather"
        assert data["source"] == "live"  # defaulted when absent in the file

    def test_threshold_analysis_served(self, tmp_path, monkeypatch):
        payload = {"source": "live", "thresholds": [{"mode": "balanced", "threshold": 0.1}]}
        self._serve(monkeypatch, tmp_path, "THRESHOLD_ANALYSIS_PATH", payload)
        data = client.get("/api/model/threshold-analysis").json()
        assert data["thresholds"][0]["mode"] == "balanced"

    def test_ablation_report_served(self, tmp_path, monkeypatch):
        payload = {"source": "live", "feature_sets": [{"feature_set": "graph"}]}
        self._serve(monkeypatch, tmp_path, "ABLATION_REPORT_PATH", payload)
        data = client.get("/api/model/ablation-report").json()
        assert data["feature_sets"][0]["feature_set"] == "graph"


class TestEndpointsArePublicReadOnly:
    def test_no_api_key_required(self):
        # Research artefacts are public read-only, like /api/model/metrics.
        for endpoint in ENDPOINTS:
            resp = client.get(endpoint)
            assert resp.status_code == 200

    def test_post_not_allowed(self):
        for endpoint in ENDPOINTS:
            assert client.post(endpoint).status_code == 405


def test_fallback_helper_shape():
    data = model_service.fallback_evaluation_report("model_comparison")
    assert data["source"] == "fallback"
    assert data["report"] == "model_comparison"
    assert "model_comparison.json" in data["note"]
