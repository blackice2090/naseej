"""Naseej backend — FastAPI entrypoint.

Run from the repo root:
    uvicorn backend.app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    routes_auth,
    routes_cases,
    routes_demo,
    routes_explain,
    routes_features,
    routes_feedback,
    routes_graph,
    routes_health,
    routes_model,
    routes_patterns,
)
from .core import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Naseej Backend",
    version=config.APP_VERSION,
    description=(
        "Research prototype API for نسيج | Naseej — a privacy-preserving "
        "cross-bank AML intelligence network. Phase 1 scaffolding."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_auth.router)
app.include_router(routes_model.router)
app.include_router(routes_graph.router)
app.include_router(routes_demo.router)
app.include_router(routes_patterns.router)
app.include_router(routes_cases.router)
app.include_router(routes_features.router)
app.include_router(routes_explain.router)
app.include_router(routes_feedback.router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "service": config.APP_NAME,
        "version": config.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
