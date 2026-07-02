"""Backend health endpoint tests.

Run from repo root:
    pytest backend/tests/test_health.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core import config

client = TestClient(app)


class TestHealthEndpoint:
    def test_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_status_is_ok(self):
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_service_name_present(self):
        data = client.get("/health").json()
        assert "service" in data
        assert isinstance(data["service"], str)
        assert len(data["service"]) > 0

    def test_version_present(self):
        data = client.get("/health").json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_service_name_matches_config(self):
        data = client.get("/health").json()
        assert data["service"] == config.APP_NAME

    def test_version_matches_config(self):
        data = client.get("/health").json()
        assert data["version"] == config.APP_VERSION

    def test_root_redirects_or_returns(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "service" in data or "docs" in data

    def test_health_response_schema(self):
        data = client.get("/health").json()
        required_keys = {"status", "service", "version"}
        assert required_keys.issubset(data.keys()), (
            f"Health response missing keys: {required_keys - data.keys()}"
        )

    def test_content_type_is_json(self):
        resp = client.get("/health")
        assert "application/json" in resp.headers.get("content-type", "")
