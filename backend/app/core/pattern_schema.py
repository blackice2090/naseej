"""Threat-pattern JSON Schema gate.

Validates incoming threat pattern objects against the canonical contract at
``docs/schemas/threat_pattern.schema.json`` (Draft 2020-12). The schema sets
``additionalProperties: false`` at every level, so any extra field — including
any PII-bearing field — fails validation before the object is processed.

Error messages are sanitized: they name the failing path and rule, never the
offending value, so a rejected payload cannot leak PII into responses or
audit logs.
"""

from __future__ import annotations

import json
from functools import lru_cache

from jsonschema import Draft202012Validator

from . import config


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(config.THREAT_PATTERN_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    # FORMAT_CHECKER enforces "format": "uuid" etc. (off by default in jsonschema).
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def validate_pattern(obj: object) -> list[str]:
    """Return a list of sanitized violation messages; empty when valid."""
    if not isinstance(obj, dict):
        return ["payload: must be a JSON object"]
    errors = sorted(_validator().iter_errors(obj), key=lambda e: list(e.absolute_path))
    messages: list[str] = []
    for err in errors:
        path = "$." + ".".join(str(p) for p in err.absolute_path) if err.absolute_path else "$"
        if err.validator == "additionalProperties":
            # Name the unexpected keys — keys are structural, values are not echoed.
            unexpected = sorted(set(err.instance) - set(err.schema.get("properties", {})))
            messages.append(f"{path}: unexpected field(s) {unexpected} — schema is closed")
        elif err.validator == "required":
            messages.append(f"{path}: {err.message}")  # names missing keys only
        else:
            messages.append(f"{path}: violates '{err.validator}' constraint")
    return messages
