"""Formal proof-of-privacy tests for ml.src.privacy_hash (Phase 6).

These tests constitute the contractual guarantee that:
  1. Every category of PII (names, IBANs, account IDs, phone numbers,
     emails, national IDs, passports, IP addresses, etc.) is stripped
     before any payload leaves the bank.
  2. Two banks observing the same underlying AML pattern topology will
     produce identical hashes even if they use completely different
     account identifiers.
  3. Structurally different topologies produce different hashes.
  4. The hash format is stable: NSJ_<PATTERN_TYPE_UPPER>_<16-hex-chars>.
  5. Value bucketing is correct at tier boundaries.
  6. All functions are deterministic (same input → same output every call).

Run from repo root:
    pytest ml/tests/test_privacy_hash.py -v
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.src.privacy_hash import (
    PII_FIELDS,
    bucket_amount,
    bucket_count,
    bucket_risk,
    bucket_time_seconds,
    generate_pattern_hash,
    generate_topology_signature,
    normalize_pattern_features,
    pii_audit_report,
    remove_pii_fields,
    verify_zero_pii,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

CLEAN_FAN_IN = {
    "pattern_type": "fan_in",
    "risk_score": 0.75,
    "features": {
        "n_sources": 5,
        "total_in": 7_500.0,
        "in_banks": [1, 2, 3],
    },
}

PII_PAYLOAD = {
    "name": "Mohammed Al-Qahtani",
    "full_name": "Mohammed Ibrahim Al-Qahtani",
    "first_name": "Mohammed",
    "last_name": "Al-Qahtani",
    "iban": "SA44 2000 0001 2345 6789 1234",
    "bban": "000000001234567891234",
    "sort_code": "12-34-56",
    "routing_number": "021000021",
    "national_id": "1234567890",
    "national_number": "SA1234567",
    "ssn": "123-45-6789",
    "tin": "98-7654321",
    "passport": "A12345678",
    "driver_license": "DL-987654",
    "phone": "+966-50-1234567",
    "mobile": "+966501234567",
    "telephone": "+966112345678",
    "email": "m.alqahtani@example.sa",
    "email_address": "m.alqahtani@bank.sa",
    "account_id": "ACC_001_PRIV",
    "from_account": "ACCT-12345-SA",
    "to_account": "ACCT-67890-SA",
    "raw_id": "RAW_ID_XYZ",
    "src_id": "SRC_123",
    "dst_id": "DST_456",
    "ip_address": "10.0.1.55",
    "device_id": "DEVICE-A1B2C3",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "dob": "1985-03-15",
    "date_of_birth": "1985-03-15",
    # Non-PII fields that must survive
    "risk_score": 0.82,
    "pattern_type": "fan_in",
    "n_transactions": 7,
}


# ═══════════════════════════════════════════════════════════════════════════════
# PII_FIELDS registry
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIFieldRegistry:
    """The registry must cover every category of Saudi/AML sensitive data."""

    def test_personal_names_in_registry(self):
        for field in ("name", "full_name", "first_name", "last_name"):
            assert field in PII_FIELDS, f"'{field}' missing from PII_FIELDS"

    def test_financial_identifiers_in_registry(self):
        for field in ("iban", "bban", "sort_code", "routing_number"):
            assert field in PII_FIELDS, f"'{field}' missing from PII_FIELDS"

    def test_government_ids_in_registry(self):
        for field in ("national_id", "national_number", "ssn", "tin", "passport", "driver_license"):
            assert field in PII_FIELDS, f"'{field}' missing from PII_FIELDS"

    def test_contact_details_in_registry(self):
        for field in ("phone", "mobile", "telephone", "email", "email_address"):
            assert field in PII_FIELDS, f"'{field}' missing from PII_FIELDS"

    def test_account_ids_in_registry(self):
        for field in ("account_id", "from_account", "to_account", "raw_id", "src_id", "dst_id"):
            assert field in PII_FIELDS, f"'{field}' missing from PII_FIELDS"

    def test_digital_identifiers_in_registry(self):
        for field in ("ip_address", "device_id", "mac_address"):
            assert field in PII_FIELDS, f"'{field}' missing from PII_FIELDS"

    def test_biometric_dates_in_registry(self):
        for field in ("dob", "date_of_birth"):
            assert field in PII_FIELDS, f"'{field}' missing from PII_FIELDS"


# ═══════════════════════════════════════════════════════════════════════════════
# remove_pii_fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestRemovePIIFields:
    """Prove that every PII category is stripped from the payload."""

    def test_strips_personal_names(self):
        result = remove_pii_fields(PII_PAYLOAD)
        for field in ("name", "full_name", "first_name", "last_name"):
            assert field not in result, f"'{field}' survived remove_pii_fields"

    def test_strips_financial_ids(self):
        result = remove_pii_fields(PII_PAYLOAD)
        for field in ("iban", "bban", "sort_code", "routing_number"):
            assert field not in result, f"'{field}' survived remove_pii_fields"

    def test_strips_government_ids(self):
        result = remove_pii_fields(PII_PAYLOAD)
        for field in ("national_id", "national_number", "ssn", "tin", "passport", "driver_license"):
            assert field not in result, f"'{field}' survived remove_pii_fields"

    def test_strips_contact_details(self):
        result = remove_pii_fields(PII_PAYLOAD)
        for field in ("phone", "mobile", "telephone", "email", "email_address"):
            assert field not in result, f"'{field}' survived remove_pii_fields"

    def test_strips_account_ids(self):
        result = remove_pii_fields(PII_PAYLOAD)
        for field in ("account_id", "from_account", "to_account", "raw_id", "src_id", "dst_id"):
            assert field not in result, f"'{field}' survived remove_pii_fields"

    def test_strips_digital_identifiers(self):
        result = remove_pii_fields(PII_PAYLOAD)
        for field in ("ip_address", "device_id", "mac_address"):
            assert field not in result, f"'{field}' survived remove_pii_fields"

    def test_strips_dates_of_birth(self):
        result = remove_pii_fields(PII_PAYLOAD)
        for field in ("dob", "date_of_birth"):
            assert field not in result, f"'{field}' survived remove_pii_fields"

    def test_preserves_non_pii_fields(self):
        result = remove_pii_fields(PII_PAYLOAD)
        assert result["risk_score"] == 0.82
        assert result["pattern_type"] == "fan_in"
        assert result["n_transactions"] == 7

    def test_case_insensitive_matching(self):
        mixed_case = {"NAME": "Alice", "IBAN": "SA123", "risk": 0.5}
        result = remove_pii_fields(mixed_case)
        assert "NAME" not in result
        assert "IBAN" not in result
        assert result["risk"] == 0.5

    def test_recursive_nested_dict(self):
        nested = {
            "pattern_type": "fan_in",
            "metadata": {
                "account_id": "SENSITIVE_ID",
                "risk_tier": "high",
            },
        }
        result = remove_pii_fields(nested)
        assert "account_id" not in result["metadata"]
        assert result["metadata"]["risk_tier"] == "high"

    def test_recursive_list_of_dicts(self):
        with_list = {
            "pattern_type": "fan_in",
            "participants": [
                {"account_id": "ACC_1", "role": "source"},
                {"account_id": "ACC_2", "role": "destination"},
            ],
        }
        result = remove_pii_fields(with_list)
        for participant in result["participants"]:
            assert "account_id" not in participant
            assert "role" in participant

    def test_empty_dict_returns_empty(self):
        assert remove_pii_fields({}) == {}

    def test_all_pii_dict_returns_empty(self):
        all_pii = {field: "value" for field in PII_FIELDS}
        result = remove_pii_fields(all_pii)
        assert result == {}

    def test_returns_copy_not_mutation(self):
        original = {"account_id": "ACC", "amount": 100.0}
        original_copy = dict(original)
        remove_pii_fields(original)
        assert original == original_copy  # original unchanged


# ═══════════════════════════════════════════════════════════════════════════════
# verify_zero_pii
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyZeroPII:
    """verify_zero_pii must return False when ANY PII key exists."""

    def test_returns_true_for_clean_payload(self):
        clean = {"pattern_type": "fan_in", "risk_tier": "high", "n_sources": 5}
        assert verify_zero_pii(clean) is True

    def test_returns_false_when_name_present(self):
        assert verify_zero_pii({"name": "Alice", "risk": 0.5}) is False

    def test_returns_false_when_iban_present(self):
        assert verify_zero_pii({"iban": "SA1234", "risk": 0.5}) is False

    def test_returns_false_when_account_id_present(self):
        assert verify_zero_pii({"account_id": "ACC", "risk": 0.5}) is False

    def test_returns_false_when_phone_present(self):
        assert verify_zero_pii({"phone": "+966501234567"}) is False

    def test_returns_false_when_email_present(self):
        assert verify_zero_pii({"email": "a@b.com"}) is False

    def test_returns_false_when_national_id_present(self):
        assert verify_zero_pii({"national_id": "1234567890"}) is False

    def test_returns_false_when_src_id_present(self):
        assert verify_zero_pii({"src_id": "ACCT-1", "n": 3}) is False

    def test_returns_false_for_nested_pii(self):
        nested = {"pattern": {"from_account": "ACCT-1", "risk": 0.5}}
        assert verify_zero_pii(nested) is False

    def test_returns_false_for_pii_in_list(self):
        with_list = {"accounts": [{"account_id": "ACC"}]}
        assert verify_zero_pii(with_list) is False

    def test_returns_true_for_empty_dict(self):
        assert verify_zero_pii({}) is True

    def test_raises_for_deeply_nested_payload(self):
        deep = {"a": {}}
        node = deep
        for _ in range(11):
            node["a"] = {"a": {}}
            node = node["a"]
        with pytest.raises(ValueError, match="depth limit"):
            verify_zero_pii(deep)

    @pytest.mark.parametrize("field", sorted(PII_FIELDS))
    def test_all_pii_fields_detected(self, field: str):
        """Every field in PII_FIELDS must cause verify_zero_pii to return False."""
        assert verify_zero_pii({field: "value"}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Bucketing helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestBucketAmount:
    """Amount tiers: (≤1k micro) (≤10k small) (≤50k medium) (≤200k large) (>200k xlarge)."""

    def test_zero_is_micro(self):
        assert bucket_amount(0.0) == "micro"

    def test_boundary_1000_is_micro(self):
        assert bucket_amount(1_000.0) == "micro"

    def test_above_1000_is_small(self):
        assert bucket_amount(1_000.01) == "small"

    def test_boundary_10000_is_small(self):
        assert bucket_amount(10_000.0) == "small"

    def test_above_10000_is_medium(self):
        assert bucket_amount(10_000.01) == "medium"

    def test_boundary_50000_is_medium(self):
        assert bucket_amount(50_000.0) == "medium"

    def test_above_50000_is_large(self):
        assert bucket_amount(50_000.01) == "large"

    def test_boundary_200000_is_large(self):
        assert bucket_amount(200_000.0) == "large"

    def test_above_200000_is_xlarge(self):
        assert bucket_amount(200_000.01) == "xlarge"

    def test_very_large_is_xlarge(self):
        assert bucket_amount(1e9) == "xlarge"

    def test_same_tier_gives_same_label(self):
        assert bucket_amount(5_000.0) == bucket_amount(9_999.0) == "small"

    def test_different_tiers_give_different_labels(self):
        assert bucket_amount(500.0) != bucket_amount(500_000.0)


class TestBucketCount:
    """Count tiers: (≤2 single) (≤5 few) (≤15 moderate) (≤50 high) (>50 extreme)."""

    def test_1_is_single(self):
        assert bucket_count(1) == "single"

    def test_2_is_single(self):
        assert bucket_count(2) == "single"

    def test_3_is_few(self):
        assert bucket_count(3) == "few"

    def test_5_is_few(self):
        assert bucket_count(5) == "few"

    def test_6_is_moderate(self):
        assert bucket_count(6) == "moderate"

    def test_15_is_moderate(self):
        assert bucket_count(15) == "moderate"

    def test_16_is_high(self):
        assert bucket_count(16) == "high"

    def test_50_is_high(self):
        assert bucket_count(50) == "high"

    def test_51_is_extreme(self):
        assert bucket_count(51) == "extreme"


class TestBucketTime:
    """Time tiers: (≤60s rapid) (≤3600 within_1h) (≤86400 same_day) (≤604800 weekly) (>604800 extended)."""

    def test_30_seconds_is_rapid(self):
        assert bucket_time_seconds(30.0) == "rapid"

    def test_60_seconds_is_rapid(self):
        assert bucket_time_seconds(60.0) == "rapid"

    def test_61_seconds_is_within_1h(self):
        assert bucket_time_seconds(61.0) == "within_1h"

    def test_3600_is_within_1h(self):
        assert bucket_time_seconds(3_600.0) == "within_1h"

    def test_86400_is_same_day(self):
        assert bucket_time_seconds(86_400.0) == "same_day"

    def test_604800_is_weekly(self):
        assert bucket_time_seconds(604_800.0) == "weekly"

    def test_above_604800_is_extended(self):
        assert bucket_time_seconds(604_801.0) == "extended"


class TestBucketRisk:
    """Risk tiers: (≤0.4 low) (≤0.7 medium) (≤0.9 high) (≤1.0 critical)."""

    def test_0_is_low(self):
        assert bucket_risk(0.0) == "low"

    def test_0_4_is_low(self):
        assert bucket_risk(0.4) == "low"

    def test_0_5_is_medium(self):
        assert bucket_risk(0.5) == "medium"

    def test_0_7_is_medium(self):
        assert bucket_risk(0.7) == "medium"

    def test_0_8_is_high(self):
        assert bucket_risk(0.8) == "high"

    def test_0_9_is_high(self):
        assert bucket_risk(0.9) == "high"

    def test_0_91_is_critical(self):
        assert bucket_risk(0.91) == "critical"

    def test_1_is_critical(self):
        assert bucket_risk(1.0) == "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_pattern_features
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizePatternFeatures:
    """Core invariant: output is always PII-free and bucket-normalised."""

    def test_output_passes_verify_zero_pii(self):
        finding = {
            "pattern_type": "fan_in",
            "risk_score": 0.75,
            "accounts_involved": ["ACC_1", "ACC_2", "ACC_3"],
            "features": {
                "target": "ACC_1",
                "n_sources": 3,
                "total_in": 7_500.0,
            },
        }
        normalized = normalize_pattern_features(finding)
        assert verify_zero_pii(normalized), "Normalized output contains PII"

    def test_accounts_involved_removed(self):
        finding = {
            "pattern_type": "fan_in",
            "risk_score": 0.6,
            "accounts_involved": ["SA_IBAN_1", "SA_IBAN_2"],
            "features": {"n_sources": 2},
        }
        normalized = normalize_pattern_features(finding)
        assert "accounts_involved" not in normalized

    def test_identity_keys_in_features_removed(self):
        finding = {
            "pattern_type": "mule_velocity",
            "risk_score": 0.8,
            "features": {
                "target": "MULE_ACCOUNT_ID",
                "source": "SOURCE_ACCOUNT_ID",
                "hub": "HUB_ID",
                "n_inflows": 5,
                "total_amount": 8_000.0,
            },
        }
        normalized = normalize_pattern_features(finding)
        feats = normalized.get("features", {})
        for id_key in ("target", "source", "hub"):
            assert id_key not in feats, f"Identity key '{id_key}' leaked into normalized features"

    def test_amount_features_bucketed(self):
        finding = {
            "pattern_type": "fan_in",
            "risk_score": 0.6,
            "features": {"total_in": 7_500.0},
        }
        normalized = normalize_pattern_features(finding)
        assert normalized["features"]["total_in"] == "small"

    def test_count_features_bucketed(self):
        finding = {
            "pattern_type": "fan_in",
            "risk_score": 0.6,
            "features": {"n_sources": 4, "n_inflows": 10},
        }
        normalized = normalize_pattern_features(finding)
        assert normalized["features"]["n_sources"] == "few"
        assert normalized["features"]["n_inflows"] == "moderate"

    def test_risk_score_bucketed_into_tier(self):
        finding = {
            "pattern_type": "fan_in",
            "risk_score": 0.85,
            "features": {},
        }
        normalized = normalize_pattern_features(finding)
        assert normalized["risk_tier"] == "high"

    def test_pattern_type_preserved(self):
        finding = {"pattern_type": "mule_velocity", "risk_score": 0.7, "features": {}}
        normalized = normalize_pattern_features(finding)
        assert normalized["pattern_type"] == "mule_velocity"

    def test_pii_in_finding_root_stripped(self):
        finding = {
            "pattern_type": "fan_in",
            "risk_score": 0.6,
            "from_account": "ACCT-1234",
            "email": "user@bank.sa",
            "features": {},
        }
        normalized = normalize_pattern_features(finding)
        assert "from_account" not in normalized
        assert "email" not in normalized


# ═══════════════════════════════════════════════════════════════════════════════
# generate_pattern_hash — format and determinism
# ═══════════════════════════════════════════════════════════════════════════════

class TestGeneratePatternHash:
    """Hash format, determinism, and topology-sensitivity."""

    def test_output_format_nsj_prefix(self):
        normalized = normalize_pattern_features(CLEAN_FAN_IN)
        h = generate_pattern_hash(normalized)
        assert h.startswith("NSJ_"), f"Hash does not start with NSJ_: {h}"

    def test_output_format_16_hex_suffix(self):
        normalized = normalize_pattern_features(CLEAN_FAN_IN)
        h = generate_pattern_hash(normalized)
        parts = h.split("_")
        hex_part = parts[-1]
        assert len(hex_part) == 16, f"Hex suffix is not 16 chars: {hex_part}"
        int(hex_part, 16)  # raises ValueError if not valid hex

    def test_pattern_type_in_hash(self):
        normalized = normalize_pattern_features(CLEAN_FAN_IN)
        h = generate_pattern_hash(normalized)
        assert "FAN_IN" in h, f"Pattern type not in hash: {h}"

    def test_deterministic_same_input(self):
        normalized = normalize_pattern_features(CLEAN_FAN_IN)
        h1 = generate_pattern_hash(normalized)
        h2 = generate_pattern_hash(normalized)
        assert h1 == h2, "Hash is not deterministic"

    def test_deterministic_across_calls(self):
        finding = {
            "pattern_type": "mule_velocity",
            "risk_score": 0.82,
            "features": {"n_inflows": 5, "total_amount": 9_000.0, "window_minutes": 30},
        }
        normalized = normalize_pattern_features(finding)
        hashes = [generate_pattern_hash(normalized) for _ in range(10)]
        assert len(set(hashes)) == 1, "Hash is not stable across repeated calls"

    def test_different_pattern_types_differ(self):
        fan_in_norm = normalize_pattern_features(
            {"pattern_type": "fan_in", "risk_score": 0.7, "features": {"n_sources": 3}}
        )
        fan_out_norm = normalize_pattern_features(
            {"pattern_type": "fan_out", "risk_score": 0.7, "features": {"n_sources": 3}}
        )
        assert generate_pattern_hash(fan_in_norm) != generate_pattern_hash(fan_out_norm)

    def test_different_risk_tiers_differ(self):
        low_norm = normalize_pattern_features(
            {"pattern_type": "fan_in", "risk_score": 0.2, "features": {"n_sources": 3}}
        )
        high_norm = normalize_pattern_features(
            {"pattern_type": "fan_in", "risk_score": 0.9, "features": {"n_sources": 3}}
        )
        assert generate_pattern_hash(low_norm) != generate_pattern_hash(high_norm)

    def test_different_feature_values_differ(self):
        few_sources = normalize_pattern_features(
            {"pattern_type": "fan_in", "risk_score": 0.7, "features": {"n_sources": 3}}
        )
        many_sources = normalize_pattern_features(
            {"pattern_type": "fan_in", "risk_score": 0.7, "features": {"n_sources": 20}}
        )
        assert generate_pattern_hash(few_sources) != generate_pattern_hash(many_sources)


# ═══════════════════════════════════════════════════════════════════════════════
# KEY PRIVACY PROOF: same topology + different PII → same hash
# ═══════════════════════════════════════════════════════════════════════════════

class TestSameTopologyDifferentPIIProducesIdenticalHash:
    """This is the central claim of the Naseej thesis.

    Two banks observing the same mule-velocity pattern will produce matching
    hashes even if they use completely different account identifiers, IBANs,
    names, or other PII.  The hash encodes ONLY topology (pattern type, risk
    tier, bucketed feature values) — never identities.
    """

    def test_fan_in_same_topology_different_account_ids(self):
        finding_bank_a = {
            "pattern_type": "fan_in",
            "risk_score": 0.75,
            "accounts_involved": ["ACC_101", "ACC_202", "ACC_303"],
            "features": {
                "target": "ACC_101",
                "n_sources": 5,
                "total_in": 7_500.0,
                "in_banks": [1, 2],
            },
        }
        finding_bank_b = {
            "pattern_type": "fan_in",
            "risk_score": 0.75,
            "accounts_involved": ["IBAN_SA_ALPHA", "IBAN_SA_BETA", "IBAN_SA_GAMMA"],
            "features": {
                "target": "IBAN_SA_ALPHA",
                "n_sources": 5,
                "total_in": 7_800.0,  # slightly different raw amount — same bucket
                "in_banks": [1, 2],
            },
        }
        h_a = generate_pattern_hash(normalize_pattern_features(finding_bank_a))
        h_b = generate_pattern_hash(normalize_pattern_features(finding_bank_b))
        assert h_a == h_b, (
            f"Same topology / different PII produced different hashes.\n"
            f"  Bank A hash: {h_a}\n  Bank B hash: {h_b}\n"
            "This would break cross-bank pattern matching."
        )

    def test_mule_velocity_same_topology_different_iban_names(self):
        finding_bank_a = {
            "pattern_type": "mule_velocity",
            "risk_score": 0.82,
            "accounts_involved": ["ACC_MULE_SA_001"],
            "features": {
                "target": "ACC_MULE_SA_001",
                "window_minutes": 45,
                "n_inflows": 5,
                "total_amount": 12_000.0,
            },
        }
        finding_bank_b = {
            "pattern_type": "mule_velocity",
            "risk_score": 0.82,
            "accounts_involved": ["SA44-2000-0001-2345"],  # IBAN format
            "features": {
                "target": "SA44-2000-0001-2345",
                "window_minutes": 50,  # same bucket (within_1h when converted to seconds)
                "n_inflows": 5,
                "total_amount": 14_000.0,  # same bucket (small: ≤50k)
            },
        }
        h_a = generate_pattern_hash(normalize_pattern_features(finding_bank_a))
        h_b = generate_pattern_hash(normalize_pattern_features(finding_bank_b))
        assert h_a == h_b, (
            f"mule_velocity: same topology different IBANs produced different hashes.\n"
            f"  Bank A: {h_a}\n  Bank B: {h_b}"
        )

    def test_same_topology_different_person_names_match(self):
        base_features = {"n_sources": 3, "total_in": 5_500.0}
        finding_with_name_a = {
            "pattern_type": "fan_in",
            "risk_score": 0.65,
            "name": "Ibrahim Al-Dosari",
            "from_account": "ACC_IBRAHIM_001",
            "features": dict(base_features),
        }
        finding_with_name_b = {
            "pattern_type": "fan_in",
            "risk_score": 0.65,
            "name": "Fatima Al-Zahrani",
            "from_account": "ACC_FATIMA_002",
            "features": dict(base_features),
        }
        h_a = generate_pattern_hash(normalize_pattern_features(finding_with_name_a))
        h_b = generate_pattern_hash(normalize_pattern_features(finding_with_name_b))
        assert h_a == h_b, "Person names caused topology mismatch — PII is leaking into hash"

    def test_national_id_difference_does_not_split_hash(self):
        """National IDs from two different account holders must not affect the hash."""
        finding_a = {
            "pattern_type": "scatter_gather",
            "risk_score": 0.72,
            "national_id": "1098765432",
            "ssn": "123-45-6789",
            "features": {"n_legs": 4, "total_out": 25_000.0},
        }
        finding_b = {
            "pattern_type": "scatter_gather",
            "risk_score": 0.72,
            "national_id": "9876543210",
            "ssn": "987-65-4321",
            "features": {"n_legs": 4, "total_out": 28_000.0},  # same bucket
        }
        h_a = generate_pattern_hash(normalize_pattern_features(finding_a))
        h_b = generate_pattern_hash(normalize_pattern_features(finding_b))
        assert h_a == h_b

    def test_ip_and_device_id_do_not_split_hash(self):
        finding_a = {
            "pattern_type": "rapid_sweep",
            "risk_score": 0.88,
            "ip_address": "10.0.1.100",
            "device_id": "DEVICE-A1",
            "features": {"ratio": 0.90, "out_amount": 9_000.0},
        }
        finding_b = {
            "pattern_type": "rapid_sweep",
            "risk_score": 0.88,
            "ip_address": "192.168.50.200",
            "device_id": "DEVICE-B2",
            "features": {"ratio": 0.90, "out_amount": 9_500.0},  # same bucket
        }
        h_a = generate_pattern_hash(normalize_pattern_features(finding_a))
        h_b = generate_pattern_hash(normalize_pattern_features(finding_b))
        assert h_a == h_b


# ═══════════════════════════════════════════════════════════════════════════════
# generate_topology_signature
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateTopologySignature:
    """Topology signature encodes graph structure without node identities."""

    def test_format_nsj_topo_prefix(self):
        edges = [("A", "B", 1000.0), ("C", "B", 2000.0)]
        sig = generate_topology_signature(edges)
        assert sig.startswith("NSJ_TOPO_"), f"Unexpected format: {sig}"

    def test_format_16_hex_suffix(self):
        edges = [("A", "B", 1000.0)]
        sig = generate_topology_signature(edges)
        hex_part = sig.split("_")[-1]
        assert len(hex_part) == 16
        int(hex_part, 16)

    def test_deterministic(self):
        edges = [("A", "B", 1000.0), ("C", "B", 2000.0), ("D", "B", 500.0)]
        s1 = generate_topology_signature(edges)
        s2 = generate_topology_signature(edges)
        assert s1 == s2

    def test_same_structure_different_node_labels(self):
        """Star-shaped (3 sources → 1 hub): node names must not change the signature."""
        star_alpha = [("A", "HUB", 5_000.0), ("B", "HUB", 4_000.0), ("C", "HUB", 6_000.0)]
        star_bravo = [("X1", "CTR", 5_500.0), ("X2", "CTR", 3_800.0), ("X3", "CTR", 5_800.0)]
        sig_a = generate_topology_signature(star_alpha)
        sig_b = generate_topology_signature(star_bravo)
        assert sig_a == sig_b, (
            f"Same star topology, different node names produced different signatures.\n"
            f"  Alpha: {sig_a}\n  Bravo: {sig_b}"
        )

    def test_different_structure_produces_different_signature(self):
        linear = [("A", "B", 1000.0), ("B", "C", 1000.0)]
        star   = [("A", "C", 1000.0), ("B", "C", 1000.0)]
        assert generate_topology_signature(linear) != generate_topology_signature(star)

    def test_different_edge_count_differs(self):
        two_edges   = [("A", "B", 1000.0), ("C", "B", 1000.0)]
        three_edges = [("A", "B", 1000.0), ("C", "B", 1000.0), ("D", "B", 1000.0)]
        assert generate_topology_signature(two_edges) != generate_topology_signature(three_edges)

    def test_amounts_in_different_buckets_differ(self):
        micro_edges = [("A", "B", 500.0)]    # bucket: micro
        large_edges = [("A", "B", 100_000.0)] # bucket: large
        assert generate_topology_signature(micro_edges) != generate_topology_signature(large_edges)

    def test_amounts_in_same_bucket_match(self):
        """Node labels differ; amounts differ but fall in same bucket → same signature."""
        edges_a = [("ALICE", "BOB", 3_000.0)]   # small bucket
        edges_b = [("NODE1", "NODE2", 8_000.0)]  # small bucket
        assert generate_topology_signature(edges_a) == generate_topology_signature(edges_b)

    def test_bank_a_iban_vs_bank_b_account_numbers_same_topology(self):
        """The critical cross-bank case: same SRC→MULE→INTL chain, different IDs."""
        chain_bank_a = [
            ("SA44_001", "SA44_MULE", 2_400.0),
            ("SA44_002", "SA44_MULE", 1_850.0),
            ("SA44_003", "SA44_MULE", 3_100.0),
            ("SA44_MULE", "SA44_INTL", 8_000.0),
        ]
        chain_bank_b = [
            ("ACC_X1", "ACC_HUB", 2_600.0),   # amounts in same buckets
            ("ACC_X2", "ACC_HUB", 1_700.0),
            ("ACC_X3", "ACC_HUB", 3_300.0),
            ("ACC_HUB", "ACC_DEST", 7_500.0),
        ]
        sig_a = generate_topology_signature(chain_bank_a)
        sig_b = generate_topology_signature(chain_bank_b)
        assert sig_a == sig_b, (
            f"Same SWIFT-chain topology, different IBANs produced different signatures.\n"
            f"  Bank A: {sig_a}\n  Bank B: {sig_b}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# pii_audit_report
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIAuditReport:
    """The audit report must document what was stripped and bucketed."""

    def _make_report(self) -> dict:
        original = {
            "pattern_type": "fan_in",
            "risk_score": 0.75,
            "account_id": "ACC_SECRET",
            "iban": "SA44-0000-1234",
            "features": {"n_sources": 5, "total_in": 7_500.0},
        }
        normalized = normalize_pattern_features(original)
        return pii_audit_report(original, normalized)

    def test_zero_pii_flag_is_true(self):
        report = self._make_report()
        assert report["zero_pii"] is True

    def test_stripped_pii_keys_listed(self):
        report = self._make_report()
        stripped = report["stripped_pii_keys"]
        assert isinstance(stripped, list)
        assert len(stripped) > 0, "Expected stripped PII keys in audit report"

    def test_account_id_in_stripped_list(self):
        report = self._make_report()
        assert "account_id" in report["stripped_pii_keys"]

    def test_pattern_hash_generated(self):
        report = self._make_report()
        ph = report.get("pattern_hash")
        assert ph is not None
        assert ph.startswith("NSJ_")

    def test_bucketed_fields_reported(self):
        report = self._make_report()
        bucketed = report["bucketed_fields"]
        assert isinstance(bucketed, list)

    def test_note_field_present(self):
        report = self._make_report()
        assert "note" in report
        assert len(report["note"]) > 0

    def test_audit_on_clean_payload_has_no_stripped_keys(self):
        original = {"pattern_type": "fan_in", "risk_score": 0.7, "features": {"n_sources": 3}}
        normalized = normalize_pattern_features(original)
        report = pii_audit_report(original, normalized)
        assert report["zero_pii"] is True
        assert report["stripped_pii_keys"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-end integration: full pattern → hash pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndToEndHashPipeline:
    """Simulate the full flow used by the backend services."""

    def test_fan_in_finding_produces_zero_pii_hash(self):
        raw_finding = {
            "pattern_type": "fan_in",
            "risk_score": 0.75,
            "reason": "Account received from 5 sources.",
            "accounts_involved": ["ACC_1", "ACC_2", "ACC_3"],
            "features": {"target": "ACC_1", "n_sources": 5, "total_in": 7_500.0},
        }
        clean = normalize_pattern_features(raw_finding)
        assert verify_zero_pii(clean), "normalize_pattern_features produced PII output"
        h = generate_pattern_hash(clean)
        assert h.startswith("NSJ_FAN_IN_")

    def test_mule_velocity_finding_produces_valid_hash(self):
        raw_finding = {
            "pattern_type": "mule_velocity",
            "risk_score": 0.82,
            "reason": "5 inflows totalling 12000 within 45m.",
            "accounts_involved": ["MULE_ACCT"],
            "features": {
                "target": "MULE_ACCT",
                "window_minutes": 45,
                "n_inflows": 5,
                "total_amount": 12_000.0,
            },
        }
        clean = normalize_pattern_features(raw_finding)
        assert verify_zero_pii(clean)
        h = generate_pattern_hash(clean)
        assert h.startswith("NSJ_MULE_VELOCITY_")

    def test_pii_audit_consistent_with_hash(self):
        raw = {
            "pattern_type": "rapid_sweep",
            "risk_score": 0.88,
            "src_id": "SENSITIVE_SRC",
            "features": {"ratio": 0.92, "out_amount": 9_200.0},
        }
        normalized = normalize_pattern_features(raw)
        report = pii_audit_report(raw, normalized)
        h_from_report = report["pattern_hash"]
        h_direct = generate_pattern_hash(normalized)
        assert h_from_report == h_direct, "pii_audit_report hash differs from direct generate_pattern_hash"
