# Explainable AI — the "Why flagged?" engine

**Status: research prototype · synthetic data · PII-safe · NOT a legal/regulatory sufficiency statement**

This document describes the explanation layer added after the ML evaluation
phase. It turns model scores, contextual rule adjustments, and pattern
typologies into analyst-readable explanations for the Investigator Dashboard —
without exposing any raw transaction, account, or customer data.

It does **not** retrain or replace the deployed model, change scoring, or
start GNN/federated work. It reads the existing scoring paths and reports.

---

## 1. What the engine produces

`backend/app/services/explanation_service.py` produces a PII-safe explanation
object for three subjects:

| Subject | Endpoint | Auth | What it explains |
|---|---|---|---|
| transaction | `POST /api/explain/transaction` | node key | A `score-with-context` decision: base-model attribution + context rule layer |
| case | `GET /api/explain/case/{case_id}` | node key (visibility + RBAC) | A registered-pattern case: typology + bucketed evidence |
| model | `GET /api/explain/model` | public | Evaluation-report summary: best/test-leader model, weakest typology, threshold policy, limitations |

The transaction/case payload shape:

```jsonc
{
  "explanation_id": "uuid",
  "subject": "transaction" | "case",
  "model_family": "XGBClassifier" | "pattern_detector" | ...,
  "explanation_method": "shap" | "fallback" | "rule",
  "method_note": "SHAP TreeExplainer attribution (shap 0.51.0).",
  "score": 0.62,
  "risk_tier": "medium",
  "top_factors": [
    {
      "feature_name": "payment_type_enc",
      "direction": "increases_risk" | "decreases_risk",
      "contribution_level": "low" | "medium" | "high",
      "human_label": "Payment type",
      "explanation": "Payment type (known_category) raised the model's risk ...",
      "value_bucket": "known_category"      // never the raw value
    }
  ],
  "contextual_factors": ["5 inbound transfers ... within the last hour", ...],
  "typology_factors": [
    {
      "typology": "rapid_sweep",
      "what_detected": "...", "why_it_matters": "...",
      "evidence_buckets": ["high_sweep_ratio", "short_dwell_time"],
      "risk_tier": "medium", "confidence_bucket": "high",
      "limitations": "Heuristic typology label ... not ground-truth classification."
    }
  ],
  "threshold_rationale": { "policy": "...", "modes": [...], "note": "..." },
  "model_limitations": ["Decision-support only — NOT a legal ... statement", ...],
  "analyst_summary": "Risk assessed medium (score 0.620). Top model drivers: ...",
  "pii_safe": true
}
```

---

## 2. What is SHAP-based vs fallback vs rule-derived vs heuristic

This distinction is surfaced in every payload (`explanation_method` +
`method_note`) and badged in the UI.

- **SHAP-based** (`explanation_method: "shap"`) — when `shap` is installed
  **and** the deployed model is a supported tree model (XGBoost / LightGBM /
  RandomForest), `top_factors` come from `shap.TreeExplainer` on the single
  transaction's feature vector. Direction = sign of the SHAP value;
  contribution_level = that feature's share of total |SHAP|.
- **Fallback** (`explanation_method: "fallback"`) — when SHAP is not installed,
  fails at runtime, or the model is not a supported tree model. `top_factors`
  come from the model's **global feature importance** (`feature_importance.json`)
  intersected with which features carry a non-default signal for this
  transaction, with direction from a small documented rules table. The note
  reads: *"SHAP unavailable; explanation uses deterministic feature/rule
  attribution fallback."* Tests force this path regardless of install state.
- **Rule-derived** (`explanation_method: "rule"`) — the **case** explanation.
  A case links to a registered pattern, not a live model call, so its factors
  come from the pattern's bucketed `velocity_features` / `graph_signature` and
  the typology library. Transaction-level SHAP/feature attribution is still
  available via `/api/explain/transaction` at scoring time.
- **Heuristic** — the **typology** label itself. Typologies come from the
  pattern-library detectors, not a ground-truth classifier. Every
  `typology_factors` entry says so in its `limitations` field.

Current install state is reported live at `GET /api/explain/model`
(`shap_available`). As of this phase SHAP 0.51.0 is installed and TreeExplainer
is compatible with the deployed XGBoost bundle, so the transaction path is
SHAP-based by default; the fallback remains fully implemented and tested.

---

## 3. Why explanations are bucketed (and raw values are not shown)

The whole product posture is zero-PII exchange. An explanation that printed a
raw amount, an account handle, or a transaction id would reintroduce exactly
the data the rest of the system is built to keep inside the bank boundary. So:

- Every factor exposes a coarse `value_bucket` (`micro`/`small`/`medium`/
  `large`/`xlarge` for amounts; `none`/`low`/`moderate`/`high` for counts;
  `cross_bank`/`same_bank`, `off_hours`/`business_hours`, etc.) — never the
  number.
- Account-identity features collapse to `known_account` / `unseen_account`
  (the LabelEncoder's `-1` code), never the encoded integer.
- A final guard (`explanation_service._scrub`) runs the **entire assembled
  payload** through `pii_guard.find_pii` and redacts any string that slips
  through, so `pii_safe: true` is always truthful — defense-in-depth over the
  controlled templates.

Never exposed: raw account ids, transaction ids, IBANs, names, national ids,
phones, emails, or raw payloads. The transaction endpoint additionally runs
the same `find_transaction_pii` guard on its **input** as `score-with-context`.

### Canonical feature contract integration

Explanations resolve through the canonical feature contract
([FEATURE_CONTRACT.md](FEATURE_CONTRACT.md)) when it is present: `human_label`
falls back to the contract's canonical name, `value_bucket` dispatches by the
contract's declared bucket type, and any surfaced feature flagged
`identity_memorization_risk` or `definition_mismatch` adds a contract-sourced
line to `model_limitations` (e.g. account-id factors carry a memorisation
caveat). The integration is decoupled via the JSON loader, so a **missing
contract degrades gracefully** to the built-in labels — the explanation engine
keeps working either way (covered by tests).

---

## 4. Context-score decisions (`/api/explain/transaction`)

The endpoint reuses `score-with-context`, so the explanation matches what the
scoring endpoint returns for the same transaction. It separates two things:

- `top_factors` explain the **base model score** (history features are 0 for a
  single transaction; SHAP/fallback attributes the computable features).
- `contextual_factors` explain the **rule layer** — the velocity/counterparty
  rule hits that produced `contextual_risk_adjustment`.
- `model_limitations` carries the standing honesty line: the model was **not
  retrained** on context features, and **context can escalate but never soften**
  the base score (the rule layer only adds, capped at +0.45; final capped at
  0.99). This mirrors `routes_features.py` and `FEATURE_STORE.md`.

---

## 5. Typology detection (`typology_factors`)

For each detected/inferred typology the engine states: what pattern was
detected, why it matters for AML, the supporting evidence buckets, the risk
tier, a confidence bucket, and the heuristic-label limitation. Covered:
`fan_in`, `fan_out`, `rapid_sweep`, `mule_velocity`, `cross_bank_pass_through`,
`scatter_gather`, `gather_scatter`, `simple_cycle`.

---

## 6. Access control & audit

- `/api/explain/transaction` — node auth; rejects PII in the input (422) and a
  mismatched `source_node_id` (audited 403). Served explanations are audited
  (metadata only: method, factor count, risk tier).
- `/api/explain/case/{id}` — reuses case visibility (`access_control.case_visible`)
  and the registry's `pattern_visible` before enriching with pattern buckets.
  Missing case → 404; visible-but-not → generic audited 403 (the reason is a
  static string, never the case id). Served → audited.
- `/api/explain/model` — public read-only, like `/api/model/metrics`. Degrades
  to `source: "fallback"` with a note when reports are absent.

No payloads or PII ever reach the audit log; denials write a sanitized static
reason, consistent with the rest of the backend.

---

## 7. Limitations before production

- Explanations are **decision-support only**, not a legal or regulatory
  sufficiency statement. A human analyst reviews, decides, and is accountable.
- SHAP attribution is computed on the **single-transaction** vector (history
  features 0), so it explains the served base score, not a full account-history
  model. The account-identity features that surface can reflect memorisation
  (flagged in `MODEL_EVALUATION.md`) and may not generalise.
- Typology labels are heuristic, not ground truth.
- Everything is on synthetic AMLworld data; no claim transfers to real banking
  data without out-of-time validation under SAMA governance.

---

## 8. Reproducing / testing

```bash
python -m pytest backend/tests/test_explain.py -v
```

Covers: safe structure, no account-id/raw-value leakage, SHAP-missing fallback
(forced via monkeypatch regardless of install), context rule factors, case
visibility + RBAC, audited denials, and graceful model-endpoint degradation.
```

---

## 9. Shadow candidate explainability (unchanged endpoints)

The live shadow-scoring endpoint (`POST /api/model/candidate/score-shadow`,
[CANDIDATE_MODEL.md](CANDIDATE_MODEL.md)) returns candidate vs baseline scores
for comparison only; it does **not** alter any `/api/explain/*` behaviour. A
candidate-only explainability *report* already exists
(`candidate_explainability_check.json`, served at
`/api/model/candidate/explainability-check`) with SHAP/fallback factors whose
labels and buckets resolve through the feature contract, bucketed and PII-safe.
Adding a **live** per-feature candidate explanation to the shadow endpoint was
intentionally deferred to keep risk low — it is a documented next step, not part
of this phase.
