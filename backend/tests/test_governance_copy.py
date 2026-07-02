"""
Governance copy guard: ensures judge-facing UI copy and docs do not contain
autonomous-blocking language that conflicts with Naseej's human-in-the-loop
positioning (recommendations only, no autonomous blocking).
"""
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]

# Files that judges and analysts read directly.
JUDGE_FACING_FILES = [
    ROOT / "naseej-ai/src/config/copy.js",
    ROOT / "docs/DEMO_SCRIPT.md",
    ROOT / "docs/JUDGE_EVIDENCE_PACK.md",
    ROOT / "README.md",
]

# Autonomous-blocking phrases forbidden in judge-facing copy (case-insensitive).
# Production-readiness / certification overclaims are tested separately by the
# backend governance-evidence API tests (test_demo_evidence.py).
FORBIDDEN_PHRASES = [
    "autonomous blocking",
    "transaction blocked by naseej",
    "prevention active",
    "system stopped transaction",
    "ai blocked transaction",
    "automatic freeze",
    "blocked automatically",
    "autonomous block",
    "system blocked",
    "ai blocked",
    "cross-bank prevention active",
]

# Pattern that flags a forbidden phrase UNLESS it is immediately preceded by a
# negation word (e.g. "no autonomous blocking", "not production-ready").
_NEG = r"(?:no |not |never |non-|without )"
_NEGATED = re.compile(rf"{_NEG}", re.IGNORECASE)


def _preceding_context(text: str, match_start: int, window: int = 40) -> str:
    return text[max(0, match_start - window):match_start]


class TestGovernanceCopy:
    def test_no_autonomous_blocking_language(self):
        violations = []
        for path in JUDGE_FACING_FILES:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for phrase in FORBIDDEN_PHRASES:
                for m in re.finditer(re.escape(phrase), text, re.IGNORECASE):
                    ctx = _preceding_context(text, m.start())
                    if _NEGATED.search(ctx):
                        continue  # negated — allowed
                    line_no = text[: m.start()].count("\n") + 1
                    violations.append(
                        f"{path.name}:{line_no} — forbidden phrase '{phrase}'"
                    )
        assert not violations, (
            "Judge-facing copy contains autonomous-blocking language:\n"
            + "\n".join(violations)
        )

    def test_stage_flagged_label_present(self):
        """STAGE_LABELS[BLOCKED] must use flagged/escalated wording, not 'stopped'."""
        copy_js = ROOT / "naseej-ai/src/config/copy.js"
        if not copy_js.exists():
            return
        text = copy_js.read_text(encoding="utf-8")
        assert "stopped at Bank B" not in text, (
            "copy.js still contains 'stopped at Bank B' — use 'escalated'"
        )
        assert "FLAGGED" in text or "flagged" in text, (
            "copy.js must contain flagged/FLAGGED wording in STAGE_LABELS"
        )

    def test_intel_feed_no_prevention_active(self):
        """INTEL_FEED must not say 'prevention active'."""
        copy_js = ROOT / "naseej-ai/src/config/copy.js"
        if not copy_js.exists():
            return
        text = copy_js.read_text(encoding="utf-8")
        assert "prevention active" not in text.lower(), (
            "copy.js INTEL_FEED still contains 'prevention active'"
        )

    def test_demo_script_no_blocks_verb(self):
        """DEMO_SCRIPT must not say 'It blocks a' (autonomous action)."""
        demo = ROOT / "docs/DEMO_SCRIPT.md"
        if not demo.exists():
            return
        text = demo.read_text(encoding="utf-8")
        assert "it blocks a" not in text.lower(), (
            "DEMO_SCRIPT.md still contains 'It blocks a' — use 'It flags'"
        )
