"""Bank-node API key authentication tests.

Run from repo root:
    pytest backend/tests/test_auth.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.app.core import auth
from backend.app.main import app

client = TestClient(app)

DEV_KEY_A = "dev-key-bank-a-local-only"
DEV_KEY_B = "dev-key-bank-b-local-only"

SCORE_TX = {
    "from_bank": "1",
    "from_account": "ACC_A",
    "to_bank": "1",
    "to_account": "ACC_B",
    "amount": 100.0,
}


class TestProtectedEndpointsRequireKey:
    def test_score_without_key_is_401(self):
        resp = client.post("/api/score-transaction", json=SCORE_TX)
        assert resp.status_code == 401

    def test_analyze_without_key_is_401(self):
        resp = client.post("/api/analyze-pattern", json={"transactions": [SCORE_TX]})
        assert resp.status_code == 401

    def test_patterns_post_without_key_is_401(self):
        resp = client.post("/api/patterns", json={})
        assert resp.status_code == 401

    def test_patterns_list_without_key_is_401(self):
        resp = client.get("/api/patterns")
        assert resp.status_code == 401

    def test_patterns_get_without_key_is_401(self):
        resp = client.get("/api/patterns/some-id")
        assert resp.status_code == 401

    def test_wrong_key_is_401(self):
        resp = client.post(
            "/api/score-transaction", json=SCORE_TX,
            headers={"X-API-Key": "not-a-real-key"},
        )
        assert resp.status_code == 401

    def test_dev_key_is_accepted(self):
        resp = client.post(
            "/api/score-transaction", json=SCORE_TX,
            headers={"X-API-Key": DEV_KEY_A},
        )
        assert resp.status_code == 200


class TestPublicEndpointsStayOpen:
    def test_health_open(self):
        assert client.get("/health").status_code == 200

    def test_root_open(self):
        assert client.get("/").status_code == 200

    def test_model_metrics_open(self):
        assert client.get("/api/model/metrics").status_code == 200

    def test_cross_bank_open(self):
        assert client.get("/api/cross-bank/results").status_code == 200


class TestEnvConfiguredKeys:
    def test_env_keys_disable_dev_keys(self, monkeypatch):
        monkeypatch.setenv(auth.ENV_VAR, "NODE_TESTBANK:real-secret-key")
        resp = client.post(
            "/api/score-transaction", json=SCORE_TX,
            headers={"X-API-Key": DEV_KEY_A},
        )
        assert resp.status_code == 401, "dev key must die when real keys are configured"

    def test_env_key_is_accepted(self, monkeypatch):
        monkeypatch.setenv(auth.ENV_VAR, "NODE_TESTBANK:real-secret-key")
        resp = client.post(
            "/api/score-transaction", json=SCORE_TX,
            headers={"X-API-Key": "real-secret-key"},
        )
        assert resp.status_code == 200

    def test_env_key_maps_to_node_id(self, monkeypatch):
        monkeypatch.setenv(auth.ENV_VAR, "NODE_TESTBANK:k1, NODE_OTHERBNK:k2")
        assert auth.active_keys() == {"k1": "NODE_TESTBANK", "k2": "NODE_OTHERBNK"}

    def test_malformed_entries_are_ignored(self, monkeypatch):
        monkeypatch.setenv(
            auth.ENV_VAR,
            "NODE_TESTBANK:good, lowercase_node:bad, NODE_NOKEY:, justgarbage",
        )
        assert auth.active_keys() == {"good": "NODE_TESTBANK"}

    def test_empty_env_means_no_access_at_all(self, monkeypatch):
        monkeypatch.setenv(auth.ENV_VAR, "")
        resp = client.post(
            "/api/score-transaction", json=SCORE_TX,
            headers={"X-API-Key": DEV_KEY_A},
        )
        assert resp.status_code == 401


class TestDevNodeIds:
    def test_dev_node_ids_conform_to_network_format(self):
        for node_id in auth.DEV_NODE_KEYS.values():
            assert auth.NODE_ID_RE.match(node_id), node_id
