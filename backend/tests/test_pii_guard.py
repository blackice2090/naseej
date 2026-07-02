"""Zero-PII guard unit tests — Arabic names, IBANs, phones, account ids.

Run from repo root:
    pytest backend/tests/test_pii_guard.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services import pii_guard


def violations_for(text: str) -> list[str]:
    return pii_guard.find_pii({"evidence_summary": text})


class TestArabicContent:
    """v1 exchange objects are English-only: Arabic free text may embed
    personal names, so the guard fails closed on any Arabic script."""

    def test_arabic_full_name_rejected(self):
        assert violations_for("Account holder محمد العتيبي moved funds")

    def test_arabic_only_text_rejected(self):
        assert violations_for("تحويل مشبوه إلى حساب خارجي")

    def test_single_arabic_character_rejected(self):
        assert violations_for("suspicious transfer ب")


class TestIbanLikeStrings:
    def test_saudi_iban_compact(self):
        assert violations_for("swept to SA4420000001234567891234 overnight")

    def test_saudi_iban_spaced(self):
        assert violations_for("IBAN SA44 2000 0001 2345 6789 1234 involved")

    def test_foreign_iban(self):
        assert violations_for("destination DE89370400440532013000")


class TestPhoneLikeStrings:
    def test_international_format(self):
        assert violations_for("contact at +966512345678")

    def test_international_with_spaces(self):
        assert violations_for("called +966 51 234 5678 twice")

    def test_local_format(self):
        assert violations_for("registered mobile 0512345678")

    def test_bare_msisdn(self):
        assert violations_for("MSISDN 966512345678 linked")


class TestRawAccountIdentifiers:
    def test_dataset_style_account(self):
        assert violations_for("funds gathered in ACC_MULE_SA_001")

    def test_demo_style_handle(self):
        assert violations_for("matched handle 0xMULE_01")

    def test_long_digit_run(self):
        assert violations_for("account 12345678 received five transfers")


class TestOtherPii:
    def test_email_rejected(self):
        assert violations_for("notified analyst@bank.example.sa")

    def test_forbidden_key_top_level(self):
        assert pii_guard.find_pii({"iban": "anything"})

    def test_forbidden_key_nested(self):
        assert pii_guard.find_pii({"meta": {"customer_iban": "x"}})

    def test_forbidden_key_in_list_items(self):
        assert pii_guard.find_pii({"items": [{"national_id": "x"}]})

    def test_raw_transactions_key_rejected(self):
        assert pii_guard.find_pii({"raw_transactions": []})

    def test_device_id_key_rejected(self):
        assert pii_guard.find_pii({"device_id": "x"})


class TestCleanContentPasses:
    def test_contract_example_summary_passes(self):
        clean = (
            "Fan-in of 5 sub-threshold transfers into a single account within "
            "40 minutes, followed by an international wire sweep of the "
            "accumulated balance."
        )
        assert violations_for(clean) == []

    def test_bucket_labels_pass(self):
        assert pii_guard.find_pii({
            "velocity_features": {
                "window_bucket": "under_1h",
                "tx_count_bucket": "2_to_5",
                "amount_bucket": "5k_to_25k",
            }
        }) == []

    def test_format_pinned_fields_exempt_from_content_rules(self):
        # An all-digit hex hash must not trip the digit-run rule: the schema
        # pins these fields' formats, the guard skips content checks there.
        assert pii_guard.find_pii({
            "pattern_id": "7f3c9a1e-2b4d-4e8f-9a6c-1d5e8b3f7a20",
            "pattern_hash": "NSJ_FAN_IN_1234567890123456",
            "detection_timestamp": "2026-06-11T09:42:00Z",
            "source_node_id": "NODE_A7C2F9E1",
        }) == []

    def test_reasons_never_echo_the_matched_value(self):
        out = violations_for("swept to SA4420000001234567891234 overnight")
        assert out
        assert all("SA44" not in v for v in out)


class TestFailClosed:
    def test_self_referencing_object_is_a_violation(self):
        cyclic: dict = {}
        cyclic["self"] = cyclic
        out = pii_guard.find_pii(cyclic)
        assert out, "guard must fail closed on unscannable input"
        assert any("failing closed" in v for v in out)

    def test_verify_zero_pii_is_boolean_twin(self):
        assert pii_guard.verify_zero_pii({"summary": "clean text"}) is True
        assert pii_guard.verify_zero_pii({"iban": "x"}) is False
