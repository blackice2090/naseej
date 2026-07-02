# Naseej — Implementation Audit (Phase 0)

**Date:** 2026-05-19
**Phase:** 0 — Project Audit and Safety Check (read-only)
**Status:** Audit complete. No source files modified. Existing demo untouched.

This document is the safety baseline for the multi-phase upgrade of نسيج | Naseej from a frontend-only rule-based simulation into a research-backed AML prototype (inspired by the AMLworld / IBM "Realistic Synthetic Financial Transactions" paper). It captures the repository's state **before** any Phase 1+ work begins, so later phases can be verified against it.

---

## 1. Repository tree (current)

Top-level of `C:\Users\acer32\Downloads\Naseej\`:

```
Naseej/
├── 1717703.pdf                  # source research paper (AMLworld / synthetic AML)
├── PRD.md                       # product requirements doc
├── README.md                    # current public README (already branded نسيج | Naseej)
├── References.md                # academic / market references
├── package-lock.json            # stub (85 bytes) — actual app lockfile lives under naseej-ai/
├── docs/
│   ├── dataset_plan.md
│   ├── JUDGES_BRIEF.md
│   ├── NASEEJ_DEMO_PRESENTATION.md
│   └── superpowers/             # tooling artifacts (skills)
├── ml/
│   ├── data/
│   │   ├── raw/HI-Small_Trans.csv          # 475 MB — AMLworld HI-Small split
│   │   ├── processed/{train,val,test}.parquet  # ~165 MB total
│   │   └── features/{train,val,test}_features.parquet  # ~290 MB total
│   ├── models/
│   │   ├── baseline_model.pkl              # 2 MB, trained XGBoost (per threshold file)
│   │   ├── baseline_threshold.json
│   │   ├── feature_importance.csv
│   │   ├── metrics.json
│   │   ├── model_comparison.md
│   │   ├── full_features/                  # ablation artifacts
│   │   └── no_account_id/                  # ablation artifacts
│   ├── notebooks/                          # (empty placeholder)
│   └── scripts/
│       ├── load_data.py                    # ~3.7 KB
│       ├── build_graph_features.py         # ~26 KB
│       ├── train_baseline.py               # ~33 KB
│       └── evaluate_model.py               # ~4 KB
└── naseej-ai/                              # frontend app (working demo)
    ├── index.html
    ├── package.json
    ├── package-lock.json
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── vite.config.js
    ├── README.md
    ├── node_modules/                       # already installed
    └── src/
        ├── App.jsx                         # ~40 KB single-file UI
        ├── main.jsx
        └── index.css
```

---

## 2. Frontend flow (current — DO NOT BREAK)

App: `naseej-ai/` — React 18.3 + Vite 5.4 + Tailwind 3.4 + framer-motion 12 + lucide-react.

Run command:
```bash
cd naseej-ai
npm run dev      # vite dev server, typically http://localhost:5173
```

State machine in `naseej-ai/src/App.jsx`:

```
STAGES = { IDLE: 0, ATTACK: 1, DETECTED: 2, BROADCASTING: 3, BLOCKED: 4 }
```

Sequence on "RUN SIMULATION":
1. **IDLE** — Bank A and Bank B process normal transactions (`TX_POOL_A`, `TX_POOL_B`).
2. **ATTACK** — Five micro-transfers from `0xSRC_A1..A5 → 0xMULE_01`, then sweep to `0xINTL_DEST` (`ATTACK_SEQUENCE` constant).
3. **DETECTED** — Bank A graph analytics flags mule velocity pattern.
4. **BROADCASTING** — Hash `0x8F9B2C_NASEEJ_PATTERN` (constant `THREAT_HASH`) propagates via federated log (`FEDERATED_LOG`).
5. **BLOCKED** — Bank B blocks `TX#ACC_01` (`ACCOMPLICE_TX`).

Branding is already correct: "نسيج | Naseej" — no MuleHunter.AI references found in the current App.jsx. (Phase 8's rebranding step is therefore mostly a no-op for this file.)

---

## 3. ML assets already present

The master prompt assumed ML work would start from scratch. It will not — there is a working baseline pipeline in `ml/scripts/` with trained artefacts:

**Model (from `ml/models/metrics.json`, test split):**
| Metric | Value |
|---|---|
| Model type | XGBoost (per `baseline_threshold.json`) |
| Threshold | 0.99400 |
| PR-AUC | 0.4271 |
| ROC-AUC | 0.9856 |
| Precision | 0.5953 |
| Recall | 0.3578 |
| F1 | 0.4469 |
| Confusion matrix | [[760785, 189], [499, 278]] |
| Laundering prevalence | 0.00102 (≈0.1%) |

**Dataset:** AMLworld HI-Small split (`HI-Small_Trans.csv`, 475 MB). Already preprocessed into parquet train/val/test in `ml/data/processed/`, and feature-engineered tables in `ml/data/features/`.

**Existing scripts (`ml/scripts/`):**
- `load_data.py` — ingestion + split.
- `build_graph_features.py` — graph feature engineering (already 26 KB).
- `train_baseline.py` — model training (already 33 KB).
- `evaluate_model.py` — evaluation harness.

These will be **kept in place**. Phase 2–4 will add new modules under `ml/src/` (new directory) rather than overwriting `ml/scripts/`.

---

## 4. Documentation already present

| File | Purpose |
|---|---|
| `README.md` | Public-facing overview, run instructions, compliance, academic foundation. Already branded نسيج \| Naseej. |
| `PRD.md` | Product requirements doc. |
| `References.md` | Academic + market references. |
| `docs/dataset_plan.md` | Dataset selection / preparation plan. |
| `docs/JUDGES_BRIEF.md` | Judge-facing brief (existing). |
| `docs/NASEEJ_DEMO_PRESENTATION.md` | Demo narrative (existing). |
| `1717703.pdf` | Source research paper (AMLworld / synthetic AML transactions). |

---

## 5. Current limitations

Honest list of gaps the upgrade is meant to close:

- No backend service. Frontend has no API to read.
- Frontend metrics are hard-coded constants; the real `metrics.json` is not surfaced in the UI.
- No cross-bank experiment script (private-only vs shared-model vs pattern-sharing comparison).
- No privacy-preserving pattern-hash module — the visible "hash" is the hard-coded constant `0x8F9B2C_NASEEJ_PATTERN`.
- No pattern library (fan-in/fan-out/cycle/scatter-gather detectors).
- No tests anywhere (no `backend/tests/`, no `ml/tests/`).
- No `requirements.txt` pinning Python deps; environment is implicit.
- Dataset preparation is not exposed via a single CLI (`prepare_dataset.py`).
- Demo claims (zero-PII federated network) are visual only — not yet backed by a hash function whose zero-PII property is unit-tested.

---

## 6. Files that will be MODIFIED in later phases

Only **additive** edits — never rewrites:

| File | Phase | Change |
|---|---|---|
| `naseej-ai/src/App.jsx` | 8 | Append new cards (Model Validation, Dataset Evidence, Cross-Bank, Pattern Library, Explainability). Do not alter existing IDLE→BLOCKED flow. |
| `README.md` | 10 | Expand with backend, ML pipeline, training, and zero-PII sections. |
| `naseej-ai/package.json` | 8 (maybe) | Possibly add a small fetch helper dep if needed — prefer plain `fetch` to avoid this. |

---

## 7. Files / directories that will be ADDED in later phases

Mapped to phases. None of these exist today.

**Phase 1 — backend + ML workspace scaffolding**
- `backend/app/main.py`
- `backend/app/api/{routes_health,routes_model,routes_graph,routes_demo}.py`
- `backend/app/core/{config,schemas}.py`
- `backend/app/services/{model_service,graph_service,privacy_service,demo_service}.py`
- `backend/requirements.txt`
- `ml/src/{data_loader,preprocessing,graph_features,pattern_library,train_baseline,evaluate,cross_bank_experiment,privacy_hash}.py`
- `ml/src/prepare_dataset.py`
- `ml/README.md`
- `scripts/{run_backend.sh,run_frontend.sh,run_training.sh}`
- `docs/ML_ROADMAP.md`
- `docs/DATASET_GUIDE.md`

**Phase 4 — baseline training (new outputs alongside existing `.pkl`)**
- `ml/models/baseline_model.joblib` (new — does not overwrite `baseline_model.pkl`)
- `ml/reports/{model_metrics.json,confusion_matrix.json,feature_importance.json,training_summary.md}`

**Phase 5 — cross-bank experiment**
- `ml/reports/{cross_bank_results.json,cross_bank_summary.md}`

**Phase 9 — tests**
- `backend/tests/{test_health,test_privacy_hash,test_model_api}.py`
- `ml/tests/{test_data_loader,test_graph_features,test_pattern_library,test_privacy_hash}.py`

**Phase 10 — documentation**
- `docs/DEMO_SCRIPT_RESEARCH_VERSION.md`
- `docs/TECHNICAL_ARCHITECTURE.md`

---

## 8. Safety contract for Phase 1+

Binding rules for every subsequent phase:

1. **Frontend off-limits until Phase 8.** Do not edit `naseej-ai/src/App.jsx`, `main.jsx`, `index.css`, `index.html`, `package.json`, `vite.config.js`, `tailwind.config.js`, or `postcss.config.js` before Phase 8.
2. **Existing ML artefacts are read-only.** Do not overwrite or delete:
   - `ml/data/raw/HI-Small_Trans.csv`
   - `ml/data/processed/*.parquet`
   - `ml/data/features/*.parquet`
   - `ml/models/baseline_model.pkl` (the new Phase 4 model goes to `baseline_model.joblib`)
   - `ml/models/{baseline_threshold.json,feature_importance.csv,metrics.json,model_comparison.md}`
   - Anything under `ml/scripts/`
3. **New ML code lives in `ml/src/`** (new directory), not `ml/scripts/`. The old scripts remain as reference and continue to work.
4. **No destructive operations** without explicit user confirmation — no `rm -rf`, no `git reset --hard`, no force-push, no dependency removals.
5. **Zero-PII contract.** Any pattern-sharing payload generated by `privacy_hash.py` / `privacy_service.py` must be unit-tested to prove it contains no raw account IDs, IBANs, names, emails, or phone numbers.
6. **Backend must degrade gracefully.** Every endpoint must return safe fallback JSON when its underlying report file is missing, so the frontend never breaks the demo.
7. **Honest claims only.** Use "research prototype" / "hackathon MVP" wording; do not claim production banking readiness.

---

## 9. Acceptance check for Phase 0

- [x] `docs/IMPLEMENTATION_AUDIT.md` exists (this file) and is non-empty.
- [x] No other file in the repo was modified during Phase 0.
- [ ] **Manual user step:** confirm the demo still runs.
  ```bash
  cd naseej-ai
  npm run dev
  # Open http://localhost:5173, click RUN SIMULATION, verify IDLE → ATTACK → DETECTED → BROADCASTING → BLOCKED.
  ```

Once that last box is ticked by the user, Phase 0 is closed and Phase 1 (backend + ML workspace scaffolding) can begin.
