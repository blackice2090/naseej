"""Zero-PII guard for objects leaving the bank boundary.

Defense-in-depth behind the JSON Schema gate: the schema rejects unknown
*fields*, this guard also rejects PII *content* smuggled inside permitted
string fields (e.g. an IBAN pasted into ``evidence_summary``).

Checks, all recursive:
  1. Forbidden key names (name, iban, account_number, national_id, phone,
     email, raw_transaction, device_id, ...).
  2. String-content patterns: IBAN-like tokens, phone-like numbers, long
     digit runs (account-number-like), email addresses, demo/account-style
     handles (ACC_*, 0x*).
  3. Arabic script. v1 network exchange is English-only because free text in
     Arabic cannot be reliably distinguished from personal names — so the
     guard fails closed on any Arabic content. This is a documented v1
     limitation, not a product stance; Arabic-capable PII detection is a
     post-MVP work item.

Fields whose exact format the JSON Schema already pins (hash, UUID,
timestamp, node id) are exempt from *content* rules only — e.g. a legitimate
16-hex pattern hash that happens to be all digits must not trip the
digit-run rule. They are never exempt from the schema gate itself.

Fail-closed contract: any internal error counts as a violation. Violation
messages name the field and rule but never echo the matched value, so
rejection reasons are safe to store in audit logs.
"""

from __future__ import annotations

import re
from typing import Any

# Exact-match forbidden keys (lowercase). Broad on purpose.
FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "name", "full_name", "first_name", "last_name", "customer_name", "holder_name",
    "iban", "bban", "account_number", "account_id", "account", "account_no",
    "from_account", "to_account", "src_id", "dst_id",
    "national_id", "national_number", "iqama", "ssn", "tin", "passport",
    "driver_license", "drivers_license",
    "phone", "phone_number", "mobile", "telephone", "msisdn",
    "email", "email_address",
    "raw_transaction", "raw_transactions", "transaction", "transactions",
    "device_id", "ip", "ip_address", "mac_address", "imei",
    "date_of_birth", "dob", "birthdate", "address", "street_address",
})

# Substring-match key fragments — catch e.g. "customer_iban", "sender_national_id".
FORBIDDEN_KEY_FRAGMENTS: tuple[str, ...] = (
    "iban", "national_id", "passport", "account_number",
    "date_of_birth", "raw_transaction", "device_id",
)

# Arabic, Arabic Supplement, Arabic Extended-A, Arabic Presentation Forms A/B.
_ARABIC = r"؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿"

# Content patterns. Each entry: (rule name, compiled regex).
CONTENT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Two letters + two digits + long alphanumeric tail (IBAN shape, e.g. SA44...).
    ("iban-like token", re.compile(r"\b[A-Z]{2}\d{2}[ \-]?[A-Z0-9][ \-A-Z0-9]{8,}\b")),
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone-like number", re.compile(r"\+\d[\d \-]{7,}|\b0\d{9,}\b|\b9665\d{8}\b")),
    # 8+ consecutive digits: account numbers, card numbers, raw phone digits.
    ("long digit run", re.compile(r"\d{8,}")),
    # Raw account handles — both AML-dataset style and demo style.
    ("account-style identifier", re.compile(r"\bACC[_\-][A-Za-z0-9_\-]{2,}\b|\b0x[A-Za-z0-9_]{3,}\b")),
    ("arabic script (v1 exchange is English-only — may embed names)",
     re.compile(f"[{_ARABIC}]")),
)

# Format-pinned by the JSON Schema — content rules skipped, key rules still apply.
CONTENT_EXEMPT_PATHS: frozenset[str] = frozenset({
    "$.pattern_id",
    "$.pattern_hash",
    "$.detection_timestamp",
    "$.source_node_id",
})


def _scan(obj: Any, path: str, violations: list[str], exempt: frozenset[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).strip().lower()
            child = f"{path}.{key}"
            if key_l in FORBIDDEN_KEYS or any(f in key_l for f in FORBIDDEN_KEY_FRAGMENTS):
                violations.append(f"{child}: forbidden PII field name")
            _scan(value, child, violations, exempt)
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            _scan(item, f"{path}[{i}]", violations, exempt)
    elif isinstance(obj, str):
        if path in exempt:
            return  # format-pinned field: skip CONTENT rules (key-name rules still applied above)
        for rule, pattern in CONTENT_RULES:
            if pattern.search(obj):
                violations.append(f"{path}: contains {rule}")


def find_pii(obj: Any, extra_exempt_paths: frozenset[str] | set[str] | None = None) -> list[str]:
    """Return all PII violations found in *obj*. Fail-closed on errors.

    ``extra_exempt_paths`` (e.g. ``{"$.feedback_id", "$.audit_ref"}``) are
    additional CONTENT-exempt paths for server-generated, format-pinned id/ref
    fields (UUIDs, SHA-256 refs) that would otherwise trip the digit-run rule.
    Forbidden-key-NAME rules still apply to those paths, so a field literally
    named e.g. ``iban`` is still rejected.
    """
    exempt = CONTENT_EXEMPT_PATHS | (frozenset(extra_exempt_paths) if extra_exempt_paths else frozenset())
    violations: list[str] = []
    try:
        _scan(obj, "$", violations, exempt)
    except Exception as exc:  # fail closed: an unscannable object is a violation
        violations.append(f"$: guard error ({type(exc).__name__}) — failing closed")
    return violations


def verify_zero_pii(obj: Any) -> bool:
    """True iff the guard finds no PII. The boolean twin of find_pii()."""
    return not find_pii(obj)


# ── transaction-ingestion guard (feature store) ────────────────────────────
#
# The network-boundary guard above treats *any* account field as PII because
# raw handles must never leave the bank. The feature store is different: it
# lives INSIDE one node's boundary and its whole job is windowing over
# pseudonymous handles. So ingestion uses this dedicated profile:
#
#   * handle fields are allowed to exist, but their VALUES must look like
#     synthetic/pseudonymous handles — no IBAN shapes, no 8+ digit runs,
#     no phone/email patterns, no Arabic, no spaces (names);
#   * every other string field still gets the full content rules;
#   * unknown fields are rejected (the Pydantic schema also forbids them —
#     this is defense-in-depth, same layering as the pattern registry).
#
# Known limitation (documented in docs/FEATURE_STORE.md): a concatenated
# real name ("MohammedAli") is indistinguishable from a synthetic handle.
# The guard blocks PII *shapes*, it cannot prove a handle is synthetic.

TX_ALLOWED_KEYS: frozenset[str] = frozenset({
    "transaction_id", "timestamp", "source_node_id",
    "from_bank", "from_account", "to_bank", "to_account",
    "amount", "currency", "payment_format",
})

# Pseudonymous handle shape: compact token, no spaces / @ / +.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-\.]{1,63}$")
# Transaction ids additionally allow # and : (demo ids look like TX#ATK_01).
_TX_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-\.#:]{0,63}$")
_BANK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-\.]{0,31}$")
_TS_SHAPE_RE = re.compile(r"^[0-9TZz:\-\+\. /]{8,40}$")

# Content rules minus "account-style identifier" — handles ARE account-style
# identifiers here, by design. Everything PII-shaped still applies.
_HANDLE_CONTENT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rule, pattern) for rule, pattern in CONTENT_RULES
    if rule != "account-style identifier"
)


def _check_handle(field: str, value: Any, violations: list[str], *,
                  shape: re.Pattern[str] = _HANDLE_RE,
                  skip_digit_run: bool = False) -> None:
    if not isinstance(value, str) or not shape.match(value):
        violations.append(f"$.{field}: not a pseudonymous handle (shape rule)")
        return
    for rule, pattern in _HANDLE_CONTENT_RULES:
        if skip_digit_run and rule == "long digit run":
            continue
        if pattern.search(value):
            violations.append(f"$.{field}: contains {rule}")


def find_transaction_pii(payload: dict[str, Any]) -> list[str]:
    """PII violations in a feature-store ingestion payload. Fail-closed.

    Violation messages name the field and rule but never echo the value.
    """
    violations: list[str] = []
    try:
        if not isinstance(payload, dict):
            return ["$: payload must be a JSON object"]

        for key in payload:
            key_l = str(key).strip().lower()
            if key_l not in TX_ALLOWED_KEYS:
                if key_l in FORBIDDEN_KEYS or any(f in key_l for f in FORBIDDEN_KEY_FRAGMENTS):
                    violations.append(f"$.{key}: forbidden PII field name")
                else:
                    violations.append(f"$.{key}: unexpected field")

        _check_handle("from_account", payload.get("from_account"), violations)
        _check_handle("to_account", payload.get("to_account"), violations)
        for bank_field in ("from_bank", "to_bank"):
            bank = payload.get(bank_field)
            if isinstance(bank, int):
                bank = str(bank)
            _check_handle(bank_field, bank, violations, shape=_BANK_RE)

        tx_id = payload.get("transaction_id")
        if tx_id is not None:
            # UUIDs can contain 12-digit hex segments — skip the digit-run
            # rule for this format-pinned field (same precedent as
            # CONTENT_EXEMPT_PATHS in the network-boundary guard).
            _check_handle("transaction_id", tx_id, violations,
                          shape=_TX_ID_RE, skip_digit_run=True)

        ts = payload.get("timestamp")
        if ts is not None and (not isinstance(ts, str) or not _TS_SHAPE_RE.match(ts)):
            violations.append("$.timestamp: not a timestamp shape")

        for free_field in ("currency", "payment_format"):
            value = payload.get(free_field)
            if value is None:
                continue
            if not isinstance(value, str) or len(value) > 40:
                violations.append(f"$.{free_field}: invalid value")
                continue
            for rule, pattern in CONTENT_RULES:
                if pattern.search(value):
                    violations.append(f"$.{free_field}: contains {rule}")

        amount = payload.get("amount")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) \
                or not (0 < float(amount) <= 1e12):
            violations.append("$.amount: must be a positive number ≤ 1e12")
    except Exception as exc:  # fail closed, same contract as find_pii
        violations.append(f"$: guard error ({type(exc).__name__}) — failing closed")
    return violations
