"""Backend configuration: paths, CORS, identity.

All paths are resolved relative to the repo root so the app can be launched
from anywhere (the CWD does not have to be `backend/`).
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "naseej-backend"
APP_VERSION = "0.1.0"

# Repo layout: <repo>/backend/app/core/config.py  -> repo root is parents[3]
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

ML_DIR: Path = REPO_ROOT / "ml"
ML_MODELS_DIR: Path = ML_DIR / "models"
ML_REPORTS_DIR: Path = ML_DIR / "reports"
ML_DATA_DIR: Path = ML_DIR / "data"

# Phase 4 will produce this file; until then it may not exist.
BASELINE_MODEL_PATH: Path = ML_MODELS_DIR / "baseline_model.joblib"

# Shadow candidate model bundle (ml/src/train_candidate_model.py output).
# OPTIONAL: absent → shadow scoring returns a safe "unavailable" response.
# This is comparison-only and must NEVER replace BASELINE_MODEL_PATH.
CANDIDATE_MODEL_PATH: Path = ML_MODELS_DIR / "candidate_model.joblib"

# Phase-4/5 report files (Phase 1 returns fallbacks if absent).
MODEL_METRICS_PATH: Path = ML_REPORTS_DIR / "model_metrics.json"
FEATURE_IMPORTANCE_PATH: Path = ML_REPORTS_DIR / "feature_importance.json"
CONFUSION_MATRIX_PATH: Path = ML_REPORTS_DIR / "confusion_matrix.json"
CROSS_BANK_RESULTS_PATH: Path = ML_REPORTS_DIR / "cross_bank_results.json"

# ML evaluation phase reports (ml/src/evaluation_suite.py output; endpoints
# return fallbacks if a report has not been generated yet).
MODEL_COMPARISON_PATH: Path = ML_REPORTS_DIR / "model_comparison.json"
PER_TYPOLOGY_RECALL_PATH: Path = ML_REPORTS_DIR / "per_typology_recall.json"
THRESHOLD_ANALYSIS_PATH: Path = ML_REPORTS_DIR / "threshold_analysis.json"
ABLATION_REPORT_PATH: Path = ML_REPORTS_DIR / "ablation_report.json"

# Offline/online feature reconciliation phase (ml/src/feature_contract.py +
# ml/src/feature_parity_check.py output; endpoints return fallbacks if absent).
FEATURE_CONTRACT_PATH: Path = ML_DIR / "features" / "feature_contract.json"
FEATURE_PARITY_PATH: Path = ML_REPORTS_DIR / "feature_parity_report.json"
TRAINING_FEATURE_MANIFEST_PATH: Path = ML_REPORTS_DIR / "training_feature_manifest.json"

# Shadow candidate model (ml/src/train_candidate_model.py output; NOT deployed).
# Endpoints return fallbacks if a report has not been generated yet.
CANDIDATE_METRICS_PATH: Path = ML_REPORTS_DIR / "candidate_model_metrics.json"
CANDIDATE_COMPARISON_PATH: Path = ML_REPORTS_DIR / "candidate_model_comparison.json"
CANDIDATE_THRESHOLDS_PATH: Path = ML_REPORTS_DIR / "candidate_thresholds.json"
CANDIDATE_EXPLAINABILITY_PATH: Path = ML_REPORTS_DIR / "candidate_explainability_check.json"

# Canonical threat-pattern contract (enforced on every registry write).
THREAT_PATTERN_SCHEMA_PATH: Path = REPO_ROOT / "docs" / "schemas" / "threat_pattern.schema.json"

# Runtime data (audit log, pattern registry) — env-overridable so tests and
# deployments can relocate it. Resolved per call: see audit/registry services.
DEFAULT_DATA_DIR: Path = REPO_ROOT / "backend" / "data"


def audit_log_path() -> Path:
    """JSONL audit log location (env: NASEEJ_AUDIT_LOG)."""
    return Path(os.environ.get("NASEEJ_AUDIT_LOG", DEFAULT_DATA_DIR / "audit" / "audit.jsonl"))


def registry_path() -> Path:
    """JSONL pattern-registry location (env: NASEEJ_REGISTRY_PATH)."""
    return Path(os.environ.get("NASEEJ_REGISTRY_PATH", DEFAULT_DATA_DIR / "patterns.jsonl"))


def cases_path() -> Path:
    """JSONL case-store location (env: NASEEJ_CASES_PATH)."""
    return Path(os.environ.get("NASEEJ_CASES_PATH", DEFAULT_DATA_DIR / "cases.jsonl"))


def shadow_observations_path() -> Path:
    """JSONL shadow-observation store (env: NASEEJ_SHADOW_OBSERVATIONS_PATH).

    Holds only bucketed/aggregate shadow-scoring observations — never raw
    transactions, identifiers, or feature values. Prototype monitoring store.
    """
    return Path(os.environ.get(
        "NASEEJ_SHADOW_OBSERVATIONS_PATH",
        DEFAULT_DATA_DIR / "shadow_observations.jsonl",
    ))


def feedback_labels_path() -> Path:
    """JSONL analyst-feedback / calibration-label store (env:
    NASEEJ_FEEDBACK_LABELS_PATH). Append-only, node-scoped, bucketed — holds
    case outcome labels + bucketed risk tiers only; never raw transactions,
    identifiers, or feature values.
    """
    return Path(os.environ.get(
        "NASEEJ_FEEDBACK_LABELS_PATH",
        DEFAULT_DATA_DIR / "feedback_labels.jsonl",
    ))


# ML evaluation report: candidate calibration readiness (public-safe).
CANDIDATE_CALIBRATION_PATH: Path = ML_REPORTS_DIR / "candidate_calibration_readiness.json"


def feature_snapshot_path() -> Path | None:
    """Optional feature-store event snapshot (env: NASEEJ_FEATURE_SNAPSHOT).

    None (the default) means the feature store is purely in-memory; tests
    set this to get reproducible window state from a JSONL replay.
    """
    raw = os.environ.get("NASEEJ_FEATURE_SNAPSHOT")
    return Path(raw) if raw else None


# CORS — Vite dev server only by default.
CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
