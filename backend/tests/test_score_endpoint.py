"""Phase 7 endpoint tests — POST /api/score-transaction.

Run from repo root:
    pytest backend/tests/test_score_endpoint.py -v

Tests verify:
  - Response schema matches ScoreOut (risk_score, prediction, reasons, zero_pii, source)
  - Model path produces source="model" when bundle is available
  - Fallback path produces source="fallback" when bundle is mocked away
  - High-risk inputs produce higher risk scores than low-risk inputs
  - Responses never expose raw account IDs or PII
  - Pattern hash format is correct (NSJ_... prefix)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


# ── Fixture payloads ──────────────────────────────────────────────────────────

BENIGN_TX = {
    "timestamp": "2024/06/15 10:30",
    "from_bank": "101",
    "from_account": "ACC_DOMESTIC_001",
    "to_bank": "101",
    "to_account": "ACC_DOMESTIC_002",
    "amount": 500.0,
    "currency": "US Dollar",
    "payment_format": "ACH",
}

HIGH_RISK_TX = {
    "timestamp": "2024/06/15 02:15",  # off-hours
    "from_bank": "101",
    "from_account": "ACC_SUSPICIOUS_001",
    "to_bank": "28856",              # cross-bank
    "to_account": "ACC_OFFSHORE_001",
    "amount": 95_000.0,              # large amount
    "currency": "US Dollar",
    "payment_format": "Wire",
}

CRYPTO_TX = {
    "timestamp": "2024/06/15 03:00",  # off-hours
    "from_bank": "200",
    "from_account": "ACC_CRYPTO_001",
    "to_bank": "999",
    "to_account": "ACC_CRYPTO_002",
    "amount": 75_000.0,
    "currency": "Bitcoin",
    "payment_format": "Bitcoin",
}

MINIMAL_TX = {
    "from_bank": "1",
    "from_account": "ACC_A",
    "to_bank": "1",
    "to_account": "ACC_B",
    "amount": 100.0,
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _post(payload: dict) -> dict:
    resp = client.post(
        "/api/score-transaction", json=payload,
        headers={"X-API-Key": "dev-key-bank-a-local-only"},
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    return resp.json()


# ── Schema tests ──────────────────────────────────────────────────────────────

class TestResponseSchema:
    def test_required_fields_present(self):
        data = _post(BENIGN_TX)
        assert "risk_score" in data
        assert "prediction" in data
        assert "reasons" in data
        assert "zero_pii" in data
        assert "source" in data

    def test_risk_score_in_range(self):
        data = _post(BENIGN_TX)
        assert 0.0 <= data["risk_score"] <= 1.0

    def test_prediction_valid_enum(self):
        data = _post(BENIGN_TX)
        assert data["prediction"] in ("benign", "suspicious", "block")

    def test_zero_pii_always_true(self):
        data = _post(BENIGN_TX)
        assert data["zero_pii"] is True

    def test_reasons_is_list(self):
        data = _post(BENIGN_TX)
        assert isinstance(data["reasons"], list)
        assert len(data["reasons"]) > 0

    def test_pattern_hash_format(self):
        data = _post(BENIGN_TX)
        ph = data.get("pattern_hash")
        if ph is not None:
            assert ph.startswith("NSJ_"), f"Unexpected hash format: {ph}"

    def test_minimal_payload_accepted(self):
        data = _post(MINIMAL_TX)
        assert "risk_score" in data

    def test_source_field_valid(self):
        data = _post(BENIGN_TX)
        assert data["source"] in ("model", "fallback")


# ── Model vs fallback ─────────────────────────────────────────────────────────

class TestModelPath:
    def test_model_source_when_bundle_loaded(self):
        """If baseline_model.joblib exists, source should be 'model'."""
        from backend.app.services import model_service
        if model_service.get_bundle() is not None:
            data = _post(BENIGN_TX)
            assert data["source"] == "model", (
                "Bundle is present but endpoint still returned source='fallback'. "
                "Check scoring_service.score()."
            )
        else:
            pytest.skip("baseline_model.joblib not present — skipping model-path test")

    def test_fallback_source_when_bundle_absent(self):
        """When bundle is mocked away, source must be 'fallback'."""
        with patch("backend.app.services.model_service.get_bundle", return_value=None):
            # Reset the scoring service's cache indirectly by patching at service level.
            with patch("backend.app.services.scoring_service.model_service.get_bundle", return_value=None):
                data = _post(BENIGN_TX)
        assert data["source"] == "fallback"

    def test_fallback_gives_valid_schema(self):
        with patch("backend.app.services.scoring_service.model_service.get_bundle", return_value=None):
            data = _post(BENIGN_TX)
        assert 0.0 <= data["risk_score"] <= 1.0
        assert data["prediction"] in ("benign", "suspicious", "block")
        assert data["zero_pii"] is True


# ── Risk ordering ─────────────────────────────────────────────────────────────

class TestRiskOrdering:
    def test_model_sensitive_to_inputs(self):
        """Model must produce different scores for structurally different inputs.

        Note: without account history, scores are dominated by payment_type_enc
        which the XGBoost trees split in data-driven directions. We cannot assert
        a human-intuitive high/low ordering without history — only that the model
        responds differently to different inputs.
        """
        scores = {
            "benign_ach": _post(BENIGN_TX)["risk_score"],
            "high_risk_wire": _post(HIGH_RISK_TX)["risk_score"],
            "crypto": _post(CRYPTO_TX)["risk_score"],
        }
        # All scores must be in valid range.
        for label, s in scores.items():
            assert 0.0 <= s <= 1.0, f"{label} score out of range: {s}"
        # At least two distinct values — model is not returning a constant.
        assert len(set(scores.values())) > 1, (
            f"Model returned identical scores for all inputs: {scores}. "
            "Feature vector construction may be broken."
        )

    def test_cross_bank_changes_score(self):
        """Toggling from_bank vs to_bank must change the risk score."""
        same_bank = {**HIGH_RISK_TX, "to_bank": HIGH_RISK_TX["from_bank"]}
        diff_bank = HIGH_RISK_TX
        score_same = _post(same_bank)["risk_score"]
        score_diff = _post(diff_bank)["risk_score"]
        # The two scores must differ (is_cross_bank feature must matter).
        assert score_same != score_diff, (
            "is_cross_bank flag had no effect on score. Feature may not be wired."
        )

    def test_crypto_tx_not_below_domestic(self):
        domestic = _post(BENIGN_TX)["risk_score"]
        crypto = _post(CRYPTO_TX)["risk_score"]
        assert crypto >= domestic


# ── PII safety ────────────────────────────────────────────────────────────────

class TestZeroPII:
    _PII_STRINGS = [
        "ACC_SUSPICIOUS_001", "ACC_OFFSHORE_001",
        "ACC_DOMESTIC_001", "ACC_DOMESTIC_002",
        "ACC_CRYPTO_001", "ACC_CRYPTO_002",
    ]

    def test_no_raw_account_id_in_reasons(self):
        data = _post(HIGH_RISK_TX)
        reasons_text = " ".join(data["reasons"])
        for pii in self._PII_STRINGS:
            assert pii not in reasons_text, (
                f"Raw account ID '{pii}' leaked into reasons: {reasons_text}"
            )

    def test_no_raw_account_id_in_hash(self):
        data = _post(HIGH_RISK_TX)
        ph = data.get("pattern_hash", "") or ""
        for pii in self._PII_STRINGS:
            assert pii not in ph


# ── Explanations ──────────────────────────────────────────────────────────────

class TestExplanations:
    def test_cross_bank_mention_in_high_risk(self):
        data = _post(HIGH_RISK_TX)
        reasons_text = " ".join(data["reasons"]).lower()
        assert "cross-bank" in reasons_text or "cross_bank" in reasons_text

    def test_off_hours_mention_in_night_tx(self):
        data = _post(HIGH_RISK_TX)
        reasons_text = " ".join(data["reasons"]).lower()
        assert "off-hours" in reasons_text or "hour" in reasons_text

    def test_velocity_limitation_disclosed(self):
        data = _post(BENIGN_TX)
        reasons_text = " ".join(data["reasons"]).lower()
        assert "velocity" in reasons_text or "history" in reasons_text


# ── Feature extraction unit tests ────────────────────────────────────────────

class TestFeatureExtraction:
    def test_cross_bank_flag(self):
        from backend.app.services.scoring_service import build_feature_vector
        tx = type("T", (), {
            "timestamp": "2024/06/15 10:30",
            "from_bank": "101",
            "to_bank": "999",
            "amount": 1000.0,
            "currency": "US Dollar",
            "payment_format": "ACH",
        })()
        cols = ["is_cross_bank", "cross_bank_flow_flag", "amount", "hour", "day_of_week"]
        df = build_feature_vector(tx, cols)
        assert df["is_cross_bank"].iloc[0] == 1.0
        assert df["amount"].iloc[0] == 1000.0
        assert df["hour"].iloc[0] == 10.0

    def test_same_bank_flag(self):
        from backend.app.services.scoring_service import build_feature_vector
        tx = type("T", (), {
            "timestamp": "2024/06/15 10:30",
            "from_bank": "101",
            "to_bank": "101",
            "amount": 500.0,
            "currency": "US Dollar",
            "payment_format": "ACH",
        })()
        cols = ["is_cross_bank", "same_bank_transfer"]
        df = build_feature_vector(tx, cols)
        assert df["is_cross_bank"].iloc[0] == 0.0
        assert df["same_bank_transfer"].iloc[0] == 1.0

    def test_known_payment_type_encoded(self):
        from backend.app.services.scoring_service import build_feature_vector, PAYMENT_TYPE_MAP
        tx = type("T", (), {
            "timestamp": None, "from_bank": "1", "to_bank": "2",
            "amount": 100.0, "currency": None, "payment_format": "SWIFT",
        })()
        df = build_feature_vector(tx, ["payment_type_enc"])
        assert df["payment_type_enc"].iloc[0] == float(PAYMENT_TYPE_MAP["SWIFT"])

    def test_unknown_payment_type_is_minus_one(self):
        from backend.app.services.scoring_service import build_feature_vector
        tx = type("T", (), {
            "timestamp": None, "from_bank": "1", "to_bank": "2",
            "amount": 100.0, "currency": None, "payment_format": "NotAType",
        })()
        df = build_feature_vector(tx, ["payment_type_enc"])
        assert df["payment_type_enc"].iloc[0] == -1.0

    def test_unknown_column_defaults_to_zero(self):
        from backend.app.services.scoring_service import build_feature_vector
        tx = type("T", (), {
            "timestamp": None, "from_bank": "1", "to_bank": "2",
            "amount": 100.0, "currency": None, "payment_format": None,
        })()
        df = build_feature_vector(tx, ["source_out_tx_count_24h", "account_pair_tx_count_before"])
        assert df["source_out_tx_count_24h"].iloc[0] == 0.0
        assert df["account_pair_tx_count_before"].iloc[0] == 0.0
