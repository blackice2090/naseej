# نسيج | Naseej

**Privacy-preserving cross-bank AML and fraud intelligence for Saudi financial institutions.**  
Research prototype · Synthetic data (AMLworld) · Not production-ready

> **Origin:** the original hackathon concept was inspired by mule-account
> detection and carried the working title *MuleHunter.AI*. The product name
> is now **Naseej | نسيج** ("weave") — banks weaving a shared defense
> without sharing customer data.

---

## Problem Statement

Money-laundering mule accounts move stolen funds across multiple banks faster than any single institution can detect them. Each bank sees only its own slice of the transaction chain. Sharing raw customer data to fill this gap violates SDAIA PDPL and SAMA confidentiality requirements.

**The result:** coordinated fraud that spans institutions is systematically under-detected.

---

## Solution

Naseej lets banks share fraud intelligence without sharing customer data.

When Bank A detects a suspicious transaction topology — a fan-in velocity pattern, a rapid sweep, a cross-bank pass-through — it generates a **cryptographic pattern hash** that encodes only the structural shape of the fraud, not the identities involved. Bank B can match its own incoming transactions against that hash and flag matching patterns for analyst review.

```
Bank A                               Naseej Network              Bank B
───────                              ───────────────              ──────
Local transactions                                           Incoming transactions
       ↓                                                            ↓
Graph Analytics                     pattern hash            Hash comparison
       ↓              ──────────────────────────────────►         ↓
XGBoost risk score    zero PII crosses this boundary        FLAG / ESCALATE / ALLOW
       ↓
Privacy Hash Engine
NSJ_MULE_VELOCITY_deadbeef...
```

**Zero PII crosses the bank boundary.** No customer names, IBANs, national IDs, account numbers, or phone numbers are transmitted.

---

## Demo Flow

The live demo runs entirely in the browser. Backend connection enriches the data cards but is not required for the simulation.

| Stage | What you see |
|-------|-------------|
| **IDLE** | Both banks process normal transactions at 1.2s intervals |
| **ATTACK** | Click **RUN SIMULATION** — 5 micro-transfers fan into a mule account, followed by an international wire sweep |
| **DETECTED** | Bank A graph analytics flags the coordinated velocity breach; mule node turns red |
| **BROADCASTING** | A `NSJ_*` hash typewriter-decodes on screen; particles flow Bank A → Bank B |
| **FLAGGED** | Bank B shakes and stamps FLAGGED on a matching accomplice transaction for analyst review |

Click **RESET DEMO** to restart at any point.

When the flag fires, the detection becomes an analyst case: switch to the
**INVESTIGATOR** tab in the top nav to triage it — risk queue, "Why
flagged?" explanation, recommended action, attributed decisions, PII-guarded
notes, and the audit trail. With the backend live this runs through the real
case API; offline it falls back to clearly-labelled mock cases. The system
recommends — a human decides (see `docs/CASE_MANAGEMENT.md`).

---

## Architecture (Text Diagram)

```
┌─────────────────────────────────────────────────────────────────────┐
│ naseej-ai/ (React 18 + Vite — modular: config/ data/ lib/ hooks/    │
│             components/{ui,graph,panels})                           │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐ │
│  │ MLValidationCard         │  │ ResearchStrip                    │ │
│  │ live from /api/model/... │  │ cross-bank | score | pattern     │ │
│  └──────────────────────────┘  └──────────────────────────────────┘ │
│  ┌───────────────────────┐  ┌───────────────────────┐               │
│  │ BankAPanel            │  │ BankBPanel             │               │
│  │ GraphView · HashDisplay│  │ IntelFeed · BlockedStamp│            │
│  └───────────────────────┘  └───────────────────────┘               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ fetch (localhost:8000, 2.5s timeout)
┌───────────────────────────────▼─────────────────────────────────────┐
│ backend/ (FastAPI + Uvicorn :8000)                                  │
│  GET  /api/model/metrics         — XGBoost test metrics    (public) │
│  GET  /api/model/comparison      — LightGBM vs XGBoost …   (public) │
│  GET  /api/model/per-typology-recall — recall by typology  (public) │
│  GET  /api/model/threshold-analysis  — operating points    (public) │
│  GET  /api/model/ablation-report — feature ablation        (public) │
│  GET  /api/model/feature-contract — offline/online contract (public)│
│  GET  /api/model/feature-parity  — parity report           (public) │
│  GET  /api/model/training-feature-manifest — approved feats (public)│
│  GET  /api/model/candidate/* — shadow candidate reports    (public) │
│  POST /api/model/candidate/score-shadow — candidate vs base(node key)│
│  GET  /api/model/candidate/shadow-monitoring — aggregates  (node key)│
│  GET  /api/model/candidate/calibration-readiness          (public)  │
│  GET  /api/model/candidate/calibration-status             (public)  │
│  POST /api/feedback/from-case/{id} — closed-case label   (node key) │
│  GET  /api/feedback[/calibration-dataset] — node-scoped  (node key) │
│  GET  /api/demo/health           — demo readiness check    (public) │
│  GET  /api/demo/governance-evidence — governance pack      (public) │
│  GET  /api/demo/judge-summary    — judge brief             (public) │
│  GET  /api/cross-bank/results    — 4-bank experiment       (public) │
│  POST /api/score-transaction     — XGBoost inference     (node key) │
│  POST /api/analyze-pattern       — Patterns + privacy hash (node key)│
│  POST /api/patterns              — register threat pattern (node key)│
│  GET  /api/patterns[/{id}]       — query pattern registry (node key)│
│  POST /api/cases/from-pattern/{id} — open analyst case    (node key)│
│  GET/PATCH/POST /api/cases/...   — case lifecycle, notes, decisions │
│  POST /api/features/ingest-transaction — feed node-local windows    │
│  GET  /api/features/account/{id} — velocity features      (node key)│
│  POST /api/features/score-with-context — model + rule layer         │
│  POST /api/explain/transaction   — Why flagged? (SHAP)   (node key) │
│  GET  /api/explain/case/{id}     — case explanation      (node key) │
│  GET  /api/explain/model         — model evidence summary  (public) │
│  GET  /api/auth/whoami           — node, role, permissions(node key)│
│  Gates: auth → role/permissions → sharing scope → JSON Schema →     │
│         zero-PII guard → audit log                                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ imports
┌───────────────────────────────▼─────────────────────────────────────┐
│ ml/ (Python — models, reports, privacy engine)                      │
│  baseline_model.joblib           — XGBoost (32 features)            │
│  ml/src/privacy_hash.py          — NSJ_<TYPE>_<16hex> hashes        │
│  ml/src/pattern_library.py       — 8 AML pattern detectors          │
│  ml/src/cross_bank_experiment.py — 3-scenario recall proof          │
│  ml/src/evaluation_suite.py      — LightGBM/typology/ablation eval  │
│  ml/src/feature_contract.py      — canonical offline/online contract│
│  ml/src/feature_parity_check.py  — replay harness + parity checker  │
│  ml/reports/*.json               — live metrics served by backend   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## How to Run

### Prerequisites

- Node.js ≥ 18
- Python 3.11+
- Packages: `pip install -r backend/requirements.txt`

All commands run from the repository root (`C:\Users\...\Naseej\`).

### Frontend (demo only — no backend needed)

```bash
cd naseej-ai
npm install
npm run dev
# Opens at http://localhost:5173
```

The demo simulation runs entirely in the browser. If the backend is not running, metric cards show fallback values and the `API OFFLINE` indicator appears in the research strip.

### Backend (enriches the four data cards)

```bash
# Windows PowerShell
uvicorn backend.app.main:app --reload --port 8000

# Bash (Linux / macOS / Git Bash)
uvicorn backend.app.main:app --reload --port 8000
```

Or use the included helper scripts:

```bash
# PowerShell
.\scripts\run_backend.ps1

# Bash
bash scripts/run_backend.sh
```

### Judge / hackathon demo

Run the frontend (and backend for live strips), then follow
[`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — a speakable 5-minute flow. The
consolidated proof points are in [`docs/JUDGE_EVIDENCE_PACK.md`](docs/JUDGE_EVIDENCE_PACK.md),
and three public read-only endpoints expose them live:

```bash
curl localhost:8000/api/demo/health              # ready | partial | unavailable (+ checks, demo_safe)
curl localhost:8000/api/demo/governance-evidence # zero-PII, HITL, audit, RBAC, shadow-only, calibration
curl localhost:8000/api/demo/judge-summary       # problem/solution, real vs simulated, top differentiators
```

These carry no raw transactions, identifiers, or PII, and make **no** certified
or production-ready claims — **PDPL-by-design** and **SAMA-aligned prototype**
only. **Naseej is a research prototype on synthetic AMLworld data — not
production validation, not certified, not production-ready.**

API documentation: `http://localhost:8000/docs`

### API authentication (bank-node keys, roles, partitioning)

Scoring, pattern analysis, the pattern registry, and cases require an
`X-API-Key` header that maps to a registered node id. Health and read-only
research stats stay public.

```bash
# Configure real keys (NODE_ID:key pairs — disables the dev keys entirely)
export NASEEJ_NODE_KEYS="NODE_A7C2F9E1:your-secret-a,NODE_B3D8E2F4:your-secret-b"

# Optional: override node profiles (type, roles, capabilities) as JSON
export NASEEJ_NODE_PROFILES='{"NODE_A7C2F9E1": {"default_role": "senior_analyst"}}'
```

Each authenticated node resolves to a server-side profile — node type
(bank/regulator/admin), allowed analyst roles, and capability flags. Banks
see only their own cases and only the patterns their sharing scope allows
(`local_only` / `bilateral` / `network_all` / `regulator_only`); case
decisions are role-gated (analyst → senior_analyst → MLRO), and the acting
role comes from the auth context, never from request bodies. Check your
identity with `GET /api/auth/whoami`.

When `NASEEJ_NODE_KEYS` is **unset**, three clearly-labelled dev keys are
active so the local demo works with zero setup: Bank A (analyst),
`dev-key-bank-b-local-only` (Bank B, MLRO), and
`dev-key-regulator-local-only` (read-only regulator). The frontend sends
`dev-key-bank-a-local-only` by default; override with `VITE_NASEEJ_API_KEY`:

```bash
# 401 — no key
curl -X POST localhost:8000/api/score-transaction -H "Content-Type: application/json" -d '{...}'

# 200 — local simulation
curl -X POST localhost:8000/api/score-transaction \
  -H "Content-Type: application/json" -H "X-API-Key: dev-key-bank-a-local-only" -d '{...}'

# Register a threat pattern (schema + zero-PII gates enforced, audited)
curl -X POST localhost:8000/api/patterns \
  -H "Content-Type: application/json" -H "X-API-Key: dev-key-bank-a-local-only" \
  -d @docs/examples/threat_pattern_example.json
```

Every request to a protected endpoint is appended to the hash-chained audit
log at `backend/data/audit/audit.jsonl` (override: `NASEEJ_AUDIT_LOG`).
The registry persists to `backend/data/patterns.jsonl` (override:
`NASEEJ_REGISTRY_PATH`) and cases to `backend/data/cases.jsonl` (override:
`NASEEJ_CASES_PATH`). Details: [`docs/SECURITY_COMPLIANCE.md`](docs/SECURITY_COMPLIANCE.md).

### Tests

```bash
# From repo root — runs all 565 tests
python -m pytest backend/tests ml/tests -v

# Individual suites
python -m pytest ml/tests/test_privacy_hash.py -v          # 136 privacy-hash tests
python -m pytest backend/tests/test_access_control.py -v   # sharing scopes, ownership, RBAC
python -m pytest backend/tests/test_cases.py -v            # case lifecycle + transitions
python -m pytest backend/tests/test_pattern_registry.py -v # registry gates + audit
python -m pytest backend/tests/test_pii_guard.py -v        # zero-PII guard (Arabic/IBAN/phone)
python -m pytest backend/tests/test_auth.py -v             # node-key authentication
python -m pytest backend/tests/test_audit_service.py -v    # append-only hash chain
python -m pytest backend/tests/test_score_endpoint.py -v   # scoring endpoint
python -m pytest backend/tests/test_privacy_service.py -v  # endpoint PII safety
python -m pytest backend/tests/test_feature_store.py -v    # velocity windows + node isolation
```

### Train the baseline model (optional — model already included)

The trained model is already at `ml/models/baseline_model.joblib`. To retrain:

```bash
python -m ml.src.train_baseline \
    --input ml/data/features/train_features.parquet \
    --output ml/models/baseline_model.joblib \
    --sample 300000

# Outputs: ml/models/baseline_model.joblib
#          ml/reports/model_metrics.json
#          ml/reports/confusion_matrix.json
#          ml/reports/feature_importance.json
#          ml/reports/training_summary.md
```

Run the cross-bank experiment:

```bash
python -m ml.src.cross_bank_experiment

# Outputs: ml/reports/cross_bank_results.json
#          ml/reports/cross_bank_summary.md
```

### Run the ML evaluation suite (LightGBM, typology recall, ablation)

Separate from the deployed baseline above — this evaluates competitors on a
temporal split with point-in-time features and **does not touch**
`model_metrics.json` or `baseline_model.joblib`. See
[`docs/MODEL_EVALUATION.md`](docs/MODEL_EVALUATION.md).

```bash
python -m ml.src.evaluation_suite --train-sample 800000 --seed 42

# Outputs (served read-only at /api/model/*):
#   ml/reports/model_comparison.{json,md}      — LightGBM vs XGBoost vs RF vs LR
#   ml/reports/per_typology_recall.{json,md}   — recall by AML typology (heuristic labels)
#   ml/reports/threshold_analysis.{json,md}    — high-precision / balanced / high-recall modes
#   ml/reports/ablation_report.{json,md}       — transaction-only vs graph vs graph+context
```

LightGBM is optional: if it is not installed the suite skips it with a
recorded reason and reports the remaining models — results are never faked.

---

## Key ML Metrics

Trained on AMLworld HI-Small (IBM synthetic AML dataset, 475 MB). **Synthetic data only — not validated on real Saudi banking transactions.**

| Metric | Value |
|--------|-------|
| Model | XGBoost |
| Training rows | 210,000 (300k sample, 70/15/15 temporal split) |
| Test rows | 45,001 |
| Prevalence | 0.102% laundering |
| **PR-AUC** | **0.2275** |
| ROC-AUC | 0.9516 |
| Precision @ threshold | 27.3% |
| Recall @ threshold | 19.6% |
| F1 | 0.228 |
| False positive rate | 0.053% |
| Threshold (val F1-optimised) | 0.0606 |
| Alerts raised on test set | 33 |
| Laundering cases caught | 9 / 46 (20%) |

**Why PR-AUC?** At 0.102% prevalence, accuracy is misleading. PR-AUC measures the area under the precision-recall curve — the right metric when positive cases are rare and every catch matters.

### Evaluation suite findings (temporal split — separate protocol, not directly comparable)

A later evaluation phase ([`docs/MODEL_EVALUATION.md`](docs/MODEL_EVALUATION.md)) re-ran the comparison on a **temporal** 70/15/15 split with point-in-time features. Under that protocol:

| Finding | Result |
|---|---|
| Best model by held-out PR-AUC | **LightGBM 0.612** (XGBoost 0.578, RandomForest 0.574, LogReg 0.043) |
| Feature ablation | transaction-only **0.077** → +graph **0.179** → +context **0.555** |
| Strongest typology | rapid_sweep (recall 0.76), cross_bank_pass_through (0.56) |
| Weakest typology | `mule_velocity` (recall 0.05) — heuristic label |

The context-feature ablation is the key result: **graph and point-in-time context features drive almost all detection skill.** These numbers use a different split protocol than the deployed baseline above, so they are *not directly comparable* with the 0.2275 figure — and remain synthetic-benchmark only.

---

## Feature reconciliation — offline/online parity ([docs/FEATURE_CONTRACT.md](docs/FEATURE_CONTRACT.md))

Before any retrain/GNN, a canonical **feature contract** reconciles the offline
training features with the online feature-store features, and a **replay harness
+ parity checker** (four deterministic scenarios) prove they agree point-in-time:

- 8 windowed count/amount features match offline↔online exactly across all
  scenarios (`parity_targets_clean: true`).
- **Name collisions resolved (contract v2):** the online store now emits
  `fan_in_normalized_1h`/`fan_out_normalized_1h`; the offline 24h integer counts
  keep their legacy names under canonical `fan_in_count_24h`/`fan_out_count_24h`.
  The contract self-checks `collisions_resolved: true`.
- The **training manifest** approves **15** parity-clean, servable, non-memorising
  features and **excludes 29** — account/bank-id encodings (memorisation,
  permanently excluded; `is_cross_bank` is the structural replacement), all-time
  cumulatives (no 30d online twin), and serve-only graph/context features. Served
  at `/api/model/{feature-contract,feature-parity,training-feature-manifest}`.

```bash
python -m ml.src.feature_contract        # regenerate ml/features/feature_contract.json
python -m ml.src.feature_parity_check     # regenerate parity + training-manifest reports
```

**GNN stays blocked** until the approved set is parity-clean end to end.

---

## Shadow candidate model ([docs/CANDIDATE_MODEL.md](docs/CANDIDATE_MODEL.md))

A clean-room candidate trained on **only** the 15 approved parity-clean features
(no account/bank identity encodings, no serve-only or all-time features). It is
a **shadow evaluation — never deployed**; `baseline_model.joblib` and
`model_metrics.json` are never overwritten.

- Selected by validation PR-AUC: **XGBoost**, held-out test **PR-AUC 0.4247**,
  F1 0.4454 (LightGBM/RF/LogReg also evaluated).
- Below the identity-using ablation (`full_with_account_ids` 0.574) — the honest
  cost of excluding serve-only graph features and identity memorisation.
- SHAP explanations resolve through the feature contract; bucketed, PII-safe.
- Served read-only at `/api/model/candidate/{metrics,comparison,thresholds,explainability-check}`;
  a small **SHADOW ONLY** card appears in the demo when reports are present.

**Live shadow scoring** (`POST /api/model/candidate/score-shadow`, node auth):
runs the candidate beside the deployed baseline on the online feature path and
returns candidate vs baseline score + agreement — **comparison-only**. It never
creates a case, blocks/approves, or affects `/api/score-transaction`. Missing
candidate or no node history → safe `candidate_unavailable` / `missing_feature`.
Every request is audited (metadata only). Readiness:
`ml/reports/candidate_shadow_readiness.{json,md}`.

```bash
python -m ml.src.train_candidate_model --train-sample 800000 --seed 42
python -m ml.src.candidate_shadow_readiness   # regenerate the readiness report
```

**Shadow monitoring** ([docs/SHADOW_MONITORING.md](docs/SHADOW_MONITORING.md)):
each shadow score writes a **bucketed, PII-safe** observation (no raw
transactions/identifiers/values). `GET /api/model/candidate/shadow-monitoring`
(node auth, node-scoped) returns last-1h/24h/all aggregates — agreement rate,
candidate vs baseline alert rates, missing-feature rate, risk-tier transition
matrix — plus a **prototype drift signal** (normal / watch / unavailable).
`GET /api/model/candidate/calibration-readiness` (public) states the candidate
is **not calibrated** (no real labels in shadow mode) and **not** recommended
for deployment. A small **PROTOTYPE MONITORING — NO DEPLOYMENT DECISION** row
appears in the demo when observations exist.

**Analyst feedback loop** ([docs/ANALYST_FEEDBACK_LOOP.md](docs/ANALYST_FEEDBACK_LOOP.md)):
closing a case turns its outcome into a bucketed, PII-safe **calibration label**
(`closed_confirmed → confirmed_fraud`, etc.) via `POST /api/feedback/from-case/{id}`
(closed cases only; visibility/RBAC enforced; auto-captured on closure in the
demo). `GET /api/feedback/calibration-dataset` (node-scoped) aggregates labels;
below a minimum threshold it returns `insufficient_labels` and **never fakes**
calibration metrics. The candidate stays uncalibrated and undeployed —
**CALIBRATION DATASET — NOT PRODUCTION CALIBRATION**.

**Deployment not recommended** — synthetic benchmark only; the deployed model is untouched.

---

## Explainability — "Why flagged?" ([docs/EXPLAINABILITY.md](docs/EXPLAINABILITY.md))

Analyst-readable, **PII-safe** explanations for the Investigator Dashboard,
served by `backend/app/services/explanation_service.py`:

- `POST /api/explain/transaction` — base-model attribution (**SHAP** TreeExplainer
  on the deployed XGBoost when available; deterministic feature-importance +
  rule **fallback** otherwise) plus the contextual rule layer.
- `GET /api/explain/case/{id}` — typology rationale + bucketed evidence for a
  case (visibility + RBAC enforced, audited).
- `GET /api/explain/model` — evaluation-report summary (best/test-leader model,
  weakest typology, threshold policy, limitations), public.

Every factor shows a coarse `value_bucket` and a direction (`increases_risk` /
`decreases_risk`), **never raw amounts, account ids, or payloads**. A final PII
guard scrubs the whole payload so `pii_safe` is always truthful. Explanations
are decision-support only — not a legal/regulatory sufficiency statement, and
the deployed model is not retrained.

---

## Cross-Bank Experiment Results

39,990 transactions split across 4 simulated banks. XGBoost trained and evaluated under three scenarios per bank.

| Scenario | Avg Recall | PII shared |
|----------|-----------|-----------|
| A — Private (baseline) | 38.9% | None |
| B — Shared (pooled) | 44.4% | All raw feature vectors |
| **C — Naseej (pattern hashes)** | **66.7%** | **Anonymised hashes only** |

**Highlight — Bank 28856 (largest, most statistically robust):**

| Scenario | Recall |
|----------|--------|
| Private | 21.4% |
| Shared | 35.7% |
| **Naseej** | **64.3%** |

Naseej achieves **500% of the shared-model recall gain at zero PII cost**.

> These results use simulated bank partitions of the same synthetic dataset. Real multi-bank results require independent validation.

---

## Zero-PII Privacy Guarantee

Every pattern hash produced by Naseej passes the `verify_zero_pii()` check, which is proved by 136 automated tests. The following fields are **never included in any hash or API response**:

- Personal names (name, full_name, first_name, last_name)
- Financial identifiers (IBAN, BBAN, sort code, routing number)
- Government IDs (national_id, national_number, SSN, TIN, passport, driver's licence)
- Contact details (phone, mobile, telephone, email)
- Account identifiers (account_id, from_account, to_account, src_id, dst_id)
- Digital identifiers (IP address, device ID, MAC address)
- Biometric dates (date of birth)

The hash encodes only **fraud topology shape** — degree sequences, bucketed amounts, pattern type — never the identities of the accounts involved.

**Formal proof (central thesis):**

```python
# Bank A sees:  ACC_MULE_SA_001 receiving 5 inflows of ~2,400 SAR each
# Bank B sees:  SA44-2000-0001-2345 receiving 5 inflows of ~2,600 SAR each
# Same pattern, different IBANs, different amounts (same bucket)

hash_bank_a == hash_bank_b  # ← proved in TestSameTopologyDifferentPIIProducesIdenticalHash
```

---

## Compliance Alignment

| Framework | Alignment |
|-----------|-----------|
| SDAIA PDPL (Personal Data Protection Law) | Zero PII by design — proved by 136 tests |
| SAMA Counter-Fraud Framework | Proactive early-warning and cross-bank threat intelligence |
| Model governance | Human triage recommended; no autonomous production blocking |

---

## Limitations

1. **Model not retrained on context features.** A node-local feature store now computes real rolling 1h/24h velocity, counterparty and graph-window features (`docs/FEATURE_STORE.md`), and `/api/features/score-with-context` layers a transparent rule adjustment over the baseline score — but the XGBoost model itself has not been retrained on these features yet (every response states `model_retrained_on_context: false`). The legacy `/api/score-transaction` path still scores without history.
2. **Synthetic data only.** AMLworld is a research benchmark, not real banking data. Out-of-time validation on real Saudi transactions is required before any production deployment.
3. **Simulated federation.** The cross-bank broadcast is a frontend animation. Production requires a secure aggregation layer with PKI.
4. **Single-factor auth only.** Protected endpoints require per-node API keys (`NASEEJ_NODE_KEYS`) and access is partitioned per node profile, but it is one credential per node — analyst roles are selected within a server-configured envelope, not issued per person. No mTLS, key rotation, rate limiting, or replay protection yet — production requires the full API Gateway from the backend blueprint plus per-analyst credentials from each bank's IAM.
5. **Fixed bucketing.** Bucket boundaries are hardcoded. Changing them invalidates all existing hashes.

---

## Roadmap

| Horizon | Key additions |
|---------|--------------|
| Post-hackathon | ~~Feature store for velocity features~~ (done — `docs/FEATURE_STORE.md`) · retrain on context features · SHAP explainability · GNN baseline |
| Pilot prototype | Out-of-time validation · Analyst case management UI · Configurable thresholds |
| Controlled pilot | Tokenised real data · Federated learning (Flower) · Differential privacy |
| Production path | SAMA sandbox · Multi-bank PKI · Streaming pipeline · Model governance |

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/TECHNICAL_ARCHITECTURE.md`](docs/TECHNICAL_ARCHITECTURE.md) | Current system architecture, ML pipeline, API reference |
| [`docs/BACKEND_BLUEPRINT.md`](docs/BACKEND_BLUEPRINT.md) | Post-MVP service decomposition (gateway, registry, privacy layer, …) |
| [`docs/THREAT_PATTERN_CONTRACT.md`](docs/THREAT_PATTERN_CONTRACT.md) | Zero-PII threat intelligence data contract + [JSON Schema](docs/schemas/threat_pattern.schema.json) |
| [`docs/SECURITY_COMPLIANCE.md`](docs/SECURITY_COMPLIANCE.md) | PDPL-by-design, SAMA alignment, audit, incident response, retention, out-of-scope |
| [`docs/CASE_MANAGEMENT.md`](docs/CASE_MANAGEMENT.md) | Case lifecycle, human-in-the-loop decision model, status machine, simulated vs real |
| [`docs/FEATURE_STORE.md`](docs/FEATURE_STORE.md) | Feature catalogue, rolling velocity windows, node isolation, contextual scoring honesty |
| [`docs/ML_ROADMAP.md`](docs/ML_ROADMAP.md) | 7-phase roadmap: rules → XGBoost → GNN → federated → governance |
| [`docs/INVESTIGATOR_EXPERIENCE.md`](docs/INVESTIGATOR_EXPERIENCE.md) | Fraud-analyst workspace design (risk queue, why-flagged, overrides, audit) |
| [`docs/DEMO_SCRIPT_RESEARCH_VERSION.md`](docs/DEMO_SCRIPT_RESEARCH_VERSION.md) | Presentation script + judge Q&A |
| [`docs/JUDGES_BRIEF.md`](docs/JUDGES_BRIEF.md) | Executive summary for evaluators |
| [`naseej-ai/README.md`](naseej-ai/README.md) | Frontend module structure and design decisions |

---

## Academic Foundation

- Malik Ashfaq Ur Rahman, *AI-Driven Fraud Detection and Financial Security Framework for Saudi Banking Systems* (May 2026)
- Edgar Altszyler et al., "Realistic Synthetic Financial Transactions for Anti-Money Laundering Models" (AMLworld / IBM, NeurIPS 2022)
- McMahan et al., "Communication-Efficient Learning of Deep Networks from Decentralized Data" (Google AI, 2017) — Federated Learning

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18.3 · Vite 5.4 · Tailwind CSS 3.4 · Framer Motion 12 · Lucide React |
| Backend | Python 3.11 · FastAPI 0.115 · Uvicorn · Pydantic v2 |
| ML | XGBoost · scikit-learn · Pandas · NumPy · joblib |
| Privacy | SHA-256 · canonical JSON · value bucketing |
| Dataset | AMLworld HI-Small (IBM synthetic, 475 MB) |
| Tests | pytest 9.0.3 · FastAPI TestClient · httpx |

---

*Research prototype. Production deployment requires SAMA supervision, adversarial robustness testing, real cryptographic federation, and independent validation on real banking data.*
