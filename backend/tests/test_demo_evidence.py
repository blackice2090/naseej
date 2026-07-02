"""Demo readiness + governance evidence pack tests.

Public read-only endpoints: safe structure, no overclaims (no affirmative
SAMA/PDPL-certified or production-ready claims; honest negations are allowed),
known limitations present, no sensitive data.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

ENDPOINTS = ("/api/demo/health", "/api/demo/governance-evidence", "/api/demo/judge-summary")


def _affirmative_overclaims(blob: str) -> list[str]:
    """Return compliance phrases that appear WITHOUT a preceding negation.
    'Not SAMA-certified' / 'not production-ready' are allowed (disclaimers);
    an unnegated 'production-ready' is an overclaim."""
    blob = blob.lower()
    bad = []
    for m in re.finditer(r"(sama[ -]certified|pdpl[ -]certified|production[ -]ready)", blob):
        ctx = blob[max(0, m.start() - 6):m.start()]
        if "not" not in ctx and "no " not in ctx:
            bad.append(m.group())
    return bad


# ── public read-only ─────────────────────────────────────────────────────────

class TestPublicReadOnly:
    def test_all_public_no_auth(self):
        for ep in ENDPOINTS:
            assert client.get(ep).status_code == 200

    def test_post_not_allowed(self):
        for ep in ENDPOINTS:
            assert client.post(ep).status_code == 405


# ── health ───────────────────────────────────────────────────────────────────

class TestDemoHealth:
    def test_structure(self):
        d = client.get("/api/demo/health").json()
        assert d["status"] in ("ready", "partial", "unavailable")
        assert isinstance(d["checks"], list) and d["checks"]
        assert isinstance(d["warnings"], list)
        assert isinstance(d["demo_safe"], bool)
        assert d["production_ready"] is False

    def test_checks_cover_required_surfaces(self):
        names = {c["name"] for c in client.get("/api/demo/health").json()["checks"]}
        for required in ("backend", "baseline_model", "candidate_model", "feature_store",
                         "feature_contract", "shadow_monitoring", "feedback_dataset",
                         "audit_log", "case_store", "rbac_auth", "zero_pii_guard",
                         "frontend_connectivity"):
            assert required in names, required

    def test_each_check_shape(self):
        for c in client.get("/api/demo/health").json()["checks"]:
            assert {"name", "status", "detail", "critical"} <= set(c)
            assert c["status"] in ("ok", "unavailable")


# ── governance evidence ──────────────────────────────────────────────────────

class TestGovernanceEvidence:
    def test_structure(self):
        d = client.get("/api/demo/governance-evidence").json()
        assert isinstance(d["evidence"], list) and len(d["evidence"]) >= 8
        assert d["compliance_posture"]["certified"] is False
        assert d["compliance_posture"]["production_ready"] is False
        assert d["compliance_posture"]["pdpl"] == "PDPL-by-design"
        assert d["compliance_posture"]["sama"] == "SAMA-aligned prototype"

    def test_each_evidence_item_shape(self):
        for item in client.get("/api/demo/governance-evidence").json()["evidence"]:
            assert {"evidence_name", "status", "source_endpoint_or_file",
                    "what_it_proves", "limitation", "demo_claim_allowed"} <= set(item)
            assert item["limitation"]  # every item names a limitation

    def test_covers_required_evidence(self):
        names = {i["evidence_name"] for i in client.get("/api/demo/governance-evidence").json()["evidence"]}
        for required in ("zero_pii_posture", "no_autonomous_blocking", "human_in_the_loop",
                         "audit_trail", "node_isolation_rbac", "feature_contract_parity",
                         "candidate_shadow_only", "calibration_status", "feedback_loop"):
            assert required in names, required

    def test_known_limitations_present(self):
        d = client.get("/api/demo/governance-evidence").json()
        assert len(d["known_limitations"]) >= 5
        joined = " ".join(d["known_limitations"]).lower()
        assert "synthetic" in joined and "not production-ready" in joined


# ── judge summary ────────────────────────────────────────────────────────────

class TestJudgeSummary:
    def test_structure(self):
        d = client.get("/api/demo/judge-summary").json()
        for key in ("problem", "solution", "what_the_demo_proves", "what_is_simulated",
                    "what_is_real", "what_is_not_claimed", "top_5_differentiators",
                    "remaining_risks", "recommended_demo_flow"):
            assert key in d, key
        assert len(d["top_5_differentiators"]) == 5
        assert d["recommended_demo_flow"]

    def test_not_claimed_includes_disclaimers(self):
        joined = " ".join(client.get("/api/demo/judge-summary").json()["what_is_not_claimed"]).lower()
        assert "not sama-certified" in joined
        assert "not pdpl-certified" in joined
        assert "not production-ready" in joined


# ── no overclaims / no sensitive data ────────────────────────────────────────

class TestNoOverclaims:
    def test_no_affirmative_compliance_claims(self):
        for ep in ENDPOINTS:
            blob = json.dumps(client.get(ep).json())
            assert _affirmative_overclaims(blob) == [], f"{ep}: {_affirmative_overclaims(blob)}"

    def test_production_ready_always_false(self):
        for ep in ENDPOINTS:
            d = client.get(ep).json()
            posture = d.get("compliance_posture", {})
            if posture:
                assert posture["production_ready"] is False
            if "production_ready" in d:
                assert d["production_ready"] is False

    def test_no_raw_identifiers_or_pii(self):
        # The evidence pack must carry no IBAN/account/email shapes.
        for ep in ENDPOINTS:
            blob = json.dumps(client.get(ep).json())
            assert not re.search(r"\b[A-Z]{2}\d{2}[A-Z0-9]{8,}\b", blob)   # IBAN-like
            assert "@" not in blob.replace("evil@example.com", "")          # only the guard-probe literal
            assert "ACC_" not in blob and "0xMULE" not in blob
