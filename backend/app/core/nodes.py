"""Node identity registry — who each network node is and what it may do.

Authentication (the API key → node id mapping) lives in ``auth.py``; this
module answers the next question: given an authenticated node id, what is
its node type, which analyst roles may it act under, and which capabilities
does its deployment have?

Profiles resolve in three layers, most specific wins per node:

  1. ``NASEEJ_NODE_PROFILES`` env var — a JSON object mapping node id to a
     partial profile override, e.g.::

         NASEEJ_NODE_PROFILES='{"NODE_X1Y2Z3A4": {"node_type": "regulator",
             "allowed_roles": ["regulator"], "default_role": "regulator",
             "can_view_all_cases": true, "can_publish_patterns": false}}'

  2. Built-in DEV profiles for the three local-simulation nodes (Bank A as
     analyst, Bank B as MLRO, one read-only regulator).
  3. A conservative default bank profile for any other authenticated node:
     analyst role only, no view-all, no fraud confirmation.

Role model: a node declares its ``allowed_roles`` envelope at onboarding;
each request acts under the node's ``default_role`` unless the caller
selects another role from that envelope via the ``X-Analyst-Role`` header
(validated server-side — see ``auth.require_context``). Request *bodies*
are never consulted for roles. This is single-credential-per-node prototype
auth: real deployments would mint per-analyst credentials from the bank's
own IAM and carry the role as a verified claim.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, fields, replace

logger = logging.getLogger(__name__)

PROFILES_ENV_VAR = "NASEEJ_NODE_PROFILES"

NODE_TYPES = ("bank", "regulator", "admin")
ROLES = ("analyst", "senior_analyst", "mlro", "regulator", "admin")


@dataclass(frozen=True)
class NodeProfile:
    node_id: str
    display_name: str
    node_type: str  # bank | regulator | admin
    allowed_roles: tuple[str, ...]
    default_role: str
    can_publish_patterns: bool
    can_create_cases: bool
    can_view_network_patterns: bool
    can_view_all_cases: bool
    can_confirm_fraud: bool
    can_escalate_to_compliance: bool


# Role → case-decision grants. Roles are cumulative up the seniority ladder;
# regulator and admin grant no case mutations at all (read-only oversight /
# maintenance respectively).
_ANALYST_GRANTS = frozenset({
    "cases:note", "cases:take_under_review", "cases:close_no_action",
})
_SENIOR_GRANTS = _ANALYST_GRANTS | {"cases:escalate", "cases:mark_false_positive"}
_MLRO_GRANTS = _SENIOR_GRANTS | {"cases:confirm_fraud"}

ROLE_GRANTS: dict[str, frozenset[str]] = {
    "analyst": _ANALYST_GRANTS,
    "senior_analyst": _SENIOR_GRANTS,
    "mlro": _MLRO_GRANTS,
    "regulator": frozenset(),
    "admin": frozenset(),
}


def permissions_for(profile: NodeProfile, role: str) -> frozenset[str]:
    """Effective permissions = node capabilities ∩ role grants.

    Node flags answer "may this deployment ever do X"; the role answers
    "may this actor do X now". Both must agree for the sensitive grants.
    """
    perms: set[str] = set()
    if profile.can_publish_patterns:
        perms.add("patterns:publish")
    if profile.can_view_network_patterns:
        perms.add("patterns:view_network")
    if profile.can_create_cases:
        perms.add("cases:create")
    if profile.can_view_all_cases:
        perms.add("cases:view_all")
    for grant in ROLE_GRANTS.get(role, frozenset()):
        if grant == "cases:confirm_fraud" and not profile.can_confirm_fraud:
            continue
        if grant == "cases:escalate" and not profile.can_escalate_to_compliance:
            continue
        perms.add(grant)
    return frozenset(perms)


# Local-simulation profiles. Bank A defaults to the junior role so the demo
# UI shows the governance ladder (analyst review, MLRO confirms); Bank B is
# the MLRO counterpart; the regulator node is read-only oversight.
_BANK_ROLES = ("analyst", "senior_analyst", "mlro")

DEV_PROFILES: dict[str, NodeProfile] = {
    "NODE_A7C2F9E1": NodeProfile(
        node_id="NODE_A7C2F9E1", display_name="Bank A", node_type="bank",
        allowed_roles=_BANK_ROLES, default_role="analyst",
        can_publish_patterns=True, can_create_cases=True,
        can_view_network_patterns=True, can_view_all_cases=False,
        can_confirm_fraud=True, can_escalate_to_compliance=True,
    ),
    "NODE_B3D8E2F4": NodeProfile(
        node_id="NODE_B3D8E2F4", display_name="Bank B", node_type="bank",
        allowed_roles=_BANK_ROLES, default_role="mlro",
        can_publish_patterns=True, can_create_cases=True,
        can_view_network_patterns=True, can_view_all_cases=False,
        can_confirm_fraud=True, can_escalate_to_compliance=True,
    ),
    "NODE_REG5C7A1": NodeProfile(
        node_id="NODE_REG5C7A1", display_name="Network Regulator", node_type="regulator",
        allowed_roles=("regulator",), default_role="regulator",
        can_publish_patterns=False, can_create_cases=False,
        can_view_network_patterns=True, can_view_all_cases=True,
        can_confirm_fraud=False, can_escalate_to_compliance=False,
    ),
}


def _default_bank_profile(node_id: str) -> NodeProfile:
    """Conservative profile for env-keyed nodes with no explicit profile:
    a bank that can work its own detections but holds no elevated rights."""
    return NodeProfile(
        node_id=node_id, display_name=node_id, node_type="bank",
        allowed_roles=("analyst",), default_role="analyst",
        can_publish_patterns=True, can_create_cases=True,
        can_view_network_patterns=True, can_view_all_cases=False,
        can_confirm_fraud=False, can_escalate_to_compliance=False,
    )


_OVERRIDABLE = {f.name for f in fields(NodeProfile)} - {"node_id"}
_BOOL_FIELDS = {f.name for f in fields(NodeProfile) if f.type == "bool"}


def _apply_override(base: NodeProfile, raw: dict) -> NodeProfile:
    """Merge a validated env override onto a base profile. Invalid values
    are skipped with a warning — config mistakes must not widen access."""
    changes: dict = {}
    for key, value in raw.items():
        if key not in _OVERRIDABLE:
            logger.warning("nodes: ignoring unknown profile field %r for %s", key, base.node_id)
            continue
        if key == "node_type" and value not in NODE_TYPES:
            logger.warning("nodes: ignoring invalid node_type for %s", base.node_id)
            continue
        if key == "allowed_roles":
            roles = tuple(r for r in value if r in ROLES) if isinstance(value, list) else ()
            if not roles:
                logger.warning("nodes: ignoring invalid allowed_roles for %s", base.node_id)
                continue
            value = roles
        if key == "default_role" and value not in ROLES:
            logger.warning("nodes: ignoring invalid default_role for %s", base.node_id)
            continue
        if key in _BOOL_FIELDS:
            value = bool(value)
        changes[key] = value
    merged = replace(base, **changes)
    if merged.default_role not in merged.allowed_roles:
        logger.warning(
            "nodes: default_role not in allowed_roles for %s — using first allowed role",
            base.node_id,
        )
        merged = replace(merged, default_role=merged.allowed_roles[0])
    return merged


def _env_overrides() -> dict[str, dict]:
    raw = os.environ.get(PROFILES_ENV_VAR)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("top-level JSON must be an object")
        return {k: v for k, v in parsed.items() if isinstance(v, dict)}
    except (ValueError, json.JSONDecodeError):
        logger.warning("nodes: malformed %s — ignoring overrides", PROFILES_ENV_VAR)
        return {}


def get_profile(node_id: str) -> NodeProfile:
    """Resolve the profile for an authenticated node id (env per call, like
    auth.active_keys — simple at demo scale)."""
    base = DEV_PROFILES.get(node_id) or _default_bank_profile(node_id)
    override = _env_overrides().get(node_id)
    return _apply_override(base, override) if override else base
