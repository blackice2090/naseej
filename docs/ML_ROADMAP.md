# Fraud Intelligence Model Roadmap — نسيج | Naseej

The path from rule-based demo to governed ML. A research prototype, not a
production banking system — each phase states what is real today vs. planned.

| Phase | Theme | Status |
|---|---|---|
| 1 | Rule-based simulation + graph features | ✅ done |
| 2 | Synthetic AML dataset experiments | ✅ done |
| 3 | Gradient-boosted baseline with graph features | ✅ done (XGBoost) |
| 3.5 | Serving-time feature store + contextual scoring | 🟨 prototype |
| 3.7 | LightGBM comparison + per-typology recall + context ablation | ✅ done |
| 3.8 | Explainable AI / SHAP "Why flagged?" engine | ✅ done |
| 3.9 | Offline/online feature reconciliation + training contract | ✅ done |
| 3.9c | Shadow candidate retrain (approved features only, NOT deployed) | ✅ done |
| 3.9d | Live shadow scoring endpoint (comparison-only) | ✅ done |
| 3.9e | Shadow monitoring + calibration + drift dashboard (aggregate/bucketed) | ✅ done |
| 3.9f | Analyst feedback loop + calibration dataset builder | ✅ done |
| 3.9g | Demo readiness + governance evidence pack | ✅ done |
| 4 | GNN experiments for transaction graph classification | ⬜ planned (**blocked on full feature parity**) |
| 5 | Federated learning simulation | ⬜ planned |
| 6 | Privacy-preserving topology sharing | 🟨 prototype |
| 7 | Model governance, drift, explainability, human review | ⬜ planned |

---

## Phase 1 — Rule-based simulation and graph features ✅

- 8 deterministic AML typology detectors in `ml/src/pattern_library.py`:
  fan-in, fan-out, simple cycle, mule velocity, rapid sweep,
  cross-bank pass-through, scatter-gather, gather-scatter.
- Graph features per transaction in `ml/src/graph_features.py` /
  `ml/scripts/build_graph_features.py`: in/out degree, cumulative flow,
  rolling 1h/24h velocity, unique counterparties, cross-bank flag,
  fan-in/out scores, time-of-day.
- The browser demo replays a fan-in + sweep typology through this logic.

## Phase 2 — Synthetic AML dataset experiments ✅

- Dataset: AMLworld HI-Small (IBM, NeurIPS) — ~475 MB synthetic
  transactions at `ml/data/raw/`, 0.10% laundering prevalence.
- Pipeline: `ml/src/prepare_dataset.py` → temporal 70/15/15 split →
  feature parquet at `ml/data/features/`.
- **Honesty note:** synthetic benchmark only. No claim transfers to real
  Saudi banking data without out-of-time validation under SAMA supervision.

## Phase 3 — Gradient-boosted baseline with graph features ✅

- Compared logistic regression, random forest, XGBoost
  (`ml/src/train_baseline.py`); XGBoost selected on validation PR-AUC.
- Test metrics (in `ml/reports/model_metrics.json`, served live by the
  backend): PR-AUC 0.2275, ROC-AUC 0.952, precision 27.3% / recall 19.6%
  at the F1-optimised threshold, FPR 0.05%.
- PR-AUC is the primary metric at 0.1% prevalence; accuracy is deliberately
  not reported.

## Phase 3.7 — LightGBM comparison + per-typology recall + context ablation ✅

- Offline evaluation suite (`ml/src/evaluation_suite.py`) on a **temporal**
  70/15/15 split with point-in-time features; outputs four report pairs under
  `ml/reports/` served read-only at `/api/model/comparison`,
  `/per-typology-recall`, `/threshold-analysis`, `/ablation-report`.
  Full details in [`MODEL_EVALUATION.md`](MODEL_EVALUATION.md).
- **LightGBM beats XGBoost** on held-out PR-AUC (0.612 vs 0.578); logistic
  regression collapses (0.043). LightGBM is an *optional* competitor — if the
  dependency is missing it is skipped with a recorded reason, never faked.
- **Context ablation is the headline:** transaction-only PR-AUC 0.077 →
  +graph 0.179 → +context 0.555. Graph and point-in-time context features
  drive almost all detection skill; the extra account-id lift (+0.019) is
  flagged as identity memorisation.
- **Per-typology recall** (heuristic labels from the pattern library, not
  ground truth): strong on cross-bank pass-through (0.56) and rapid-sweep
  (0.76); weakest on `mule_velocity` (0.05) — a concrete target for Phase 4.
- **Honesty:** synthetic benchmark, temporal-split protocol distinct from and
  not directly comparable with the deployed `model_metrics.json`; the suite
  never overwrites the deployed model or its metrics.

## Phase 3.5 — Serving-time feature store + contextual scoring 🟨

- **Prototype exists** ([`FEATURE_STORE.md`](FEATURE_STORE.md)): a
  node-scoped in-memory feature store computes rolling 1h/24h velocity,
  counterparty-newness and graph-window features (21-feature catalogue
  mirroring the Phase 1 train-time definitions) from locally ingested
  pseudonymous transactions. This addresses the documented
  single-transaction limitation of Phase 3 serving.
- `POST /api/features/score-with-context` = baseline XGBoost score + a
  **deterministic, capped rule layer** with per-rule explanations.
  **Honesty contract:** the response always carries
  `model_retrained_on_context: false` — the model has not been retrained,
  and no endpoint claims otherwise.
- Remaining before retraining on these features (gates, in order):
  1. point-in-time recomputation of the catalogue features over the
     training set (no lookahead bias);
  2. per-feature leakage audit against the label;
  3. re-run the temporal split + threshold selection, publish new
     `ml/reports/*`, and sync the frontend fallback metrics
     (honest-copy rule);
  4. ablation showing PR-AUC gain over the Phase 3 baseline;
  5. bias evaluation of newness/velocity features (new customers,
     bursty-but-legitimate accounts).

## Phase 3.8 — Explainable AI / SHAP "Why flagged?" engine ✅

- PII-safe analyst explanations ([`EXPLAINABILITY.md`](EXPLAINABILITY.md)):
  SHAP TreeExplainer on the deployed XGBoost when available, deterministic
  feature-importance + rule fallback otherwise. Endpoints
  `/api/explain/{transaction,case/{id},model}`; bucketed values only.
- The deployed model is not retrained; explanations are decision-support, not
  a legal sufficiency statement.

## Phase 3.9 — Offline/online feature reconciliation + training contract ✅

- Canonical feature contract ([`FEATURE_CONTRACT.md`](FEATURE_CONTRACT.md),
  `ml/src/feature_contract.py` → `ml/features/feature_contract.json`) reconciles
  every offline training feature with the online feature-store feature: names,
  definitions, windows, and a `parity_status` per feature.
- Parity checker + deterministic replay harness
  (`ml/src/feature_parity_check.py`): the eight windowed count/amount features
  match offline↔online point-in-time; the `fan_in_score`/`fan_out_score` name
  **collisions**, all-time cumulatives, and account/bank-id encodings are flagged.
- Training manifest approves **15** parity-clean, servable, non-memorising
  features and **excludes 29** (incl. all account/bank-id encodings).
- Served read-only at `/api/model/{feature-contract,feature-parity,training-feature-manifest}`.
- Explanations now resolve labels/buckets/limitations through the contract.

## Phase 3.9b — Feature Reconciliation Fix Sprint ✅ (contract v2)

- **Name collisions resolved:** the online store now emits
  `fan_in_normalized_1h` / `fan_out_normalized_1h`; the offline 24h integer
  counts keep their legacy column names under canonical `fan_in_count_24h` /
  `fan_out_count_24h`. The contract self-checks `collisions_resolved: true` — no
  bare feature name maps to two different canonical meanings.
- **Replay harness expanded to four deterministic scenarios** (fan-in→sweep,
  fan-out dispersion, cross-bank pass-through, quiet legitimate); all eight
  windowed parity-targets match point-in-time in every scenario.
- **Serve-only features** kept serving-only by explicit decision (B): no offline
  point-in-time equivalent; rule-layer/explanation use only, never training.
- **All-time cumulatives** kept excluded — a 30d online equivalent was NOT built
  (the store's 25h horizon can't hold 30 days without a retention/memory change).
- **Account/bank encodings** permanently excluded; `is_cross_bank` is the
  approved structural replacement. Only the 4 encodings remain `definition_mismatch`.

## Phase 3.9c — Shadow candidate retrain ✅ (NOT deployed)

- `ml/src/train_candidate_model.py` trains on ONLY the 15 approved features;
  selected XGBoost, test PR-AUC 0.4247. Never overwrites the deployed bundle or
  `model_metrics.json`. See [`CANDIDATE_MODEL.md`](CANDIDATE_MODEL.md).

## Phase 3.9d — Live shadow scoring + candidate monitoring ✅ (comparison-only)

- `POST /api/model/candidate/score-shadow` (node auth, PII guard, audited) runs
  the candidate beside the deployed baseline on the online feature path and
  returns candidate vs baseline score + agreement. **Comparison-only:** it never
  creates a case, blocks/approves, or affects `/api/score-transaction`.
- Candidate is OPTIONAL: missing artifact → safe `candidate_unavailable`; no
  node window history / unparseable timestamp → `missing_feature`, not scored.
- Feature vector is exactly the 15 approved features (identity/bank encodings,
  all-time, account-pair, serve-only are hard-blocked).
- Readiness report `candidate_shadow_readiness.{json,md}`; a small
  comparison row appears in the demo's Candidate Model card.
- The deployed model, `/api/score-transaction`, and `/api/explain/*` are unchanged.

## Phase 3.9e — Shadow monitoring + calibration + drift ✅ (aggregate/bucketed)

- Bucketed, PII-safe shadow observations (`shadow_monitoring_service.py`,
  JSONL at `NASEEJ_SHADOW_OBSERVATIONS_PATH`) — no raw transactions/identifiers/
  feature values; a PII guard double-checks every write. See
  [`SHADOW_MONITORING.md`](SHADOW_MONITORING.md).
- `GET /api/model/candidate/shadow-monitoring` (node auth, node-scoped; cross-node
  needs `cases:view_all`) returns last-1h/24h/all aggregates + a prototype drift
  signal (normal/watch/unavailable).
- `GET /api/model/candidate/calibration-readiness` (public) states the candidate
  is NOT calibrated, no real labels in shadow mode, no deployment recommendation.
- Small "Shadow Monitoring" row in the demo (agreement / candidate-alert /
  missing-feature rates + drift) labelled PROTOTYPE MONITORING — NO DEPLOYMENT
  DECISION; hidden when there are no observations.

## Phase 3.9f — Analyst feedback loop + calibration dataset ✅ (NOT production calibration)

- Closed-case outcomes become bucketed, PII-safe calibration labels
  (`feedback_service.py`, append-only JSONL at `NASEEJ_FEEDBACK_LABELS_PATH`).
  See [`ANALYST_FEEDBACK_LOOP.md`](ANALYST_FEEDBACK_LOOP.md).
- `POST /api/feedback/from-case/{id}` (closed cases only; 409 otherwise;
  visibility/RBAC enforced), `GET /api/feedback` + `/api/feedback/calibration-dataset`
  (node-scoped), `GET /api/model/candidate/calibration-status` (public, enum only).
- Calibration proxies computed only above a label threshold (default 30) and
  clearly labelled prototype; below threshold → `insufficient_labels`, never faked.
- Feedback auto-captured on case closure in the demo; Shadow Monitoring row adds
  labeled-count + calibration status (CALIBRATION DATASET — NOT PRODUCTION CALIBRATION).
- The deployed model, `/api/score-transaction`, `/api/explain/*`, and case
  management are unchanged; no cases are created by feedback endpoints.

## Phase 3.9g — Demo readiness + governance evidence pack ✅ (no behaviour change)

- `demo_evidence_service.py` consolidates proof points into three public
  read-only endpoints: `GET /api/demo/health` (12-point readiness check →
  ready/partial/unavailable, `demo_safe`, `production_ready:false`),
  `/api/demo/governance-evidence` (9 evidence items, each with what-it-proves +
  limitation + allowed-claim), `/api/demo/judge-summary` (problem/solution,
  real vs simulated, top-5 differentiators, demo flow).
- Honesty enforced: PDPL-by-design + SAMA-aligned prototype only; never
  certified/production-ready (tested — no affirmative overclaims).
- Compact **Governance Evidence** strip in the demo; speakable
  [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) + [`JUDGE_EVIDENCE_PACK.md`](JUDGE_EVIDENCE_PACK.md).
- No scoring/ML behaviour changed; baseline + candidate untouched.

## Phase 4 — GNN experiments ⬜ (blocked on full feature parity)

- Goal: beat the boosted baseline PR-AUC by classifying transaction
  *subgraphs* rather than feature-vector rows.
- **Motivation from Phase 3.7:** per-typology recall showed the boosted model
  is weakest on `mule_velocity` and on unmatched laundering — multi-hop
  temporal patterns that flat per-transaction features approximate poorly.
- **Why still blocked (Phase 3.9/3.9b gate):** the name collisions are now
  resolved and the eight windowed features are parity-clean, but full
  offline/online parity still does NOT exist — the all-time cumulatives have no
  servable twin (kept excluded, not back-filled) and the serve-only graph/context
  features have no offline twin, so the trainable+servable set is the 15 tabular
  features only. A GNN also needs a leakage-audited temporal graph (no edges from
  the future). Until a richer approved set is parity-clean end to end
  (FEATURE_CONTRACT.md §7), a GNN comparison would not be trustworthy. The
  training manifest is the gating checklist.
- Gate: a GNN must beat the boosted baseline on PR-AUC **and** stay
  explainable enough for analyst review (subgraph attribution), or it
  stays a research track.

## Phase 5 — Federated learning simulation ⬜

- Simulate N bank nodes (partition AMLworld by bank id, as the cross-bank
  experiment already does) training a shared model without pooling rows —
  Flower or OpenFL.
- Measure: federated recall vs. private-only and vs. centralized pooling;
  communication cost; behavior under non-IID bank distributions.
- The existing cross-bank experiment (`ml/src/cross_bank_experiment.py`)
  is the control: pattern-hash sharing already reaches 66.7% avg recall vs
  38.9% private-only on the synthetic partition.

## Phase 6 — Privacy-preserving topology sharing 🟨

- **Prototype exists:** deterministic `NSJ_*` hashes over normalized,
  bucketed topology (`ml/src/privacy_hash.py`), zero-PII proved by 136
  tests; contract in [`THREAT_PATTERN_CONTRACT.md`](THREAT_PATTERN_CONTRACT.md).
- Post-MVP hardening: k-anonymity floor before broadcast, differential
  privacy on shared aggregate statistics, bucket-boundary versioning,
  collision/false-match rate measurement, adversarial review of
  re-identification risk.

## Phase 7 — Governance, drift, explainability, human review ⬜

- SHAP attributions surfaced in the analyst "Why flagged?" panel
  ([`INVESTIGATOR_EXPERIENCE.md`](INVESTIGATOR_EXPERIENCE.md)).
- Drift monitoring: score-distribution and alert-rate drift, precision
  proxies from analyst dispositions (Model Monitoring service).
- Challenger models, periodic revalidation, threshold-change governance.
- False-positive feedback loop from case dispositions into training labels.
- Model cards + decision records for every deployed version.

---

## Standing rules across all phases

1. Synthetic or properly authorized data only; never real PII in research.
2. PR-AUC first; report FPR and alert volume with every metric set.
3. No model autonomously blocks a transaction — analyst review always.
4. Every shared artifact passes `verify_zero_pii()` and schema validation.
