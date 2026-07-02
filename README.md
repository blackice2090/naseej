<div align="center">
<div align="center">

<p align="center">
  <img src="./naseejlogo.png" alt="Naseej Logo" width="150">
</p>

# نسيج | Naseej
**Privacy-preserving cross-bank AML & fraud intelligence for Saudi financial institutions.**

Banks weave a shared defense against money-laundering mule networks — *without ever sharing customer data.*

**Team Madar | فريق مدار · AMAD Hackathon · FinTech Track**

<br>

![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.4-646CFF?logo=vite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-06B6D4?logo=tailwindcss&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-baseline_model-FF6600)
![Privacy by Design](https://img.shields.io/badge/Privacy-by--design-2E7D32)
![Synthetic Data](https://img.shields.io/badge/Data-Synthetic_AMLworld-6A1B9A)
![Tests](https://img.shields.io/badge/tests-565%20passing-brightgreen)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)

</div>

> [!IMPORTANT]
> **Naseej is a research prototype.** It is trained and evaluated on **synthetic data only** (IBM AMLworld) and is **not production-ready**, **not certified**, and **not validated on real Saudi banking transactions**. All privacy and compliance claims are *by-design* properties demonstrated in a prototype — not formal certifications.

> **Origin:** the original hackathon concept was inspired by mule-account detection and carried the working title *MuleHunter.AI*. The product name is now **Naseej | نسيج** ("weave") — banks weaving a shared defense without sharing customer data.

---

## Table of Contents

- [Overview](#overview)
- [Problem](#problem)
- [Solution](#solution)
- [Key Features](#key-features)
- [Demo Screenshots](#demo-screenshots)
- [Demo Flow](#demo-flow)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Dataset](#dataset)
- [ML Validation](#ml-validation)
- [Model Governance & Advanced ML](#model-governance--advanced-ml)
- [Privacy & Compliance](#privacy--compliance)
- [How to Run](#how-to-run)
- [API Overview](#api-overview)
- [Tests](#tests)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [Team](#team)
- [References & Dataset Source](#references--dataset-source)
- [License & Prototype Disclaimer](#license--prototype-disclaimer)

---

## Overview

Naseej lets banks share **fraud intelligence** without sharing **customer data**.

When one bank detects a suspicious transaction topology — a fan-in velocity pattern, a rapid sweep, a cross-bank pass-through — it detects the pattern *locally*, converts it into a **zero-PII cryptographic pattern hash**, and broadcasts only that hash. Any other bank can match the hash against its own incoming transactions and flag look-alike patterns for analyst review. No customer names, IBANs, national IDs, phone numbers, or account identifiers ever cross the bank boundary.

The repository contains a working end-to-end prototype:

- a **React + Vite** browser demo (`naseej-ai/`) that visualizes a live cross-bank attack and detection,
- a **FastAPI** backend (`backend/`) exposing scoring, pattern-registry, case-management, feature-store, explainability, and governance endpoints,
- a real **XGBoost** ML pipeline (`ml/`) trained on the IBM AMLworld synthetic AML dataset, plus a privacy-hash engine, evaluation suite, and feature-parity tooling.

---

## Problem

Money-laundering mule accounts move stolen funds across multiple banks faster than any single institution can detect them. Each bank sees only its own slice of the transaction chain. Sharing raw customer data to fill this gap violates **SDAIA PDPL** and **SAMA** confidentiality requirements.

**The result:** coordinated fraud that spans institutions is systematically under-detected.

---

## Solution

Naseej detects the pattern locally, anonymizes it into a structural hash, and shares only the hash — so other banks gain the signal without receiving any customer data.

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

**Zero PII crosses the bank boundary.** The hash encodes only the *shape* of the fraud — degree sequences, bucketed amounts, pattern type — never the identities of the accounts involved.

---

## Key Features

| Capability | What it does |
|---|---|
| 🔐 **Zero-PII pattern hashing** | Converts a fraud topology into an `NSJ_<TYPE>_<hash>` fingerprint using SHA-256 over canonical, bucketed features. Verified by 136 automated privacy tests. |
| 🧠 **Real ML scoring** | XGBoost model trained on IBM AMLworld, served via `/api/score-transaction`, reporting honest PR-AUC / precision / recall metrics. |
| 🕸️ **Graph analytics** | Detects 8 AML typologies (fan-in velocity, rapid sweep, cross-bank pass-through, …) from local transaction graphs. |
| 🔁 **Cross-bank matching** | Bank B matches broadcast hashes against its own traffic and flags look-alikes for analyst review. |
| 🧑‍⚖️ **Human-in-the-loop cases** | Investigator dashboard with a risk queue, "Why flagged?" explanations, RBAC decision ladder, PII-guarded notes, and an append-only audit trail. |
| 🧾 **Explainability** | PII-safe "Why flagged?" attributions using SHAP (with a deterministic fallback), served for transactions, cases, and the model. |
| 🛡️ **Governance evidence** | Read-only endpoints report demo readiness, zero-PII guarantees, and honest "what is real vs simulated" statements for reviewers. |
| 🔑 **Node auth & RBAC** | Per-node API keys, sharing scopes (`local_only` / `bilateral` / `network_all` / `regulator_only`), and a role ladder (analyst → senior → MLRO). |

---

## Demo Screenshots

The live demo runs entirely in the browser. The sequence below walks through a full cross-bank mule attack — from idle banks, to detection in Bank A, to a zero-PII hash arriving at Bank B and blocking the accomplice transaction.

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="./Naseejscreenshot/Interface%20before%20running.png" alt="Naseej interface with both banks idle before the simulation runs" width="100%">
      <p align="center"><b>01 · Interface before running</b><br>Both banks process normal traffic; live API status shown in the research strip.</p>
    </td>
    <td width="50%" valign="top">
      <img src="./Naseejscreenshot/Attack%20in%20Bank%20A.png" alt="A mule attack unfolding inside Bank A" width="100%">
      <p align="center"><b>02 · Attack in Bank A</b><br>Micro-transfers fan into a mule account, followed by an international wire sweep.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="./Naseejscreenshot/Graph%20Analytics%20%26%20alert.png" alt="Bank A graph analytics raising a velocity-breach alert" width="100%">
      <p align="center"><b>03 · Graph Analytics &amp; alert</b><br>Bank A graph analytics flags the coordinated velocity breach; the mule node turns red.</p>
    </td>
    <td width="50%" valign="top">
      <img src="./Naseejscreenshot/Pattern%20Hash%20reveal.png" alt="The zero-PII pattern hash being revealed on screen" width="100%">
      <p align="center"><b>04 · Pattern Hash reveal</b><br>The detection is encoded into an <code>NSJ_*</code> zero-PII pattern hash.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="./Naseejscreenshot/Hash%20arriving%20at%20Bank%20B.png" alt="The pattern hash arriving at Bank B" width="100%">
      <p align="center"><b>05 · Hash arriving at Bank B</b><br>Only the anonymized hash crosses the boundary; Bank B matches it against its own traffic.</p>
    </td>
    <td width="50%" valign="top">
      <img src="./Naseejscreenshot/Blocked%20in%20Bank%20B.png" alt="A matching transaction being flagged and blocked in Bank B" width="100%">
      <p align="center"><b>06 · Blocked / Flagged in Bank B</b><br>Bank B flags the matching accomplice transaction for analyst review.</p>
    </td>
  </tr>
</table>

▶ **Full walkthrough:** [90-second walkthrough of Naseej MVP](./Naseejscreenshot/90-second%20walkthrough%20of%20Naseej%20MVP.mp4) *(video file in `./Naseejscreenshot/`)*

---

## Demo Flow

The live demo runs entirely in the browser. A backend connection enriches the data cards but is **not** required for the simulation.

| Stage | What you see |
|-------|-------------|
| **IDLE** | Both banks process normal transactions at 1.2s intervals |
| **ATTACK** | Click **RUN SIMULATION** — 5 micro-transfers fan into a mule account, followed by an international wire sweep |
| **DETECTED** | Bank A graph analytics flags the coordinated velocity breach; the mule node turns red |
| **BROADCASTING** | A `NSJ_*` hash typewriter-decodes on screen; particles flow Bank A → Bank B |
| **FLAGGED** | Bank B shakes and stamps FLAGGED on a matching accomplice transaction for analyst review |

Click **RESET DEMO** to restart at any point.

When the flag fires, the detection becomes an analyst case: switch to the **INVESTIGATOR** tab in the top nav to triage it — risk queue, "Why flagged?" explanation, recommended action, attributed decisions, PII-guarded notes, and the audit trail. With the backend live this runs through the real case API; offline it falls back to clearly-labelled mock cases. **The system recommends — a human decides.**

---

## Tech Stack

Only technologies actually present in the repository are listed (verified against `naseej-ai/package.json`, `backend/requirements.txt`, and the `ml/` source).

| Layer | Technologies |
|---|---|
| **Frontend** | React 18.3 · Vite 5.4 · Tailwind CSS 3.4 · Framer Motion 12 · Lucide React · PostCSS · Autoprefixer |
| **Backend** | FastAPI 0.115 · Uvicorn · Pydantic v2 · jsonschema · python-multipart · Python 3.11 |
| **ML** | XGBoost *(deployed baseline)* · LightGBM *(optional, evaluation suite)* · scikit-learn · Pandas · NumPy · NetworkX · joblib · SHAP *(optional)* |
| **Privacy** | SHA-256 · canonical JSON · value bucketing · fail-closed zero-PII guard |
| **Data** | IBM AMLworld HI-Small (synthetic AML dataset) |
| **Testing** | pytest · FastAPI TestClient · httpx |

---

## Architecture

Naseej is a three-tier prototype with an explicit **privacy boundary** between banks. Each layer is designed so that PII never leaves the bank that owns it.

```
┌──────────────────────────────────────────────────────────────┐
│  FRONTEND  ·  naseej-ai/ (React 18 + Vite)                    │
│  BankAPanel · BankBPanel · GraphView · HashDisplay ·         │
│  MLValidationCard · Investigator dashboard                    │
└───────────────────────────────┬──────────────────────────────┘
                                │  fetch → localhost:8000 (2.5s timeout)
┌───────────────────────────────▼──────────────────────────────┐
│  BACKEND  ·  backend/ (FastAPI + Uvicorn :8000)               │
│  Gates: auth → role/permissions → sharing scope →            │
│         JSON Schema → zero-PII guard → audit log              │
└───────────────────────────────┬──────────────────────────────┘
                                │  imports
┌───────────────────────────────▼──────────────────────────────┐
│  ML  ·  ml/ (Python)                                          │
│  baseline_model.joblib (XGBoost) · privacy_hash.py ·         │
│  pattern_library.py (8 detectors) · evaluation_suite.py ·    │
│  feature_contract.py · reports/*.json (served by backend)    │
└──────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility |
|---|---|
| **Frontend layer** | Browser-only demo simulation, live metric cards, and the investigator workspace. Modular structure: `config/ data/ lib/ hooks/ components/{ui,graph,panels}`. |
| **Backend layer** | FastAPI service that mediates every protected action through a fixed gate chain (auth → RBAC → sharing scope → schema → PII guard → audit). |
| **ML layer** | XGBoost baseline, 8-typology pattern library, evaluation suite (LightGBM/RF/LR comparison), and feature-contract/parity tooling. Reports are served read-only. |
| **Privacy layer** | The zero-PII guard, SHA-256 pattern hashing, value bucketing, and the hash-chained audit log — the enforcement points on the bank boundary. |
| **API layer** | Node-key authenticated endpoints for scoring, patterns, cases, features, explanations, feedback, and public governance/evidence reports (see [API Overview](#api-overview)). |

---

## Dataset

| | |
|---|---|
| **Source** | IBM / Kaggle public release |
| **Reference** | [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml) |
| **Type** | Synthetic financial transactions generated for AML research |
| **Subset used** | AMLworld **HI-Small** (~475 MB) |
| **Label** | `Is Laundering` (0/1) |

**Why synthetic data?** It enables privacy-safe MVP validation with **no real customer data**. This is deliberate for a prototype: it lets Naseej demonstrate the detection-and-sharing mechanism without touching regulated personal information.

> ⚠️ **Disclaimer:** all reported numbers are **synthetic-benchmark results** on AMLworld — they are **not** production performance and have **not** been validated on real Saudi banking data.

---

## ML Validation

Trained on AMLworld HI-Small (IBM synthetic AML dataset). **Synthetic data only — not validated on real Saudi banking transactions.**

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

**Why PR-AUC, not accuracy?** At 0.102% prevalence, accuracy is misleading — a model that flags nothing is >99.8% "accurate." PR-AUC measures the area under the precision-recall curve, the right metric when positive cases are rare and every catch matters. **Human review is required before any production blocking decision.**

### Evaluation suite findings (temporal split — separate protocol, not directly comparable)

A later evaluation phase re-ran the comparison on a **temporal** 70/15/15 split with point-in-time features. Under that protocol:

| Finding | Result |
|---|---|
| Best model by held-out PR-AUC | **LightGBM 0.612** (XGBoost 0.578, RandomForest 0.574, LogReg 0.043) |
| Feature ablation | transaction-only **0.077** → +graph **0.179** → +context **0.555** |
| Strongest typology | rapid_sweep (recall 0.76), cross_bank_pass_through (0.56) |
| Weakest typology | `mule_velocity` (recall 0.05) — heuristic label |

The context-feature ablation is the key result: **graph and point-in-time context features drive almost all detection skill.** These numbers use a different split protocol than the deployed baseline above, so they are *not directly comparable* with the 0.2275 figure — and remain synthetic-benchmark only. Typology labels are **heuristic** (inferred from a pattern library, not ground truth).

### Cross-bank experiment

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

> These results use *simulated* bank partitions of the same synthetic dataset. Real multi-bank results require independent validation.

---

## Model Governance & Advanced ML

Beyond the deployed baseline, the repository includes honest-by-design ML engineering and governance tooling. None of the below changes the deployed model — the baseline and its metrics are never overwritten.

<details>
<summary><b>Feature reconciliation — offline/online parity</b></summary>

A canonical **feature contract** reconciles the offline training features with the online feature-store features, and a **replay harness + parity checker** (four deterministic scenarios) prove they agree point-in-time:

- 8 windowed count/amount features match offline↔online exactly across all scenarios (`parity_targets_clean: true`).
- **Name collisions resolved (contract v2):** the online store emits `fan_in_normalized_1h`/`fan_out_normalized_1h`; the offline 24h integer counts keep their legacy names under canonical `fan_in_count_24h`/`fan_out_count_24h`.
- The **training manifest** approves **15** parity-clean, servable, non-memorising features and **excludes 29** — account/bank-id encodings (memorisation; `is_cross_bank` is the structural replacement), all-time cumulatives, and serve-only graph/context features.

**GNN stays blocked** until the approved set is parity-clean end to end.

</details>

<details>
<summary><b>Shadow candidate model</b></summary>

A clean-room candidate trained on **only** the 15 approved parity-clean features (no identity encodings, no serve-only or all-time features). It is a **shadow evaluation — never deployed**; `baseline_model.joblib` and `model_metrics.json` are never overwritten.

- Selected by validation PR-AUC: **XGBoost**, held-out test **PR-AUC 0.4247**, F1 0.4454.
- Below the identity-using ablation (`full_with_account_ids` 0.574) — the honest cost of excluding serve-only graph features and identity memorisation.
- **Live shadow scoring** (`POST /api/model/candidate/score-shadow`) runs the candidate beside the baseline — comparison-only; it never creates a case, blocks/approves, or affects `/api/score-transaction`.
- **Shadow monitoring** records bucketed, PII-safe observations and a prototype drift signal. The candidate is **not calibrated** and **not recommended for deployment**.

</details>

<details>
<summary><b>Analyst feedback loop</b></summary>

Closing a case turns its outcome into a bucketed, PII-safe **calibration label** (`closed_confirmed → confirmed_fraud`, etc.). Below a minimum threshold the calibration dataset returns `insufficient_labels` and **never fakes** calibration metrics. The candidate stays uncalibrated and undeployed — **calibration dataset, not production calibration**.

</details>

<details>
<summary><b>Explainability — "Why flagged?"</b></summary>

Analyst-readable, **PII-safe** explanations served by `explanation_service.py`:

- `POST /api/explain/transaction` — **SHAP** TreeExplainer on the deployed XGBoost when available; deterministic feature-importance + rule **fallback** otherwise.
- `GET /api/explain/case/{id}` — typology rationale + bucketed evidence (visibility + RBAC enforced, audited).
- `GET /api/explain/model` — evaluation-report summary (public).

Every factor shows a coarse `value_bucket` and a direction (`increases_risk` / `decreases_risk`) — **never raw amounts, account ids, or payloads**. A final PII guard scrubs the whole payload so `pii_safe` is always truthful. Explanations are **decision-support only** — not a legal/regulatory sufficiency statement — and the deployed model is not retrained.

</details>

---

## Privacy & Compliance

Naseej is **PDPL-by-design** and a **SAMA-aligned prototype**. It is **not** SAMA-certified, **not** PDPL-certified, and makes **no** guaranteed-compliance or production-ready claims — those require formal audit and certification the project has not undergone.

### Zero-PII guarantee

Every pattern hash passes the `verify_zero_pii()` check, proved by **136 automated tests**. The following are **never** included in any hash or API response:

- Personal names (name, full_name, first_name, last_name)
- Financial identifiers (IBAN, BBAN, sort code, routing number)
- Government IDs (national_id, national_number, SSN, TIN, passport, driver's licence)
- Contact details (phone, mobile, telephone, email)
- Account identifiers (account_id, from_account, to_account, src_id, dst_id)
- Digital identifiers (IP address, device ID, MAC address)
- Biometric dates (date of birth)

**Formal proof (central thesis):**

```python
# Bank A sees:  ACC_MULE_SA_001 receiving 5 inflows of ~2,400 SAR each
# Bank B sees:  SA44-2000-0001-2345 receiving 5 inflows of ~2,600 SAR each
# Same pattern, different IBANs, different amounts (same bucket)

hash_bank_a == hash_bank_b  # ← proved in TestSameTopologyDifferentPIIProducesIdenticalHash
```

### Compliance alignment

| Framework | Alignment (by-design, not certified) |
|-----------|-----------|
| SDAIA PDPL (Personal Data Protection Law) | Zero PII by design — proved by 136 tests |
| SAMA Counter-Fraud Framework | Proactive early-warning and cross-bank threat intelligence |
| Model governance | Human triage recommended; no autonomous production blocking |

---

## How to Run

### Prerequisites

- Node.js ≥ 18
- Python 3.11+
- `pip install -r backend/requirements.txt`

All commands run from the repository root.

### Frontend (demo only — no backend needed)

```bash
cd naseej-ai
npm install
npm run dev
# Opens at http://localhost:5173
```

The demo simulation runs entirely in the browser. If the backend is not running, metric cards show fallback values and an `API OFFLINE` indicator appears in the research strip.

### Backend (enriches the data cards)

```bash
# Windows PowerShell / Bash — same command
uvicorn backend.app.main:app --reload --port 8000
```

Or use the included helper scripts:

```bash
# PowerShell
.\scripts\run_backend.ps1

# Bash
bash scripts/run_backend.sh
```

**API documentation:** `http://localhost:8000/docs`

### Judge / hackathon demo

Run the frontend (and backend for live strips). Three public read-only endpoints expose the judge/demo evidence live:

```bash
curl localhost:8000/api/demo/health              # ready | partial | unavailable (+ checks, demo_safe)
curl localhost:8000/api/demo/governance-evidence # zero-PII, HITL, audit, RBAC, shadow-only, calibration
curl localhost:8000/api/demo/judge-summary       # problem/solution, real vs simulated, top differentiators
```

These carry no raw transactions, identifiers, or PII, and make **no** certified or production-ready claims — **PDPL-by-design** and **SAMA-aligned prototype** only.

### API authentication (bank-node keys, roles, partitioning)

Scoring, pattern analysis, the pattern registry, and cases require an `X-API-Key` header mapped to a registered node id. Health and read-only research stats stay public.

```bash
# Configure real keys (NODE_ID:key pairs — disables the dev keys entirely)
export NASEEJ_NODE_KEYS="NODE_A7C2F9E1:your-secret-a,NODE_B3D8E2F4:your-secret-b"
```

When `NASEEJ_NODE_KEYS` is **unset**, three clearly-labelled dev keys are active so the local demo works with zero setup: Bank A (analyst), Bank B / MLRO (`dev-key-bank-b-local-only`), and a read-only regulator (`dev-key-regulator-local-only`). The frontend sends `dev-key-bank-a-local-only` by default; override with `VITE_NASEEJ_API_KEY`.

```bash
# 401 — no key
curl -X POST localhost:8000/api/score-transaction -H "Content-Type: application/json" -d '{...}'

# 200 — local simulation
curl -X POST localhost:8000/api/score-transaction \
  -H "Content-Type: application/json" -H "X-API-Key: dev-key-bank-a-local-only" -d '{...}'
```

Every request to a protected endpoint is appended to the hash-chained audit log at `backend/data/audit/audit.jsonl` (override: `NASEEJ_AUDIT_LOG`). The registry persists to `backend/data/patterns.jsonl` and cases to `backend/data/cases.jsonl`.

### Train the baseline model (optional — model already included)

The trained model is already at `ml/models/baseline_model.joblib`. To retrain, or to run the evaluation suite and cross-bank experiment:

```bash
# Retrain the deployed baseline
python -m ml.src.train_baseline \
    --input ml/data/features/train_features.parquet \
    --output ml/models/baseline_model.joblib --sample 300000

# Cross-bank recall experiment
python -m ml.src.cross_bank_experiment

# Evaluation suite (LightGBM/RF/LR comparison, typology recall, ablation)
python -m ml.src.evaluation_suite --train-sample 800000 --seed 42
```

LightGBM is optional: if it is not installed the suite skips it with a recorded reason and reports the remaining models — results are never faked.

---

## API Overview

Public read-only endpoints serve live ML/evaluation reports (with graceful fallback). Protected endpoints require an `X-API-Key` node key. Every protected request passes the gate chain **auth → role/permissions → sharing scope → JSON Schema → zero-PII guard → audit log**.

| Group | Endpoint | Auth | Description |
|---|---|:---:|---|
| **Model & evaluation** | `GET /api/model/metrics` | public | XGBoost test metrics |
| | `GET /api/model/comparison` | public | LightGBM vs XGBoost vs RF vs LR |
| | `GET /api/model/per-typology-recall` | public | Recall by AML typology (heuristic labels) |
| | `GET /api/model/threshold-analysis` | public | Operating points |
| | `GET /api/model/ablation-report` | public | Feature ablation |
| | `GET /api/model/feature-contract` · `feature-parity` · `training-feature-manifest` | public | Offline/online reconciliation reports |
| **Shadow candidate** | `GET /api/model/candidate/*` | public | Shadow candidate reports (metrics, comparison, …) |
| | `POST /api/model/candidate/score-shadow` | node key | Candidate vs baseline — comparison only |
| | `GET /api/model/candidate/shadow-monitoring` | node key | Node-scoped aggregates + prototype drift |
| | `GET /api/model/candidate/calibration-readiness` · `calibration-status` | public | States: not calibrated, no deploy |
| **Scoring & patterns** | `POST /api/score-transaction` | node key | XGBoost inference |
| | `POST /api/analyze-pattern` | node key | Patterns + privacy hash |
| | `POST /api/patterns` · `GET /api/patterns[/{id}]` | node key | Register / query the threat-pattern registry |
| **Cases** | `POST /api/cases/from-pattern/{id}` | node key | Open an analyst case |
| | `GET/PATCH/POST /api/cases/...` | node key | Case lifecycle, notes, decisions |
| **Features** | `POST /api/features/ingest-transaction` | node key | Feed node-local velocity windows |
| | `GET /api/features/account/{id}` | node key | Velocity/graph features |
| | `POST /api/features/score-with-context` | node key | Baseline model + transparent rule layer |
| **Explainability** | `POST /api/explain/transaction` | node key | "Why flagged?" (SHAP / fallback) |
| | `GET /api/explain/case/{id}` | node key | Case explanation |
| | `GET /api/explain/model` | public | Model evidence summary |
| **Feedback** | `POST /api/feedback/from-case/{id}` | node key | Closed-case → PII-safe calibration label |
| | `GET /api/feedback[/calibration-dataset]` | node key | Node-scoped labels |
| **Demo / governance** | `GET /api/demo/health` · `governance-evidence` · `judge-summary` | public | Readiness, evidence, judge brief |
| | `GET /api/cross-bank/results` | public | 4-bank experiment |
| **Auth** | `GET /api/auth/whoami` | node key | Node, role, permissions |

---

## Tests

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
python -m pytest backend/tests/test_feature_store.py -v    # velocity windows + node isolation
```

---

## Limitations

1. **Model not retrained on context features.** A node-local feature store now computes real rolling 1h/24h velocity, counterparty, and graph-window features, and `/api/features/score-with-context` layers a transparent rule adjustment over the baseline score — but the XGBoost model itself has **not** been retrained on these features yet (every response states `model_retrained_on_context: false`). The legacy `/api/score-transaction` path still scores without history.
2. **Synthetic data only.** AMLworld is a research benchmark, not real banking data. Out-of-time validation on real Saudi transactions is required before any production deployment.
3. **Simulated federation.** The cross-bank broadcast is a frontend animation. Production requires a secure aggregation layer with PKI.
4. **Single-factor auth only.** Protected endpoints require per-node API keys and access is partitioned per node profile, but it is one credential per node — analyst roles are selected within a server-configured envelope, not issued per person. No mTLS, key rotation, rate limiting, or replay protection yet.
5. **Fixed bucketing.** Bucket boundaries are hardcoded. Changing them invalidates all existing hashes.

---

## Roadmap

| Horizon | Key additions |
|---------|--------------|
| Post-hackathon | ~~Feature store for velocity features~~ (done) · retrain on context features · SHAP explainability · GNN baseline |
| Pilot prototype | Out-of-time validation · Analyst case management UI · Configurable thresholds |
| Controlled pilot | Tokenised real data · Federated learning (Flower) · Differential privacy |
| Production path | SAMA sandbox · Multi-bank PKI · Streaming pipeline · Model governance |

---

## Team

**Team Madar | فريق مدار** — AMAD Hackathon · FinTech Track

| Member | Role |
|---|---|
| **OBAID ALMUTAIRI** | Founder & Product Lead |
| **AMAL ALMUTAIRI** | AI / Data Lead |
| **SADEEM ALMUTAIRI** | UI/UX Designer |
| **ASEEL ALMUTAIRI** | Full-Stack Developer |
| **ABDULLMALIK ALMUTAIRI** | Business & Partnerships Lead |

*A team combining product, AI, design, engineering, and partnerships.*

---

## References & Dataset Source

- **Dataset** — [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml) (IBM / Kaggle public release; AMLworld HI-Small subset used).
- Erik Altman, Jovan Blanuša, Luc von Niederhäusern, Béni Egressy, Andreea Anghel, and Kubilay Atasu, *"Realistic Synthetic Financial Transactions for Anti-Money Laundering Models"* (AMLworld / IBM, NeurIPS 2022).
- Malik Ashfaq Ur Rahman, *AI-Driven Fraud Detection and Financial Security Framework for Saudi Banking Systems* (May 2026).
- McMahan et al., *"Communication-Efficient Learning of Deep Networks from Decentralized Data"* (Google AI, 2017) — Federated Learning.

---

## License & Prototype Disclaimer

*Research prototype. Production deployment would require SAMA supervision, adversarial robustness testing, real cryptographic federation, per-analyst credentials, and independent validation on real banking data.* Naseej is **not** certified, **not** production-ready, and trained on **synthetic data only**.
