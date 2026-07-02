"""Bank-node API key authentication.

Every protected endpoint requires an ``X-API-Key`` header that maps to a
registered node id. Keys come from the ``NASEEJ_NODE_KEYS`` environment
variable in the form::

    NASEEJ_NODE_KEYS="NODE_A7C2F9E1:secret-key-a,NODE_B3D8E2F4:secret-key-b"

Node ids must match the network format ``NODE_<8 uppercase alphanumerics>``
(the same format the threat-pattern schema pins for ``source_node_id``).

When the variable is unset, three clearly-labelled DEV keys are active so
the local browser demo works out of the box (Bank A, Bank B, and a
read-only regulator node — see ``nodes.py`` for their profiles). Setting ``NASEEJ_NODE_KEYS``
disables the dev keys entirely — there is no fallback merge, so a real
deployment cannot accidentally accept a dev key.

This is single-factor shared-secret auth: a deliberate first step, not the
target state. The blueprint's API Gateway (mTLS per node, rotation, rate
limiting) replaces it post-MVP.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
from dataclasses import dataclass

from fastapi import Header, HTTPException

from .nodes import get_profile, permissions_for

logger = logging.getLogger(__name__)

ENV_VAR = "NASEEJ_NODE_KEYS"

NODE_ID_RE = re.compile(r"^NODE_[A-Z0-9]{8}$")

# Local-simulation keys, active ONLY when NASEEJ_NODE_KEYS is unset.
# These are not secrets — they exist so `npm run dev` + `uvicorn` work
# with zero setup. Never use them outside a local demo.
DEV_NODE_KEYS: dict[str, str] = {
    "dev-key-bank-a-local-only": "NODE_A7C2F9E1",
    "dev-key-bank-b-local-only": "NODE_B3D8E2F4",
    "dev-key-regulator-local-only": "NODE_REG5C7A1",
}

_warned_dev_keys = False


def _parse_env_keys(raw: str) -> dict[str, str]:
    """Parse ``NODE_ID:key`` pairs into a key→node_id map, skipping bad entries."""
    table: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        node_id, sep, key = pair.partition(":")
        node_id, key = node_id.strip(), key.strip()
        if not sep or not key or not NODE_ID_RE.match(node_id):
            logger.warning("auth: ignoring malformed %s entry for %r", ENV_VAR, node_id or pair[:20])
            continue
        table[key] = node_id
    return table


def active_keys() -> dict[str, str]:
    """Return the key→node_id table, resolved from the environment per call.

    Per-call resolution keeps tests and key rotation simple at demo scale;
    a production gateway would cache with invalidation.
    """
    global _warned_dev_keys
    raw = os.environ.get(ENV_VAR)
    if raw is not None:
        return _parse_env_keys(raw)
    if not _warned_dev_keys:
        logger.warning(
            "auth: %s not set — DEV node keys active. Local simulation only.", ENV_VAR
        )
        _warned_dev_keys = True
    return DEV_NODE_KEYS


@dataclass(frozen=True)
class AuthContext:
    """Resolved identity of the calling request: who (node), in what
    capacity (node type + role), with what rights (permissions).

    The role is NEVER taken from a request body. It is the node profile's
    default role, optionally replaced via the ``X-Analyst-Role`` header but
    only with a role inside the node's server-configured ``allowed_roles``
    envelope — a caller cannot claim a role its node was not granted.
    """

    node_id: str
    display_name: str
    node_type: str
    role: str
    permissions: frozenset[str]

    def has(self, permission: str) -> bool:
        return permission in self.permissions


def _authenticate(x_api_key: str | None) -> str:
    """Resolve an API key to a node id; 401 otherwise. Constant-time
    comparison avoids leaking key prefixes through timing."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    for key, node_id in active_keys().items():
        if secrets.compare_digest(x_api_key, key):
            return node_id
    raise HTTPException(status_code=401, detail="Unknown API key.")


def require_context(
    x_api_key: str | None = Header(default=None),
    x_analyst_role: str | None = Header(default=None),
) -> AuthContext:
    """FastAPI dependency: authenticate the node and resolve its AuthContext."""
    node_id = _authenticate(x_api_key)
    profile = get_profile(node_id)

    role = profile.default_role
    if x_analyst_role:
        requested = x_analyst_role.strip().lower()
        if requested not in profile.allowed_roles:
            # Audit the denial without echoing the header value — an
            # arbitrary header string must never reach the audit log.
            from ..services import audit_service  # local import: no core→services cycle at module load

            audit_service.record(
                node_id=node_id, endpoint="(auth)", action="role_select",
                decision="denied", reason="requested role not in node's allowed_roles",
            )
            raise HTTPException(
                status_code=403,
                detail="Requested analyst role is not permitted for this node.",
            )
        role = requested

    return AuthContext(
        node_id=node_id,
        display_name=profile.display_name,
        node_type=profile.node_type,
        role=role,
        permissions=permissions_for(profile, role),
    )


def require_node(x_api_key: str | None = Header(default=None)) -> str:
    """Backward-compatible dependency for routes that only need the node id."""
    return _authenticate(x_api_key)
