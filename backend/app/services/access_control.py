"""Access partitioning — who may see which patterns and cases.

Pure predicates over an ``AuthContext`` and a stored object; the route layer
calls these and turns False into an audited 403. Fail-closed throughout: an
unknown sharing scope or a malformed object means *not visible*.

Pattern sharing scopes (``governance_tags.sharing_scope``):

  local_only      source node only — registered for the node's own audit
                  trail, never served to anyone else.
  bilateral       source node plus the nodes explicitly listed in
                  ``governance_tags.shared_with_node_ids``. An empty or
                  missing list means nobody else (fail closed), not everybody.
  network_all     every authenticated node whose profile grants
                  ``patterns:view_network``.
  regulator_only  source node plus regulator/admin node types.

Case visibility: a case belongs to the node that opened it
(``owner_node_id``) and is served only to nodes in ``visible_to_node_ids``
(owner plus the pattern's source node, recorded at creation) — unless the
caller holds ``cases:view_all`` (regulator/admin oversight). Mutation is
stricter than visibility: only the owning node may modify a case.
"""

from __future__ import annotations

from typing import Any

from ..core.auth import AuthContext

# Decision id → permission required to take it. The same table gates the
# PATCH /status endpoint via STATUS_TO_DECISION below, so there is no
# unguarded path onto the status machine.
DECISION_PERMISSION: dict[str, str] = {
    "take_under_review": "cases:take_under_review",
    "escalate": "cases:escalate",
    "confirm_fraud": "cases:confirm_fraud",
    "mark_false_positive": "cases:mark_false_positive",
    "close_no_action": "cases:close_no_action",
}


def pattern_visible(ctx: AuthContext, pattern: dict[str, Any]) -> bool:
    """May this caller read this (already schema-validated) pattern?"""
    try:
        source = pattern["source_node_id"]
        if ctx.node_id == source:
            return True
        scope = pattern["governance_tags"]["sharing_scope"]
        if scope == "local_only":
            return False
        if scope == "bilateral":
            recipients = pattern["governance_tags"].get("shared_with_node_ids") or []
            return ctx.node_id in recipients
        if scope == "network_all":
            return ctx.has("patterns:view_network")
        if scope == "regulator_only":
            return ctx.node_type in ("regulator", "admin")
        return False  # unknown scope: fail closed
    except (KeyError, TypeError):
        return False


def case_visible(ctx: AuthContext, case: dict[str, Any]) -> bool:
    """May this caller read this case?"""
    try:
        if ctx.has("cases:view_all"):
            return True
        if ctx.node_id == case["owner_node_id"]:
            return True
        return ctx.node_id in (case.get("visible_to_node_ids") or [])
    except (KeyError, TypeError):
        return False


def case_mutable_by(ctx: AuthContext, case: dict[str, Any]) -> bool:
    """May this caller modify this case at all (before per-action RBAC)?
    Only the owning node works its own cases; visibility grants reading."""
    try:
        return ctx.node_id == case["owner_node_id"]
    except (KeyError, TypeError):
        return False
