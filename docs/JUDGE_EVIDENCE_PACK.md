# Naseej — Judge Evidence Pack

**نسيج | Naseej — privacy-preserving cross-bank AML & fraud intelligence.**
Research prototype · synthetic AMLworld data · **not production validation.**
PDPL-by-design · SAMA-aligned prototype · **not certified, not production-ready.**

A consolidated, checkable summary of what Naseej is, what's real, and what is
explicitly *not* claimed. Live counterparts:
`GET /api/demo/health`, `/api/demo/governance-evidence`, `/api/demo/judge-summary`.

---

## 1. Architecture summary

```
React/Vite demo (naseej-ai/)  ──HTTP──>  FastAPI backend (backend/)  ──imports──>  ml/
  · Demo + Investigator views             · auth → RBAC → PII guard → audit          · XGBoost baseline
  · governance/evidence strips            · case status machine (HITL)               · feature contract + parity
  · offline-safe fallbacks                · feature store (node-local windows)        · evaluation suite + reports
                                          · shadow scoring + monitoring + feedback    · privacy hash engine
```

- **Frontend** never blocks on the backend; offline → labelled fallbacks.
- **Backend** is the system of record; every protected call is authenticated,
  RBAC-checked, PII-guarded, and audited.
- **ml/** holds the real model, the feature contract, and all evaluation reports.

## 2. Endpoints summary (selected)

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | public | liveness |
| `POST /api/score-transaction` | node key | deployed XGBoost inference (unchanged) |
| `POST /api/analyze-pattern` | node key | typology detection + zero-PII hash |
| `POST /api/patterns`, `GET /api/patterns[/{id}]` | node key | threat-pattern registry (schema + PII gates) |
| `POST /api/cases/from-pattern/{id}`, `GET/PATCH/POST /api/cases/*` | node key, RBAC | human-in-the-loop case lifecycle |
| `GET /api/explain/{transaction,case/{id},model}` | node key / public | PII-safe "Why flagged?" (SHAP/fallback) |
| `GET /api/model/{metrics,comparison,…,feature-contract,feature-parity,training-feature-manifest}` | public | ML evaluation + reconciliation reports |
| `POST /api/model/candidate/score-shadow` | node key | shadow candidate vs baseline (comparison-only) |
| `GET /api/model/candidate/{metrics,…,shadow-monitoring,calibration-status}` | public / node key | candidate evidence + monitoring |
| `POST /api/feedback/from-case/{id}`, `GET /api/feedback[/calibration-dataset]` | node key | analyst feedback → calibration labels |
| `GET /api/demo/{health,governance-evidence,judge-summary}` | public | this evidence pack, live |

## 3. Test count

**565 tests pass** (`python -m pytest backend/tests ml/tests`). Frontend build
passes (`cd naseej-ai && npm run build`).

## 4. What is real

- Real **XGBoost** model + PR-AUC-primary evaluation on AMLworld (LightGBM
  comparison, per-typology recall, context ablation).
- Real **zero-PII guard** (fail-closed), **hash-chained audit log** (tamper-
  evident), **node-scoped RBAC**, **case status machine** (HITL, role-gated).
- Real **SHAP/fallback explanations** resolving through the feature contract,
  bucketed and PII-safe.
- Real **offline/online feature contract + parity harness** (4 scenarios),
  **shadow scoring**, **shadow monitoring + prototype drift**, and the
  **analyst feedback → calibration dataset** loop.

## 5. What is simulated

- The **2-node pattern network** and cross-bank exchange (single process,
  synthetic bank partitions).
- **Transactions and accounts** (AMLworld synthetic; zero real PII).
- **Demo case creation when offline** (clearly labelled mock).

## 6. Privacy guarantees

- Only `NSJ_*` pattern hashes and bucketed aggregates cross the node boundary.
- The PII guard rejects names, IBANs, account ids, phones, emails, long digit
  runs, demo-style handles, and (v1) Arabic free text — fail-closed.
- Explanations, shadow observations, and feedback labels store **buckets only**,
  never raw values or identifiers; a guard re-checks each store before write.
- Audit records carry metadata only — never transactions or feature values.

## 7. Security / RBAC summary

- Per-node API keys; identity resolved server-side (`/api/auth/whoami`).
- Cases/patterns/feedback are node-scoped; cross-node access is an audited
  generic 403. Regulator/admin aggregate-all only via `cases:view_all`.
- Role ladder: analyst → senior_analyst → MLRO; confirm-fraud requires MLRO.
- Hash-chained audit log; `verify_chain()` detects tampering.

## 8. ML honesty summary

- PR-AUC is primary; **accuracy is never reported** (~0.1% prevalence).
- Account/bank-identity encodings are **excluded** from training (memorisation
  risk); `is_cross_bank` is the structural replacement.
- Offline/online feature parity is **measured and gated**, not assumed.
- The candidate (15 approved features, test PR-AUC 0.4247) is **shadow-only and
  NOT deployed**; the deployed baseline is unchanged.

## 9. Explainability summary

- "Why flagged?" answers for transactions, cases, and the model.
- SHAP TreeExplainer when available; deterministic feature/rule fallback
  otherwise — the method is labelled in every response.
- Bucketed values only; decision-support, **not** a legal sufficiency statement.

## 10. Feedback / calibration summary

- Closed-case outcomes → PII-safe, node-scoped calibration labels.
- `calibration-dataset` returns `insufficient_labels` below a threshold and
  **never fakes** metrics; any proxies are clearly prototype.
- The candidate is **not calibrated for production**.

## 11. Limitations

- Synthetic data only; no out-of-time validation; not certified; not production-ready.
- Pattern network simulated (2 local nodes), not a live inter-bank deployment.
- Audit log tamper-evident, not tamper-proof; key management prototype-grade.
- PII guard is shape/keyword based (English-only free text in v1).
- GNN and federated learning have not started; sharing is pattern-hash exchange.

## 12. Suggested judge Q&A

- **"Production-ready?"** → No — research prototype on synthetic data, explicit.
- **"SAMA/PDPL certified?"** → No. PDPL-by-design and SAMA-aligned prototype only.
- **"Federated learning?"** → No — we share pattern hashes, not gradients.
- **"Did you deploy the new model?"** → No — shadow-only; baseline unchanged.
- **"How is PII protected?"** → Fail-closed guard + tested zero-PII hashes;
  bucketed everything; see `/api/demo/governance-evidence`.
- **"What's genuinely novel?"** → Zero-PII cross-bank intelligence + honest,
  gated ML + human-in-the-loop governance with a tamper-evident audit trail.
- **"What would it take to deploy?"** → Real labeled out-of-time data under SAMA
  governance, calibration, live-scale parity, drift monitoring, and sign-off.
