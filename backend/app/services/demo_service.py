"""Demo aggregator: combines model metrics + cross-bank results + dataset facts
into a single payload for the frontend dashboard. Phase 7 wires this to the
real ml/reports files; Phase 1 returns safe fallback content.
"""

from __future__ import annotations

from typing import Any

from ..core import config
from . import model_service


def research_summary() -> dict[str, Any]:
    metrics = model_service.load_json_report(config.MODEL_METRICS_PATH) or model_service.fallback_metrics()
    cross_bank = model_service.load_json_report(config.CROSS_BANK_RESULTS_PATH) or fallback_cross_bank()
    return {
        "project": "نسيج | Naseej",
        "dataset": {
            "source": "AMLworld (IBM HI-Small synthetic AML transactions)",
            "split": "HI-Small",
            "raw_file": "ml/data/raw/HI-Small_Trans.csv",
            "note": "Statistics populated by Phase 2 prepare_dataset.py.",
        },
        "model": metrics,
        "cross_bank": cross_bank,
        "privacy": {
            "zero_pii": True,
            "pattern_hash_engine": "stub (Phase 6 will implement zero-PII tested hash)",
        },
        "source": "fallback" if metrics.get("source") == "fallback" else "live",
    }


def fallback_cross_bank() -> dict[str, Any]:
    return {
        "source": "fallback",
        "banks": [],
        "improvement_summary": "Phase 5 has not produced ml/reports/cross_bank_results.json yet.",
    }
