"""Generate the candidate shadow-scoring readiness report.

Assesses whether the shadow candidate can be scored online (artifacts present,
approved features producible, endpoint wired) without deploying anything. The
readiness logic lives in the backend serving layer
(``backend.app.services.candidate_service.shadow_readiness``); this script
renders it to ml/reports for review and the docs.

CLI:
    python -m ml.src.candidate_shadow_readiness
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORTS_DIR = REPO_ROOT / "ml" / "reports"


def _markdown(r: dict[str, Any]) -> str:
    lines = ["# Candidate Shadow-Scoring Readiness (SHADOW ONLY)", ""]
    lines.append(f"- Generated: {r['generated_at']}  ·  Deployed: **{r['deployed']}**  ·  "
                 f"Deployment recommended: **{r['deployment_recommended']}**")
    lines.append("")
    lines.append("## Artifact availability")
    lines.append("")
    lines.append("| Artifact | Present |")
    lines.append("|---|---|")
    for k, v in r["artifact_availability"].items():
        lines.append(f"| `{k}` | {'✅' if v else '❌'} |")
    lines.append("")
    fa = r["feature_availability"]
    lines.append("## Feature availability")
    lines.append("")
    lines.append(f"- Approved feature count: **{fa['approved_feature_count']}**")
    lines.append(f"- Intrinsic (from payload): {', '.join('`'+f+'`' for f in fa['intrinsic_from_payload'])}")
    lines.append(f"- Windowed (from online store): {', '.join('`'+f+'`' for f in fa['windowed_from_online_store'])}")
    lines.append(f"- Missing-feature behaviour: {fa['missing_feature_behaviour']}")
    lines.append(f"- Excluded (confirmed never used): {', '.join('`'+f+'`' for f in fa['excluded_confirmed'])}")
    lines.append("")
    ep = r["endpoint"]
    lines.append("## Endpoint")
    lines.append("")
    lines.append(f"- `{ep['path']}`")
    lines.append(f"- Auth: {ep['auth']}")
    lines.append(f"- PII guard: {ep['pii_guard']}")
    lines.append(f"- Audited: {ep['audited']}  ·  Creates cases: {ep['creates_cases']}  ·  "
                 f"Affects deployed scoring: {ep['affects_deployed_scoring']}")
    lines.append("")
    lines.append("## Known limitations")
    for lim in r["known_limitations"]:
        lines.append(f"- {lim}")
    lines.append("")
    lines.append(f"## Why not deployed\n\n{r['why_not_deployed']}")
    lines.append("")
    lines.append("## Needed before deployment")
    for item in r["needed_before_deployment"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("> SHADOW ONLY — comparison/monitoring artefact. The deployed model, "
                 "scoring endpoint, and explainability endpoints are unchanged.")
    return "\n".join(lines) + "\n"


def run(reports_dir: Path = DEFAULT_REPORTS_DIR) -> dict[str, Any]:
    from backend.app.services import candidate_service

    candidate_service.reset_candidate_cache()
    readiness = candidate_service.shadow_readiness()
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "candidate_shadow_readiness.json").write_text(
        json.dumps(readiness, indent=2), encoding="utf-8")
    (reports_dir / "candidate_shadow_readiness.md").write_text(_markdown(readiness), encoding="utf-8")
    return readiness


def main() -> int:  # pragma: no cover
    r = run()
    print(json.dumps(r["artifact_availability"], indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
