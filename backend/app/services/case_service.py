"""Case Management Service — human-in-the-loop AML investigation.

Turns registered threat patterns into analyst-reviewable cases. The system
only *recommends* actions; every state change is an explicit, attributed
analyst decision. Nothing in this service blocks a transaction.

Storage: append-only JSONL of case snapshots (env: NASEEJ_CASES_PATH).
Every mutation appends a full snapshot; on load, the last snapshot per
case_id wins. Like the audit log, nothing is ever rewritten in place, so
the file doubles as a coarse change history.

Privacy: a case carries only what the zero-PII pattern object carried, plus
analyst free text that has already passed the PII guard at the route layer.
No raw transactions, no customer identifiers — cases link to fraud via
pattern_id / pattern_hash only.

Partitioning: every case records ``owner_node_id`` (the node that opened
it) and ``visible_to_node_ids`` (owner + the pattern's source node). The
route layer enforces both via services/access_control.py; the store itself
stays policy-free.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core import config

# ── Status machine ─────────────────────────────────────────────────────────
# Forward-only with one deliberate exception (escalated → under_review,
# de-escalation). Closed states are terminal. A case cannot jump from open
# straight to a fraud verdict: confirmation requires review first — that is
# the human-in-the-loop guarantee, encoded.

TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"under_review", "escalated", "closed_no_action"}),
    "under_review": frozenset({"escalated", "closed_confirmed", "closed_false_positive", "closed_no_action"}),
    "escalated": frozenset({"under_review", "closed_confirmed", "closed_false_positive", "closed_no_action"}),
    "closed_confirmed": frozenset(),
    "closed_false_positive": frozenset(),
    "closed_no_action": frozenset(),
}

# Analyst decisions are semantic shortcuts onto the same status machine.
DECISION_TO_STATUS: dict[str, str] = {
    "take_under_review": "under_review",
    "escalate": "escalated",
    "confirm_fraud": "closed_confirmed",
    "mark_false_positive": "closed_false_positive",
    "close_no_action": "closed_no_action",
}


class InvalidTransitionError(ValueError):
    """Requested status change is not allowed from the current status."""


class CaseNotFoundError(KeyError):
    pass


class DuplicateOpenCaseError(ValueError):
    """An open (non-closed) case already exists for this pattern."""


def recommend_action(risk_score: float, *, is_cross_bank: bool = False) -> str:
    """Policy ladder mapping pattern risk to a recommended (not executed)
    action. Documented in docs/CASE_MANAGEMENT.md — change both together."""
    if risk_score >= 0.9:
        return "freeze_for_review"
    if risk_score >= 0.7:
        return "escalate_to_compliance" if is_cross_bank else "delay_transaction"
    if risk_score >= 0.4:
        return "request_step_up_verification"
    return "monitor"


def _risk_tier(score: float) -> str:
    return "critical" if score >= 0.9 else "high" if score >= 0.7 else "medium" if score >= 0.4 else "low"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _fill_ownership(case: dict[str, Any]) -> dict[str, Any]:
    """In-memory upgrade for snapshots written before access partitioning:
    the creating node was always the pattern's source node back then, so
    ownership defaults to source. Never rewrites the file."""
    if "owner_node_id" not in case:
        case["owner_node_id"] = case.get("source_node_id")
    if not case.get("visible_to_node_ids"):
        case["visible_to_node_ids"] = [n for n in {case["owner_node_id"], case.get("source_node_id")} if n]
    if "sharing_scope" not in case:
        case["sharing_scope"] = "local_only"
    return case


class CaseStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._by_id: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    snapshot = _fill_ownership(json.loads(raw))
                    self._by_id[snapshot["case_id"]] = snapshot
        except FileNotFoundError:
            pass

    def _append_snapshot(self, case: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(case, ensure_ascii=True, sort_keys=True) + "\n")
        self._by_id[case["case_id"]] = case

    # ── creation ───────────────────────────────────────────────────────────

    def create_from_pattern(self, pattern: dict[str, Any], *, owner_node_id: str) -> dict[str, Any]:
        with self._lock:
            for existing in self._by_id.values():
                if (
                    existing["pattern_id"] == pattern["pattern_id"]
                    and not existing["status"].startswith("closed")
                ):
                    raise DuplicateOpenCaseError(pattern["pattern_id"])

            now = _now()
            source = pattern["source_node_id"]
            case = {
                "case_id": str(uuid.uuid4()),
                "pattern_id": pattern["pattern_id"],
                "pattern_hash": pattern["pattern_hash"],
                "typology": pattern["typology"],
                "risk_tier": _risk_tier(pattern["risk_score"]),
                "risk_score": pattern["risk_score"],
                "confidence": pattern["confidence"],
                "source_node_id": source,
                # Ownership & partitioning: the opening node owns the case;
                # the detecting node may follow up on its own detection.
                # Nobody else sees it (regulator oversight comes from the
                # cases:view_all permission, not from this list).
                "owner_node_id": owner_node_id,
                "visible_to_node_ids": sorted({owner_node_id, source}),
                "sharing_scope": pattern.get("governance_tags", {}).get("sharing_scope", "local_only"),
                "status": "open",
                "recommended_action": recommend_action(
                    pattern["risk_score"],
                    is_cross_bank=bool(pattern.get("graph_signature", {}).get("is_cross_bank")),
                ),
                "created_at": now,
                "updated_at": now,
                "assigned_to": None,
                "evidence_summary": pattern["evidence_summary"],
                "analyst_notes": [],
                "decision_history": [],
                "false_positive_flag": False,
                "audit_refs": [],
            }
            self._append_snapshot(case)
        return case

    # ── reads ──────────────────────────────────────────────────────────────

    def get(self, case_id: str) -> dict[str, Any]:
        case = self._by_id.get(case_id)
        if case is None:
            raise CaseNotFoundError(case_id)
        return case

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        items = list(self._by_id.values())
        if status:
            items = [c for c in items if c["status"] == status]
        return sorted(items, key=lambda c: c["created_at"], reverse=True)

    # ── mutations (each appends a new snapshot; history is append-only) ────

    def transition(
        self,
        case_id: str,
        new_status: str,
        *,
        node_id: str,
        reason: str,
        analyst_role: str,
        decision: str | None = None,
        audit_ref: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            case = dict(self.get(case_id))
            previous = case["status"]
            if new_status not in TRANSITIONS.get(previous, frozenset()):
                raise InvalidTransitionError(f"{previous} → {new_status}")

            # Copy-and-append: never mutate stored history lists in place.
            case["decision_history"] = list(case["decision_history"]) + [{
                "timestamp": _now(),
                "node_id": node_id,
                "decision": decision or f"status:{new_status}",
                "reason": reason,
                "previous_status": previous,
                "new_status": new_status,
                "analyst_role": analyst_role,
                "audit_ref": audit_ref,
            }]
            case["status"] = new_status
            case["updated_at"] = _now()
            case["assigned_to"] = case["assigned_to"] or node_id
            if new_status == "closed_false_positive":
                case["false_positive_flag"] = True
            if audit_ref:
                case["audit_refs"] = list(case["audit_refs"]) + [audit_ref]
            self._append_snapshot(case)
        return case

    def add_note(
        self,
        case_id: str,
        note: str,
        *,
        node_id: str,
        analyst_role: str,
        audit_ref: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            case = dict(self.get(case_id))
            case["analyst_notes"] = list(case["analyst_notes"]) + [{
                "timestamp": _now(),
                "node_id": node_id,
                "analyst_role": analyst_role,
                "note": note,
            }]
            case["updated_at"] = _now()
            if audit_ref:
                case["audit_refs"] = list(case["audit_refs"]) + [audit_ref]
            self._append_snapshot(case)
        return case

    def attach_audit_ref(self, case_id: str, audit_ref: str) -> dict[str, Any]:
        with self._lock:
            case = dict(self.get(case_id))
            case["audit_refs"] = list(case["audit_refs"]) + [audit_ref]
            self._append_snapshot(case)
        return case

    def __len__(self) -> int:
        return len(self._by_id)


_instances: dict[str, CaseStore] = {}
_instances_lock = threading.Lock()


def get_case_store() -> CaseStore:
    """Singleton per resolved path (same pattern as the registry): tests
    point NASEEJ_CASES_PATH at a temp file for a fresh, isolated store."""
    path = config.cases_path()
    key = str(path)
    with _instances_lock:
        if key not in _instances:
            _instances[key] = CaseStore(path)
        return _instances[key]
