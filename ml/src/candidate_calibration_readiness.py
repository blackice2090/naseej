"""Generate the candidate calibration-readiness report.

A static, honest statement that the shadow candidate is NOT calibrated for
production: live shadow mode has no real labels, so probabilities cannot be
calibrated and no deployment can be recommended. Lists exactly what is needed
before calibration could even begin.

CLI:
    python -m ml.src.candidate_calibration_readiness
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORTS_DIR = REPO_ROOT / "ml" / "reports"


def build() -> dict[str, Any]:
    return {
        "source": "live",
        "report": "candidate_calibration_readiness",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "shadow_only": True,
        "deployed": False,
        "calibrated_for_production": False,
        "deployment_recommended": False,
        "real_labels_available_in_shadow_mode": False,
        "statement": (
            "The shadow candidate is NOT calibrated for production. Live shadow scoring produces no "
            "ground-truth labels, so candidate probabilities cannot be calibrated and no threshold can "
            "be validated against real outcomes. Shadow monitoring is comparison/observation only."
        ),
        "needed_for_calibration": [
            "Labeled outcomes (confirmed fraud / confirmed legitimate) for shadow-scored transactions.",
            "Out-of-time validation on real (non-synthetic) supervised data under SAMA governance.",
            "Threshold tuning against those labels (precision/recall operating points re-derived on real data).",
            "An analyst feedback loop feeding confirmed dispositions back into evaluation.",
            "Drift monitoring on real distributions (the prototype drift signal is not sufficient).",
            "A SAMA-governed pilot validation with a documented rollback + human-in-the-loop plan.",
        ],
        "drift_status": (
            "Only a PROTOTYPE drift signal exists, computed from bucketed synthetic shadow observations. "
            "It is a coarse early-warning aid, not statistical production monitoring."
        ),
        "note": "Synthetic AMLworld benchmark; comparison-only. The deployed model is unchanged.",
        "pii_safe": True,
    }


def _markdown(r: dict[str, Any]) -> str:
    lines = ["# Candidate Calibration Readiness (SHADOW ONLY)", ""]
    lines.append(f"- Generated: {r['generated_at']}  ·  Calibrated for production: **{r['calibrated_for_production']}**  ·  "
                 f"Deployment recommended: **{r['deployment_recommended']}**")
    lines.append("")
    lines.append(r["statement"])
    lines.append("")
    lines.append("## Needed for calibration")
    for item in r["needed_for_calibration"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Drift status\n\n{r['drift_status']}")
    lines.append("")
    lines.append("> SHADOW ONLY — no real labels in live shadow mode, no deployment recommendation. "
                 "The deployed model, scoring endpoint, and explainability endpoints are unchanged.")
    return "\n".join(lines) + "\n"


def run(reports_dir: Path = DEFAULT_REPORTS_DIR) -> dict[str, Any]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    r = build()
    (reports_dir / "candidate_calibration_readiness.json").write_text(
        json.dumps(r, indent=2), encoding="utf-8")
    (reports_dir / "candidate_calibration_readiness.md").write_text(_markdown(r), encoding="utf-8")
    return r


def main() -> int:  # pragma: no cover
    r = run()
    print(json.dumps({k: r[k] for k in ("calibrated_for_production", "deployment_recommended")}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
