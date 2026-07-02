# sys.path is set up by the root conftest.py

import pytest

from backend.app.services import feature_store_service


@pytest.fixture(autouse=True)
def _isolated_runtime(tmp_path, monkeypatch):
    """Every backend test runs with DEV node keys active, audit/registry
    files redirected to a per-test temp dir (fresh singletons per path),
    and an empty in-memory feature store."""
    monkeypatch.delenv("NASEEJ_NODE_KEYS", raising=False)
    monkeypatch.delenv("NASEEJ_NODE_PROFILES", raising=False)
    monkeypatch.delenv("NASEEJ_FEATURE_SNAPSHOT", raising=False)
    monkeypatch.setenv("NASEEJ_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("NASEEJ_REGISTRY_PATH", str(tmp_path / "patterns.jsonl"))
    monkeypatch.setenv("NASEEJ_CASES_PATH", str(tmp_path / "cases.jsonl"))
    monkeypatch.setenv("NASEEJ_SHADOW_OBSERVATIONS_PATH", str(tmp_path / "shadow_observations.jsonl"))
    monkeypatch.setenv("NASEEJ_FEEDBACK_LABELS_PATH", str(tmp_path / "feedback_labels.jsonl"))
    feature_store_service.reset()
    yield
    feature_store_service.reset()
