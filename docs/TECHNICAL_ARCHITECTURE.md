# Technical Architecture — نسيج | Naseej

**Version:** Phase 10 (Research Prototype / Hackathon MVP)  
**Status:** All phases 0–9 complete  
**Honest framing:** This is a research-grade prototype built on synthetic AML data. It is not production banking infrastructure.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Repository Layout](#2-repository-layout)
3. [Frontend Architecture](#3-frontend-architecture)
4. [Backend Architecture](#4-backend-architecture)
5. [ML Pipeline Architecture](#5-ml-pipeline-architecture)
6. [Dataset Pipeline](#6-dataset-pipeline)
7. [Graph Feature Engineering](#7-graph-feature-engineering)
8. [Baseline Model Training](#8-baseline-model-training)
9. [Cross-Bank Experiment](#9-cross-bank-experiment)
10. [Privacy-Preserving Pattern Hash Engine](#10-privacy-preserving-pattern-hash-engine)
11. [API Endpoint Reference](#11-api-endpoint-reference)
12. [Test Coverage Summary](#12-test-coverage-summary)
13. [Known Limitations](#13-known-limitations)
14. [Future Roadmap](#14-future-roadmap)

---

## 1. System Overview

Naseej is a privacy-preserving fraud intelligence layer that allows Saudi banks to detect mule-account AML patterns across institutions without sharing customer PII.

### Core thesis

```
Two banks observing the same laundering topology will produce identical
pattern hashes — even when their account identifiers are completely different.
This enables cross-institution threat sharing with zero raw data exchange.
```

### High-level data flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BANK A (Local Node)                         │
│                                                                     │
│  Transactions → Graph Feature Engineering → XGBoost Risk Score     │
│                              ↓                                      │
│                   Pattern Library (fan-in, mule-velocity, …)        │
│                              ↓                                      │
│            Privacy Hash Engine → NSJ_<TYPE>_<16hex> hash            │
│                              ↓                                      │
│                   Zero-PII hash broadcast                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  (no raw PII crosses this boundary)
┌──────────────────────────────▼──────────────────────────────────────┐
│                      NASEEJ FEDERATED LAYER                         │
│              Secure aggregation of anonymised pattern hashes         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                         BANK B (Receiving Node)                     │
│                                                                      │
│  Incoming transaction → hash comparison → BLOCK / FLAG / ALLOW      │
└──────────────────────────────────────────────────────────────────────┘
```

### Stack summary

| Layer | Technology |
|-------|-----------|
| Frontend | React 18.3 + Vite 5.4 + Tailwind CSS 3.4 + Framer Motion 12 |
| Backend | Python 3.11 · FastAPI 0.115 · Uvicorn |
| ML | XGBoost · scikit-learn · Pandas · NumPy |
| Privacy | SHA-256 · canonical JSON · value bucketing |
| Dataset | AMLworld HI-Small (IBM, 475 MB synthetic AML) |
| Tests | pytest 9.0.3 · FastAPI TestClient · 209 tests |

---

## 2. Repository Layout

```
Naseej/
├── naseej-ai/                  # React 18 frontend
│   └── src/App.jsx             # ~1300-line single-file UI
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                # 4 route modules
│   │   ├── core/               # config.py, schemas.py
│   │   └── services/           # model, scoring, graph, demo, privacy services
│   └── tests/                  # 81 backend tests
├── ml/
│   ├── data/
│   │   ├── raw/                # HI-Small_Trans.csv (475 MB, read-only)
│   │   ├── processed/          # train/val/test.parquet (~165 MB)
│   │   ├── features/           # engineered feature parquets (~290 MB)
│   │   └── samples/            # 5k and 100k sample parquets
│   ├── models/                 # baseline_model.joblib + legacy .pkl
│   ├── reports/                # JSON + Markdown reports
│   ├── src/                    # importable Python modules (Phase 1-6)
│   └── tests/                  # 136 privacy-hash tests
├── docs/                       # All documentation
├── scripts/                    # run_backend.sh/ps1, run_frontend.sh/ps1, etc.
├── conftest.py                 # Root pytest configuration
├── pytest.ini                  # testpaths + importlib mode
└── PRD.md / README.md / References.md
```

---

## 3. Frontend Architecture

**File:** `naseej-ai/src/App.jsx` (~1300 lines, single-file)

### State machine

```
STAGES = { IDLE: 0, ATTACK: 1, DETECTED: 2, BROADCASTING: 3, BLOCKED: 4 }
```

The simulation is driven by `setTimeout` chains in `handleRun()`. All timing is hard-coded and deterministic — the demo is always reproducible.

### Layout (top-to-bottom)

```
┌──────────────────────────────────────────────────────┐
│ Top nav: NASEEJ.AI branding + network status          │
├──────────────────────────────────────────────────────┤
│ MLValidationCard: live model metrics (API or fallback)│
├──────────────────────────────────────────────────────┤
│ ResearchStrip: cross-bank | live score | pattern      │
│                                    API: ● LIVE/OFFLINE│
├──────────────────────────────────────────────────────┤
│ BankAPanel              │  BankBPanel                 │
│ - Stats grid            │  - Stats grid               │
│ - Alert banner          │  - Federated log            │
│ - Live TX feed          │  - Live TX feed             │
│ - Graph (SVG mule map)  │  - FL status / BLOCKED      │
│ - Hash display          │                             │
│           BroadcastPulse (BROADCASTING stage)         │
├──────────────────────────────────────────────────────┤
│ ControlBar: RUN SIMULATION / RESET DEMO + stage label │
└──────────────────────────────────────────────────────┘
```

### Backend API layer

```javascript
const API_BASE = 'http://localhost:8000'

async function apiFetch(path, init = {}) { ... }
// - AbortSignal.timeout(2500ms)
// - Returns null on any error → safe fallback
```

**Fallback strategy:** All four cards display hardcoded fallback data when the backend is unreachable. The demo runs identically with or without a live backend.

### Backend calls

| When | Endpoint | Data shown |
|------|----------|-----------|
| Mount | `GET /api/model/metrics` | MLValidationCard (PR-AUC, Precision, etc.) |
| Mount | `GET /api/cross-bank/results` | CrossBankSection (recall bars) |
| Stage → ATTACK | `POST /api/score-transaction` | LiveScoreSection (risk %, verdict) |
| Stage → DETECTED | `POST /api/analyze-pattern` | PatternSection (type, tier, action) |

### Key components

| Component | Purpose |
|-----------|---------|
| `MLValidationCard` | Prop-driven metrics; CountUp animation |
| `ResearchStrip` | New Phase 8 strip; 3 live-data sections |
| `CrossBankSection` | Animated recall bars |
| `LiveScoreSection` | Live risk score from API |
| `PatternSection` | Live pattern analysis result |
| `BankAPanel` / `BankBPanel` | Left/right split-screen |
| `GraphView` | SVG mule network (SRC→MULE→INTL) |
| `HashDisplay` | Matrix typewriter decode effect |
| `BroadcastPulse` | Framer Motion particle flow A→B |

---

## 4. Backend Architecture

**Entry point:** `uvicorn backend.app.main:app --reload --port 8000`

### Module structure

```
backend/app/
├── main.py               # FastAPI app, CORS middleware, router registration
├── core/
│   ├── config.py         # Path resolution (REPO_ROOT parents[3]), CORS origins
│   └── schemas.py        # Pydantic v2 request/response models
├── api/
│   ├── routes_health.py  # GET /health
│   ├── routes_model.py   # GET /api/model/metrics, /api/model/feature-importance
│   ├── routes_graph.py   # POST /api/score-transaction, POST /api/analyze-pattern
│   └── routes_demo.py    # GET /api/cross-bank/results, GET /api/demo/research-summary
└── services/
    ├── model_service.py    # Lazy-loads baseline_model.joblib bundle
    ├── scoring_service.py  # Feature extraction + XGBoost inference (Phase 7)
    ├── privacy_service.py  # Wraps ml.src.privacy_hash for endpoint use
    ├── graph_service.py    # Pattern analysis orchestration
    └── demo_service.py     # Research summary + cross-bank fallbacks
```

### Graceful degradation

Every endpoint has a fallback path. If `baseline_model.joblib` is absent, `/api/score-transaction` uses a heuristic (amount / 50,000). If report files are missing, static endpoints return `"source": "fallback"` with safe placeholder data. The frontend never receives a 500 error.

### CORS

Configured for `http://localhost:5173` (Vite dev server). Update `CORS_ORIGINS` in `backend/app/core/config.py` for other environments.

---

## 5. ML Pipeline Architecture

```
HI-Small_Trans.csv (raw, 475 MB)
        │
        ▼
ml/src/data_loader.py          — column normalisation, schema validation, sampling
        │
        ▼
ml/src/preprocessing.py        — timestamp parsing, bank IDs, payment encoding
        │
        ▼
ml/scripts/build_graph_features.py  — cumulative + velocity + mule-pattern features
        │ (produces ml/data/features/*.parquet, ~290 MB)
        │
        ▼
ml/src/train_baseline.py       — model zoo (LR, RF, XGBoost), temporal split,
        │                        best-model selection by val PR-AUC
        │ (produces ml/models/baseline_model.joblib + ml/reports/*.json)
        │
        ├──▶ ml/src/cross_bank_experiment.py   — 3-scenario cross-bank proof
        │         (produces ml/reports/cross_bank_results.json)
        │
        └──▶ ml/src/pattern_library.py         — 8 AML detectors
                 + ml/src/privacy_hash.py       — zero-PII hash engine
```

### Model bundle format

```python
# Written by ml/src/train_baseline.py line 303:
joblib.dump({
    "model":           best_estimator,      # XGBClassifier
    "feature_columns": feat_cols,           # ordered list of 32 column names
    "threshold":       val_thr,             # optimal threshold by val F1
    "model_name":      best_name,           # "xgboost"
}, out_path)
```

---

## 6. Dataset Pipeline

**Source:** IBM / AMLworld "Realistic Synthetic Financial Transactions for Anti-Money Laundering Models" — HI-Small split.

| File | Size | Rows | Laundering ratio |
|------|------|------|-----------------|
| `HI-Small_Trans.csv` | 475 MB | ~5.1M | 0.102% |
| `ml/data/processed/train.parquet` | ~55 MB | ~3.6M | 0.102% |
| `ml/data/processed/val.parquet` | ~12 MB | ~760k | 0.102% |
| `ml/data/processed/test.parquet` | ~12 MB | ~760k | 0.102% |
| `ml/data/features/train_features.parquet` | ~115 MB | ~3.6M | 0.102% |

**Column schema (AMLworld CSV → normalized):**

| Original CSV header | Normalized column |
|---------------------|------------------|
| Timestamp | timestamp |
| From Bank | from_bank (→ source_bank) |
| Account | from_account (→ source_account) |
| To Bank | to_bank (→ target_bank) |
| Account.1 | to_account (→ target_account) |
| Amount Paid | amount |
| Payment Currency | currency |
| Payment Format | payment_type |
| Is Laundering | is_laundering (label) |

**Honesty note:** This is synthetic data. It is not a substitute for real Saudi banking transactions. Production deployment would require SAMA-supervised data sharing agreements and out-of-time validation on real transaction flows.

---

## 7. Graph Feature Engineering

**Module:** `ml/scripts/build_graph_features.py` (production, 32 output features)  
**Module:** `ml/src/graph_features.py` (modular Phase-3 version, 25 features)

### Feature categories

#### Base features (per-row, O(n))
| Feature | Description |
|---------|-------------|
| `amount` | Transaction amount (SAR) |
| `payment_type_enc` | Label-encoded payment format |
| `currency_enc` | Label-encoded currency |
| `source_bank_enc` / `target_bank_enc` | Label-encoded bank IDs |
| `source_account_enc` / `target_account_enc` | Label-encoded account IDs |
| `is_cross_bank` / `cross_bank_flow_flag` | 1 if banks differ |
| `hour` / `day_of_week` / `is_weekend` | Timestamp decomposition |

#### Cumulative features (O(n) via groupby cumcount/cumsum)
| Feature | Description |
|---------|-------------|
| `source_out_tx_count_total_before` | Outgoing tx count before current row |
| `source_out_amount_sum_total_before` | Cumulative amount sent |
| `source_unique_targets_total_before` | Distinct targets seen so far |
| `target_in_tx_count_total_before` | Incoming tx count |
| `target_in_amount_sum_total_before` | Cumulative amount received |
| `target_unique_sources_total_before` | Distinct sources seen so far |
| `account_pair_tx_count_before` | Transactions between this exact src→dst pair |
| `account_pair_amount_sum_before` | Cumulative amount for this pair |

#### Velocity features (O(n log n) via merge_asof rolling window)
| Feature | Window |
|---------|--------|
| `source_out_tx_count_1h` / `source_out_amount_sum_1h` | 1-hour rolling |
| `target_in_tx_count_1h` / `target_in_amount_sum_1h` | 1-hour rolling |
| `source_out_tx_count_24h` / `source_out_amount_sum_24h` | 24-hour rolling |
| `target_in_tx_count_24h` / `target_in_amount_sum_24h` | 24-hour rolling |

**Leakage prevention:** All features use strictly past data — `cumcount()` before current row, velocity windows `(t - window, t)` exclusive.

#### Mule-pattern features (O(n), derived arithmetic)
| Feature | Description |
|---------|-------------|
| `fan_in_score` | Rolling inflow count to target (24h) |
| `fan_out_score` | Rolling outflow count from source (24h) |
| `sweep_ratio` | `amount / (historical_avg_outflow + ε)` |
| `rapid_movement_flag` | 1 if ≥2 outflows in 1h or ≥3 in 24h with above-avg total |

### Top features by XGBoost importance

| Rank | Feature | Importance |
|------|---------|-----------|
| 1 | `payment_type_enc` | 0.211 |
| 2 | `account_pair_tx_count_before` | 0.154 |
| 3 | `is_cross_bank` | 0.076 |
| 4 | `target_unique_sources_total_before` | 0.047 |
| 5 | `cross_bank_flow_flag` | 0.045 |
| 6 | `account_pair_amount_sum_before` | 0.036 |
| 7 | `source_out_amount_sum_total_before` | 0.033 |
| 8 | `source_out_tx_count_24h` | 0.029 |

---

## 8. Baseline Model Training

**Module:** `ml/src/train_baseline.py`

### Model zoo

| Model | val PR-AUC | val ROC-AUC | val F1 | Fit time |
|-------|-----------|------------|-------|---------|
| Logistic Regression | 0.0244 | 0.9519 | 0.0732 | 4.1s |
| Random Forest | 0.1356 | 0.9109 | 0.2692 | 13.7s |
| **XGBoost** (selected) | **0.2271** | **0.9697** | **0.2955** | **4.3s** |

Selection criterion: highest val PR-AUC. XGBoost wins.

### Test-set evaluation (Phase 4 — 300,000 row sample, temporal split)

| Metric | Value |
|--------|-------|
| Model | XGBoost |
| Threshold (val-optimised F1) | 0.0606 |
| PR-AUC | **0.2275** |
| ROC-AUC | 0.9516 |
| Precision | 27.3% |
| Recall | 19.6% |
| F1 | 0.228 |
| False Positive Rate | 0.053% |
| Alerts raised | 33 |
| Confirmed laundering caught | 9 / 46 positive cases |
| Prevalence | 0.102% |

**Why PR-AUC over accuracy:** At 0.102% prevalence, a model that labels everything as benign achieves 99.9% accuracy but catches zero fraud. PR-AUC measures performance under class imbalance where it matters.

### XGBoost hyperparameters

```python
XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    tree_method="hist", eval_metric="aucpr",
)
```

### Ablation variants

`ml/models/full_features/` and `ml/models/no_account_id/` contain ablation runs that compare performance with and without account ID encoding. The `no_account_id` variant demonstrates that graph and velocity features alone carry meaningful signal even without identity-based leakage.

---

## 9. Cross-Bank Experiment

**Module:** `ml/src/cross_bank_experiment.py`  
**Output:** `ml/reports/cross_bank_results.json`, `ml/reports/cross_bank_summary.md`

### Design

39,990 transactions split across 4 simulated banks proportional to transaction volume. Three scenarios trained and evaluated per bank:

| Scenario | Training data | PII shared |
|----------|--------------|-----------|
| A — Private | Bank's own transactions only | None |
| B — Shared | Pooled raw features from all banks | All raw feature vectors |
| C — Naseej | Own transactions + cross-bank pattern signals | Anonymised hashes only |

### Naseej cross-bank features (Scenario C)

```
global_source_bank_count     — distinct banks where source appears
global_target_bank_count     — distinct banks where target appears
global_source_out_degree     — source's total tx count network-wide
global_target_in_degree      — target's total incoming count
local_vs_global_out_ratio    — fraction of source activity visible locally
```

In production these are derived from SHA-256 pattern hashes contributed by each bank and aggregated by a secure aggregator — no raw transaction rows cross bank boundaries.

### Results

| Scenario | Avg Recall (4 banks) | Recall gain vs. private |
|----------|---------------------|------------------------|
| A — Private | 38.9% | — |
| B — Shared | 44.4% | +5.6 pp |
| **C — Naseej** | **66.7%** | **+27.8 pp** |

**Highlight — Bank 28856 (largest, most statistically robust):**

| Scenario | Recall | Confirmed detected |
|----------|--------|-------------------|
| Private | 21.4% | 3 / 14 |
| Shared | 35.7% | 5 / 14 |
| **Naseej** | **64.3%** | **9 / 14** |

Naseej recall efficiency vs. raw data sharing: **+500%** of the shared-model recall gain at zero PII cost.

**Caveat:** Experiment uses the same synthetic dataset split into simulated banks. The result should be validated on real multi-bank data before production claims.

---

## 10. Privacy-Preserving Pattern Hash Engine

**Module:** `ml/src/privacy_hash.py` (Phase 6)  
**Service:** `backend/app/services/privacy_service.py`

### Design invariants

1. **No raw identifiers** — account IDs, IBANs, names, phones stripped before hashing
2. **Bucketed continuous values** — amounts/counts mapped to ordered tiers so minor cross-bank differences don't break hash matching
3. **Canonical serialisation** — `json.dumps(sort_keys=True)` ensures identical bytes for identical payloads
4. **Topology-only** — structural shape (degree sequence, edge count, pattern type) encoded; no node identities

### Hash format

```
NSJ_<PATTERN_TYPE_UPPER>_<16-hex-chars>

Examples:
  NSJ_FAN_IN_a3b7c2d1e4f58901
  NSJ_MULE_VELOCITY_deadbeef12345678
  NSJ_TOPO_abcdef0123456789
```

### PII field registry (25 fields)

```python
PII_FIELDS = {
    "name", "full_name", "first_name", "last_name",
    "iban", "bban", "sort_code", "routing_number",
    "national_id", "national_number", "ssn", "tin",
    "phone", "mobile", "telephone",
    "email", "email_address",
    "account_id", "from_account", "to_account", "raw_id", "src_id", "dst_id",
    "passport", "driver_license",
    "ip_address", "device_id", "mac_address",
    "dob", "date_of_birth",
}
```

### Value bucketing tiers

| Category | Tiers |
|----------|-------|
| Amount | micro (≤1k) / small (≤10k) / medium (≤50k) / large (≤200k) / xlarge (>200k) |
| Count | single (≤2) / few (≤5) / moderate (≤15) / high (≤50) / extreme (>50) |
| Time | rapid (≤1min) / within_1h / same_day / weekly / extended |
| Risk | low (≤0.4) / medium (≤0.7) / high (≤0.9) / critical (≤1.0) |

### Proven cross-bank matching property

Two banks observing the same mule-velocity pattern with different account IDs (Bank A: `ACC_MULE_SA_001`, Bank B: `SA44-2000-0001-2345`) produce **identical hashes** after normalization, because:
- Account IDs are stripped by `remove_pii_fields()`
- Amounts in the same bucket → same tier label → same canonical JSON → same SHA-256

This property is formally proved in `ml/tests/test_privacy_hash.py::TestSameTopologyDifferentPIIProducesIdenticalHash`.

### Pattern library detectors

| Detector | AML Typology |
|----------|-------------|
| `detect_fan_in` | Many sources → one collector |
| `detect_fan_out` | One source → many targets |
| `detect_mule_velocity` | High-velocity inflows in short window |
| `detect_rapid_sweep` | Receive then immediately forward ≥80% |
| `detect_simple_cycle` | A→B→C→A layering cycle |
| `detect_cross_bank_pass_through` | In from Bank X, out to Bank Y |
| `detect_scatter_gather` | Disperse then reconverge |
| `detect_gather_scatter` | Collect then disperse |

---

## 11. API Endpoint Reference

**Base URL:** `http://localhost:8000`  
**Documentation:** `http://localhost:8000/docs` (Swagger UI)

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service status, name, version |

### Model

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/model/metrics` | XGBoost test-set metrics (PR-AUC, ROC-AUC, F1, threshold, etc.) |
| GET | `/api/model/feature-importance` | Top-25 features by XGBoost gain |

### Transaction Intelligence

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/score-transaction` | Single-transaction risk score via XGBoost |
| POST | `/api/analyze-pattern` | Multi-transaction pattern detection + zero-PII hash |

#### POST /api/score-transaction

```json
// Request
{
  "timestamp": "2024/06/15 02:15",
  "from_bank": "101",
  "from_account": "ACC_001",
  "to_bank": "28856",
  "to_account": "ACC_002",
  "amount": 11200.0,
  "currency": "US Dollar",
  "payment_format": "Wire"
}

// Response
{
  "risk_score": 0.000006,
  "prediction": "benign",
  "reasons": [
    "Cross-bank transfer (source and destination bank differ)",
    "Off-hours transaction (hour 02:xx)",
    "Velocity and cumulative features unavailable (no account history provided)..."
  ],
  "pattern_hash": "NSJ_SINGLE_TRANSACTION_a3b7c2d1e4f58901",
  "zero_pii": true,
  "source": "model"
}
```

**Note on conservative scoring:** Without account history, velocity and cumulative features default to 0. The model scores near base-rate for isolated transactions. The `reasons` array always discloses this limitation.

#### POST /api/analyze-pattern

```json
// Request
{
  "transactions": [
    {"from_bank": "101", "from_account": "SRC_1", "to_bank": "101",
     "to_account": "MULE", "amount": 2400.0, "payment_format": "ACH"},
    ...
  ]
}

// Response
{
  "detected_patterns": [
    {
      "pattern_type": "mule_velocity",
      "risk_tier": "high",
      "risk_score": 0.85,
      "reason": "5 inflows totalling 10100 within 60m on a single account.",
      "features": {"n_inflows": "few", "total_amount": "small"},
      "pattern_hash": "NSJ_MULE_VELOCITY_deadbeef12345678",
      "zero_pii": true
    }
  ],
  "graph_summary": {"tx_count": 6, "unique_accounts": 7, "total_amount": 21100.0},
  "risk_score": 0.85,
  "pattern_hash": "NSJ_MULE_VELOCITY_deadbeef12345678",
  "recommended_action": "block",
  "zero_pii": true,
  "source": "engine"
}
```

### Demo

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cross-bank/results` | Full cross-bank experiment (4 banks, 3 scenarios) |
| GET | `/api/demo/research-summary` | High-level research overview |

---

## 12. Test Coverage Summary

**Command:** `pytest backend/tests ml/tests -v`  
**Result:** 209 passed / 0 failed in 2.15s

| File | Tests | Coverage area |
|------|-------|--------------|
| `ml/tests/test_privacy_hash.py` | 136 | Privacy-hash engine (full proof) |
| `backend/tests/test_score_endpoint.py` | 24 | Score-transaction endpoint |
| `backend/tests/test_privacy_service.py` | 48 | Backend privacy service + endpoints |
| `backend/tests/test_health.py` | 9 | Health endpoint |

### Privacy invariants formally proved

| Test class | Invariant |
|-----------|-----------|
| `TestRemovePIIFields` | All 7 PII categories stripped; recursive; case-insensitive; copy semantics |
| `TestVerifyZeroPII` (parameterized ×25) | Every PII_FIELDS entry causes False return |
| `TestBucketAmount/Count/Time/Risk` | All tier boundaries verified at edge cases |
| `TestSameTopologyDifferentPIIProducesIdenticalHash` | Central cross-bank thesis: Bank A IBAN ≠ Bank B account → same hash |
| `TestGenerateTopologySignature` | Same graph structure + different node labels → same signature |
| `TestAnalyzePatternEndpointZeroPII` | No raw account IDs in any response field |
| `TestScoreTransactionEndpointZeroPII` | PII embedded in account strings not reflected in output |

---

## 13. Known Limitations

### ML model

- **Conservative single-transaction scoring.** Without account history, velocity and cumulative features are zeroed. The XGBoost model scores near base-rate (0.1%) for isolated transactions. A feature store keyed on account ID would be required for production-grade real-time scoring.
- **Synthetic data only.** The model was trained on AMLworld HI-Small. Performance on real Saudi banking transactions is unknown. Out-of-time validation would be required before any production deployment.
- **Categorical encoder not exported.** The LabelEncoder fitted for account IDs during training is not saved in the joblib bundle. Unknown accounts use -1 (correct fallback), but known account encoding cannot be replicated without the original encoder.
- **Sample size.** Phase 4 trained on a 300,000-row sample of the full dataset (5.1M rows) to meet time constraints. Full-dataset training would likely improve PR-AUC.

### Cross-bank experiment

- **Simulated banks.** The 4 "banks" are partitions of the same synthetic dataset, not independent institutions with different data distributions. Real cross-bank results would differ.
- **No adversarial robustness testing.** An attacker aware of the bucketing scheme could potentially craft transactions that produce matching hashes for different attack patterns. Differential privacy and adversarial testing are future work.

### Privacy hash

- **Bucket granularity vs. collision risk.** Wider buckets increase cross-bank matching but also false-positive matching rate. Narrower buckets reduce false matches but may split genuinely equivalent patterns.
- **Salt version control.** Changing the normalisation schema requires bumping the salt ("naseej-v1"), invalidating all existing hashes.

### Infrastructure

- **No production federation.** The federated broadcast is simulated in the frontend. Production would require a secure aggregation layer, PKI, and potentially differential privacy on pattern statistics.
- **No authentication.** The backend API has no authentication or rate limiting. Production deployment would require both.
- **CORS is open for localhost only.** Production would require proper origin management.

---

## 14. Future Roadmap

### Immediate (post-hackathon)

- Export the fitted LabelEncoder alongside the model bundle for accurate single-transaction scoring
- Build a feature store for real-time velocity feature computation
- Add SHAP explainability to the XGBoost model

### Short-term (pilot prototype)

- Graph Neural Network baseline (GIN / GraphSAGE) on transaction subgraphs
- Out-of-time validation on held-out months of data
- Case management UI for analyst review workflow
- Configurable thresholds and operating modes per bank

### Medium-term (controlled banking pilot)

- Tokenised real transaction feeds (SAMA-supervised data sharing)
- Federated learning prototype (Flower / OpenFL framework)
- Differential privacy on shared pattern statistics
- Adversarial robustness testing against hash-manipulation attacks
- Model monitoring and drift detection

### Long-term (production path)

- SAMA sandbox engagement
- Multi-bank secure aggregation with PKI
- Real-time streaming feature pipeline (Kafka / Flink)
- Regulatory-grade audit logging and explainability
- Model governance framework and human-in-the-loop controls

---

*This document describes a research prototype built on synthetic data. All claims about detection performance refer to the AMLworld benchmark dataset and should not be extrapolated to production banking environments without independent validation.*
