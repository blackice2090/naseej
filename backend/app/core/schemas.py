"""Pydantic v2 request/response schemas for the Naseej backend.

These mirror the AMLworld / IBM AML synthetic transaction columns where it
makes sense, but stay deliberately small for Phase 1. Phases 3–7 will extend
them with graph-feature fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class TransactionIn(BaseModel):
    timestamp: str | None = Field(None, description="ISO-8601 or AMLworld format")
    from_bank: str | int
    from_account: str
    to_bank: str | int
    to_account: str
    amount: float
    currency: str | None = None
    payment_format: str | None = None


class ScoreOut(BaseModel):
    risk_score: float
    prediction: Literal["benign", "suspicious", "block"]
    reasons: list[str] = []
    pattern_hash: str | None = None
    zero_pii: bool = True
    source: Literal["model", "fallback"] = "fallback"


class PatternIn(BaseModel):
    transactions: list[TransactionIn]


# ── Case management (human-in-the-loop investigation) ─────────────────────

CaseStatus = Literal[
    "open",
    "under_review",
    "escalated",
    "closed_confirmed",
    "closed_false_positive",
    "closed_no_action",
]

RecommendedAction = Literal[
    "monitor",
    "request_step_up_verification",
    "delay_transaction",
    "freeze_for_review",
    "escalate_to_compliance",
]

# Pseudonymous role labels only — analyst identity stays inside the bank's
# own IAM; Naseej cases never carry personal identifiers. The acting role is
# NOT part of any request body: it comes from the AuthContext (node profile
# default, or X-Analyst-Role validated against the node's allowed_roles).
# A body-supplied "analyst_role" is ignored by construction.
AnalystRole = Literal["analyst", "senior_analyst", "mlro", "regulator", "admin"]

AnalystDecision = Literal[
    "take_under_review",
    "escalate",
    "confirm_fraud",
    "mark_false_positive",
    "close_no_action",
]


class CaseStatusPatchIn(BaseModel):
    new_status: CaseStatus
    reason: str = Field(..., min_length=3, max_length=500)


class CaseNoteIn(BaseModel):
    note: str = Field(..., min_length=3, max_length=2000)


class CaseDecisionIn(BaseModel):
    decision: AnalystDecision
    reason: str = Field(..., min_length=3, max_length=500)


# ── Feature store (node-local velocity / context features) ────────────────
# Closed schemas (extra="forbid"): an unknown field is rejected before the
# PII guard even runs — same layered gating as the pattern registry.


class FeatureTransactionIn(BaseModel):
    """A synthetic/pseudonymous transaction for feature-store ingestion.

    No PII fields exist in this schema; handle *values* are additionally
    checked by pii_guard.find_transaction_pii (IBAN/phone/name shapes etc.).
    """

    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., min_length=1, max_length=64)
    timestamp: str = Field(..., min_length=8, max_length=40)
    source_node_id: str = Field(..., min_length=4, max_length=32)
    from_bank: str | int
    from_account: str = Field(..., min_length=2, max_length=64)
    to_bank: str | int
    to_account: str = Field(..., min_length=2, max_length=64)
    amount: float = Field(..., gt=0)
    currency: str | None = Field(None, max_length=40)
    payment_format: str | None = Field(None, max_length=40)


class ContextScoreIn(BaseModel):
    """score-with-context input: the transaction to score now, against the
    calling node's local window state. transaction_id is optional because
    the transaction may not have been ingested yet."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: str | None = Field(None, min_length=1, max_length=64)
    timestamp: str | None = Field(None, min_length=8, max_length=40)
    source_node_id: str | None = Field(None, min_length=4, max_length=32)
    from_bank: str | int
    from_account: str = Field(..., min_length=2, max_length=64)
    to_bank: str | int
    to_account: str = Field(..., min_length=2, max_length=64)
    amount: float = Field(..., gt=0)
    currency: str | None = Field(None, max_length=40)
    payment_format: str | None = Field(None, max_length=40)


class ShadowScoreIn(ContextScoreIn):
    """score-shadow input: a pseudonymous transaction plus an OPTIONAL
    ``pattern_id`` so the resulting shadow observation can later be linked to a
    case opened from the same pattern (analyst feedback loop). The feature-store
    schema (ContextScoreIn) stays unchanged; this only adds the optional link.
    """

    model_config = ConfigDict(extra="forbid")

    pattern_id: str | None = Field(None, min_length=1, max_length=64)


class FeatureIngestOut(BaseModel):
    accepted: bool = True
    transaction_id: str
    events_in_window: int
    accounts_tracked: int
    zero_pii: bool = True


class AccountFeaturesOut(BaseModel):
    account_id: str
    features: dict[str, Any]
    node_scoped: bool = True
    zero_pii: bool = True


class ContextScoreOut(BaseModel):
    """Contextual score = baseline model + deterministic rule layer.

    Honesty contract: ``model_retrained_on_context`` is always False until a
    real retraining produces a bundle that consumes these features — the
    adjustment is a transparent rule layer, not a new model.
    """

    base_model_score: float
    contextual_risk_adjustment: float
    final_contextual_score: float
    prediction: Literal["benign", "suspicious", "block"]
    explanation: list[str] = []
    context_features: dict[str, Any] = {}
    model_retrained_on_context: Literal[False] = False
    base_score_source: Literal["model", "fallback"] = "fallback"
    pattern_hash: str | None = None
    zero_pii: bool = True


class PatternOut(BaseModel):
    detected_patterns: list[dict[str, Any]] = []
    graph_summary: dict[str, Any] = {}
    risk_score: float = 0.0
    pattern_hash: str | None = None
    recommended_action: Literal["allow", "review", "block"] = "review"
    zero_pii: bool = True
    source: Literal["engine", "fallback"] = "fallback"
