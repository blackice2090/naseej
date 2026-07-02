"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from ..core import config
from ..core.schemas import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut, tags=["health"])
def health() -> HealthOut:
    return HealthOut(status="ok", service=config.APP_NAME, version=config.APP_VERSION)
