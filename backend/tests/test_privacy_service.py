"""Backend privacy service tests — proves zero-PII contract at the API layer.

The privacy_service wraps ml.src.privacy_hash for use by FastAPI endpoints.
These tests verify that:
  1. Every PII field category is stripped by the service layer.
  2. Pattern hashes returned by backend endpoints never contain raw identifiers.
  3. verify_zero_pii passes for all normalized outputs.
  4. The analyze-pattern endpoint returns zero_pii=True for any input.
  5. The score-transaction endpoint never exposes account IDs in its response.

Run from repo root:
    pytest backend/tests/test_privacy_service.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import privacy_service

client = TestClient(app)

# ─── Raw PII finding simulating what pattern_library returns ─────────────────

RAW_FINDING_WITH_PII = {
    "pattern_type": "fan_in",
    "risk_score": 0.75,
    "reason": "Account received funds from 5 distinct sources.",
    "accounts_involved": [
        "ACC_MULE_SA_001",
        "SA44_2000_1234",
        "IBAN_SA_5678",
    ],
    "features": {
        "target": "ACC_MULE_SA_001",   # account ID — must be stripped
        "n_sources": 5,
        "total_in": 7_500.0,
        "in_banks": [1, 2, 3],
    },
}

# Known PII field names that must never appear in service output
PII_FIELD_NAMES = [
    "name", "full_name", "first_name", "last_name",
    "iban", "bban", "sort_code", "routing_number",
    "national_id", "national_number", "ssn", "tin", "passport", "driver_license",
    "phone", "mobile", "telephone", "email", "email_address",
    "account_id", "from_account", "to_account", "raw_id", "src_id", "dst_id",
    "ip_address", "device_id", "mac_address", "dob", "date_of_birth",
]

# ─── Endpoint payloads ────────────────────────────────────────────────────────

ATTACK_SEQUENCE_PAYLOAD = {
    "transactions": [
        {"from_bank": "101", "from_account": "0xSRC_A1", "to_bank": "101",
         "to_account": "0xMULE_01", "amount": 2_400.0, "payment_format": "ACH"},
        {"from_bank": "101", "from_account": "0xSRC_A2", "to_bank": "101",
         "to_account": "0xMULE_01", "amount": 1_850.0, "payment_format": "ACH"},
        {"from_bank": "101", "from_account": "0xSRC_A3", "to_bank": "101",
         "to_account": "0xMULE_01", "amount": 3_100.0, "payment_format": "ACH"},
        {"from_bank": "101", "from_account": "0xSRC_A4", "to_bank": "101",
         "to_account": "0xMULE_01", "amount": 990.0,   "payment_format": "ACH"},
        {"from_bank": "101", "from_account": "0xSRC_A5", "to_bank": "101",
         "to_account": "0xMULE_01", "amount": 1_760.0, "payment_format": "ACH"},
        {"from_bank": "101", "from_account": "0xMULE_01", "to_bank": "28856",
         "to_account": "0xINTL_DEST", "amount": 11_200.0, "payment_format": "Wire"},
    ]
}

SWEEP_TX = {
    "from_bank": "101",
    "from_account": "0xMULE_01",
    "to_bank": "28856",
    "to_account": "0xINTL_DEST",
    "amount": 11_200.0,
    "payment_format": "Wire",
}


# ═══════════════════════════════════════════════════════════════════════════════
# privacy_service module — unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrivacyServiceModule:
    """Test the service-layer wrapper (real engine or fallback)."""

    def test_strip_pii_removes_account_id(self):
        result = privacy_service.strip_pii({"account_id": "ACC", "risk": 0.5})
        assert "account_id" not in result
        assert result["risk"] == 0.5

    def test_strip_pii_removes_iban(self):
        result = privacy_service.strip_pii({"iban": "SA1234", "n": 3})
        assert "iban" not in result

    def test_strip_pii_removes_all_pii_categories(self):
        payload = {f: "SENSITIVE" for f in PII_FIELD_NAMES}
        payload["safe_field"] = "keep_me"
        result = privacy_service.strip_pii(payload)
        for pii_field in PII_FIELD_NAMES:
            assert pii_field not in result, f"'{pii_field}' not stripped by privacy_service"
        assert result["safe_field"] == "keep_me"

    def test_normalize_pattern_features_output_is_zero_pii(self):
        normalized = privacy_service.normalize_pattern_features(RAW_FINDING_WITH_PII)
        assert privacy_service.verify_zero_pii(normalized), (
            "normalize_pattern_features returned a payload that contains PII"
        )

    def test_normalize_removes_accounts_involved(self):
        normalized = privacy_service.normalize_pattern_features(RAW_FINDING_WITH_PII)
        assert "accounts_involved" not in normalized

    def test_generate_pattern_hash_returns_nsj_format(self):
        normalized = privacy_service.normalize_pattern_features(RAW_FINDING_WITH_PII)
        h = privacy_service.generate_pattern_hash(normalized)
        assert h.startswith("NSJ_"), f"Hash does not start with NSJ_: {h}"

    def test_generate_pattern_hash_deterministic(self):
        normalized = privacy_service.normalize_pattern_features(RAW_FINDING_WITH_PII)
        h1 = privacy_service.generate_pattern_hash(normalized)
        h2 = privacy_service.generate_pattern_hash(normalized)
        assert h1 == h2

    def test_verify_zero_pii_true_for_clean(self):
        clean = {"pattern_type": "fan_in", "risk_tier": "high", "n_sources": 3}
        assert privacy_service.verify_zero_pii(clean) is True

    def test_verify_zero_pii_false_for_account_id(self):
        assert privacy_service.verify_zero_pii({"account_id": "ACC"}) is False

    def test_verify_zero_pii_false_for_name(self):
        assert privacy_service.verify_zero_pii({"name": "Alice"}) is False

    def test_verify_zero_pii_false_for_phone(self):
        assert privacy_service.verify_zero_pii({"phone": "+966501234567"}) is False

    def test_topology_signature_format(self):
        edges = [("A", "B", 5_000.0), ("C", "B", 3_000.0)]
        sig = privacy_service.generate_topology_signature(edges)
        assert sig.startswith("NSJ_TOPO_"), f"Unexpected topology signature format: {sig}"

    def test_topology_signature_node_independent(self):
        """Same graph structure, different node labels → same signature."""
        graph_a = [("IBAN_1", "IBAN_MULE", 5_000.0), ("IBAN_2", "IBAN_MULE", 4_000.0)]
        graph_b = [("ACC_X", "ACC_Y",  5_200.0), ("ACC_Z", "ACC_Y", 3_800.0)]
        sig_a = privacy_service.generate_topology_signature(graph_a)
        sig_b = privacy_service.generate_topology_signature(graph_b)
        assert sig_a == sig_b, (
            f"Topology signature is node-dependent — IDs are leaking.\n"
            f"  IBAN graph: {sig_a}\n  Account graph: {sig_b}"
        )

    def test_pii_audit_report_marks_zero_pii(self):
        normalized = privacy_service.normalize_pattern_features(RAW_FINDING_WITH_PII)
        report = privacy_service.pii_audit_report(RAW_FINDING_WITH_PII, normalized)
        assert report["zero_pii"] is True

    def test_pii_audit_report_lists_stripped_account_id(self):
        finding_with_account = {**RAW_FINDING_WITH_PII, "account_id": "ACC_SENSITIVE"}
        normalized = privacy_service.normalize_pattern_features(finding_with_account)
        report = privacy_service.pii_audit_report(finding_with_account, normalized)
        assert "account_id" in report["stripped_pii_keys"]

    def test_placeholder_pattern_hash_format(self):
        h = privacy_service.placeholder_pattern_hash("mule_velocity", "3|5")
        assert h.startswith("NSJ_MULE_VELOCITY_"), f"Unexpected placeholder hash: {h}"


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoint: POST /api/analyze-pattern — zero-PII guarantee
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalyzePatternEndpointZeroPII:
    """The analyze-pattern endpoint must never expose account IDs or PII."""

    def _post(self, payload: dict) -> dict:
        resp = client.post(
            "/api/analyze-pattern", json=payload,
            headers={"X-API-Key": "dev-key-bank-a-local-only"},
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        return resp.json()

    def test_zero_pii_flag_always_true(self):
        data = self._post(ATTACK_SEQUENCE_PAYLOAD)
        assert data["zero_pii"] is True

    def test_pattern_hash_present_and_nsj_format(self):
        data = self._post(ATTACK_SEQUENCE_PAYLOAD)
        ph = data.get("pattern_hash")
        assert ph is not None
        assert ph.startswith("NSJ_"), f"Pattern hash format wrong: {ph}"

    def test_no_raw_account_ids_in_detected_patterns(self):
        """account IDs used in the request must not appear in the response patterns."""
        data = self._post(ATTACK_SEQUENCE_PAYLOAD)
        raw_accounts = [
            "0xSRC_A1", "0xSRC_A2", "0xSRC_A3", "0xSRC_A4", "0xSRC_A5",
            "0xMULE_01", "0xINTL_DEST",
        ]
        patterns_str = str(data.get("detected_patterns", []))
        for acct in raw_accounts:
            assert acct not in patterns_str, (
                f"Raw account ID '{acct}' leaked into detected_patterns"
            )

    def test_no_pii_fields_in_detected_patterns(self):
        data = self._post(ATTACK_SEQUENCE_PAYLOAD)
        for pattern in data.get("detected_patterns", []):
            for pii_field in PII_FIELD_NAMES:
                assert pii_field not in pattern, (
                    f"PII field '{pii_field}' found in detected pattern: {pattern}"
                )
            feats = pattern.get("features", {})
            for pii_field in PII_FIELD_NAMES:
                assert pii_field not in feats, (
                    f"PII field '{pii_field}' found in pattern features"
                )

    def test_recommended_action_is_valid(self):
        data = self._post(ATTACK_SEQUENCE_PAYLOAD)
        assert data["recommended_action"] in ("allow", "review", "block")

    def test_risk_score_in_range(self):
        data = self._post(ATTACK_SEQUENCE_PAYLOAD)
        assert 0.0 <= data["risk_score"] <= 1.0

    def test_graph_summary_no_pii(self):
        data = self._post(ATTACK_SEQUENCE_PAYLOAD)
        summary = data.get("graph_summary", {})
        for pii_field in PII_FIELD_NAMES:
            assert pii_field not in summary

    def test_single_transaction_payload(self):
        single = {
            "transactions": [{
                "from_bank": "101",
                "from_account": "ACC_ALICE",
                "to_bank": "101",
                "to_account": "ACC_BOB",
                "amount": 500.0,
            }]
        }
        data = self._post(single)
        assert data["zero_pii"] is True
        assert "ACC_ALICE" not in str(data)
        assert "ACC_BOB" not in str(data)


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoint: POST /api/score-transaction — zero-PII guarantee
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreTransactionEndpointZeroPII:
    """The score-transaction endpoint must never expose account IDs or PII."""

    def _post(self, payload: dict) -> dict:
        resp = client.post(
            "/api/score-transaction", json=payload,
            headers={"X-API-Key": "dev-key-bank-a-local-only"},
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        return resp.json()

    def test_zero_pii_always_true(self):
        data = self._post(SWEEP_TX)
        assert data["zero_pii"] is True

    def test_account_ids_not_in_reasons(self):
        data = self._post(SWEEP_TX)
        reasons_text = " ".join(data.get("reasons", []))
        for account in ("0xMULE_01", "0xINTL_DEST"):
            assert account not in reasons_text, (
                f"Raw account ID '{account}' leaked into reasons"
            )

    def test_account_ids_not_in_pattern_hash(self):
        data = self._post(SWEEP_TX)
        ph = data.get("pattern_hash") or ""
        for account in ("0xMULE_01", "0xINTL_DEST"):
            assert account not in ph

    def test_no_pii_fields_in_response_keys(self):
        data = self._post(SWEEP_TX)
        for pii_field in PII_FIELD_NAMES:
            assert pii_field not in data, f"PII field '{pii_field}' found in response"

    def test_sensitive_tx_with_real_names(self):
        """Even if caller passes PII-like account names, they must not appear in output."""
        pii_tx = {
            "from_bank": "101",
            "from_account": "Mohammed-Al-Qahtani-IBAN-SA44-2000",
            "to_bank": "999",
            "to_account": "Fatima-Al-Zahrani-national_id-1234",
            "amount": 45_000.0,
            "payment_format": "SWIFT",
        }
        data = self._post(pii_tx)
        response_str = str(data)
        assert "Mohammed" not in response_str
        assert "Fatima" not in response_str
        assert "national_id" not in str(data.keys())
        assert data["zero_pii"] is True

    @pytest.mark.parametrize("pii_field,value", [
        ("name", "Ibrahim Al-Dosari"),
        ("iban", "SA44-2000-0001-1234"),
        ("national_id", "1234567890"),
        ("phone", "+966501234567"),
        ("email", "user@bank.sa"),
    ])
    def test_pii_in_account_field_not_reflected(self, pii_field: str, value: str):
        """PII embedded inside account strings must not appear verbatim in response."""
        tx = {
            "from_bank": "101",
            "from_account": f"{pii_field}:{value}",
            "to_bank": "101",
            "to_account": "DEST",
            "amount": 500.0,
        }
        data = self._post(tx)
        # The value must not be reflected verbatim in any field.
        assert value not in str(data), (
            f"PII value '{value}' reflected verbatim in score-transaction response"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-bank and model metrics endpoints — no PII in static reports
# ═══════════════════════════════════════════════════════════════════════════════

class TestStaticReportEndpoints:
    def test_model_metrics_no_pii_fields(self):
        resp = client.get("/api/model/metrics")
        assert resp.status_code == 200
        data = resp.json()
        for pii_field in PII_FIELD_NAMES:
            assert pii_field not in data, f"PII field '{pii_field}' in model metrics"

    def test_cross_bank_results_no_pii_fields(self):
        resp = client.get("/api/cross-bank/results")
        assert resp.status_code == 200
        data = resp.json()
        data_str = str(data)
        for pii_field in ("name", "iban", "account_id", "national_id", "phone", "email"):
            assert pii_field not in data.keys(), f"PII key '{pii_field}' in cross-bank results"

    def test_feature_importance_no_pii_fields(self):
        resp = client.get("/api/model/feature-importance")
        assert resp.status_code == 200
        data = resp.json()
        for pii_field in PII_FIELD_NAMES:
            assert pii_field not in data, f"PII field '{pii_field}' in feature importance"
