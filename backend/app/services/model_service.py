"""Lazy model loader.

The joblib bundle written by ``ml.src.train_baseline`` contains:
    {"model": estimator, "feature_columns": list[str],
     "threshold": float, "model_name": str}

``get_bundle()`` loads and caches the full dict.  ``get_model()``,
``get_feature_columns()``, and ``get_threshold()`` are convenience wrappers
used by the scoring service (Phase 7).  All callers must handle None / missing
keys and fall back gracefully.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..core import config

logger = logging.getLogger(__name__)

_BUNDLE: dict[str, Any] | None = None
_LOAD_ATTEMPTED: bool = False


def get_bundle() -> dict[str, Any] | None:
    """Load the full model bundle lazily. Returns None if the artefact is absent."""
    global _BUNDLE, _LOAD_ATTEMPTED
    if _LOAD_ATTEMPTED:
        return _BUNDLE
    _LOAD_ATTEMPTED = True
    path = config.BASELINE_MODEL_PATH
    if not path.exists():
        logger.warning("Baseline model not found at %s — running in fallback mode.", path)
        return None
    try:
        import joblib

        raw = joblib.load(path)
        if isinstance(raw, dict) and "model" in raw:
            _BUNDLE = raw
            logger.info(
                "Loaded model bundle from %s (model=%s, features=%d, threshold=%.4f)",
                path,
                raw.get("model_name", "?"),
                len(raw.get("feature_columns", [])),
                raw.get("threshold", float("nan")),
            )
        else:
            # Legacy format: joblib file IS the estimator directly.
            _BUNDLE = {"model": raw, "feature_columns": [], "threshold": 0.5, "model_name": "legacy"}
            logger.info("Loaded legacy model (no bundle dict) from %s", path)
    except Exception as exc:  # pragma: no cover - degraded mode
        logger.exception("Failed to load baseline model: %s", exc)
        _BUNDLE = None
    return _BUNDLE


def get_model() -> Any | None:
    """Return the trained estimator, or None if unavailable."""
    bundle = get_bundle()
    return bundle["model"] if bundle else None


def get_feature_columns() -> list[str] | None:
    """Return the ordered feature column list stored in the bundle."""
    bundle = get_bundle()
    if bundle is None:
        return None
    cols = bundle.get("feature_columns", [])
    return cols if cols else None


def get_threshold() -> float | None:
    """Return the decision threshold stored in the bundle."""
    bundle = get_bundle()
    return float(bundle["threshold"]) if bundle and "threshold" in bundle else None


def load_json_report(path) -> dict | None:
    """Read a JSON report file. Returns None if missing or unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed reading %s: %s", path, exc)
        return None


def fallback_metrics() -> dict:
    """Safe-default metrics shown when no report has been generated yet."""
    return {
        "source": "fallback",
        "model_type": "xgboost-baseline",
        "threshold": None,
        "pr_auc": None,
        "roc_auc": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "confusion_matrix": None,
        "prevalence": None,
        "note": "Phase 4 has not produced ml/reports/model_metrics.json yet.",
    }


def fallback_feature_importance() -> dict:
    return {
        "source": "fallback",
        "features": [],
        "note": "Phase 4 has not produced ml/reports/feature_importance.json yet.",
    }


def fallback_evaluation_report(report_name: str) -> dict:
    """Safe default for the ML evaluation reports (comparison, per-typology
    recall, threshold analysis, ablation) when the suite has not run yet."""
    return {
        "source": "fallback",
        "report": report_name,
        "note": (
            f"ml/reports/{report_name}.json has not been generated yet — "
            "run `python -m ml.src.evaluation_suite` to produce it."
        ),
    }


def fallback_feature_artifact(artifact: str, how_to: str) -> dict:
    """Safe default for the feature-reconciliation artifacts (contract, parity,
    training manifest) when they have not been generated yet."""
    return {
        "source": "fallback",
        "report": artifact,
        "note": f"{artifact} has not been generated yet — run `{how_to}` to produce it.",
    }
