"""Identity endpoint — lets a client mirror its backend-resolved capabilities.

The frontend never decides security: it calls this endpoint and disables UI
actions the backend would reject anyway. The backend remains authoritative;
a tampered client still hits the 403s in the case/pattern routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.auth import AuthContext, require_context

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/whoami")
def whoami(ctx: AuthContext = Depends(require_context)) -> dict:
    return {
        "node_id": ctx.node_id,
        "display_name": ctx.display_name,
        "node_type": ctx.node_type,
        "role": ctx.role,
        "permissions": sorted(ctx.permissions),
    }
