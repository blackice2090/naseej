# Model Evaluation — LightGBM Comparison, Per-Typology Recall, Context Ablation

**Status: research prototype · synthetic AMLworld benchmark only · not production validation**

This document covers the post-MVP ML evaluation phase. It does **not** change
the deployed model or the demo; it adds an offline evaluation suite
(`ml/src/evaluation_suite.py`) that strengthens Naseej's ML credibility by
answering three questions on held-out data:

1. Does a stronger gradient-boosting library (LightGBM) beat XGBoost here?
2. Which AML typologies does the model detect well, and which does it miss?
3. Do graph and context features actually improve detection, or is the lift
   just account-identity memorisation?

All outputs live under `ml/reports/` as JSON + Markdown pairs and are served
read-only by the backend at `/api/model/*`. A condensed, analyst-facing
summary of these reports (best/test-leader model, weakest typology, threshold
policy, limitations, and SHAP availability) is also served at
`GET /api/explain/model` — see [`EXPLAINABILITY.md`](EXPLAINABILITY.md).

---

## 1. Why PR-AUC is the primary metric (and accuracy is not reported)

Laundering prevalence in AMLworld HI-Small is ~0.1%. A classifier that
predicts "benign" for **every** transaction is 99.9% accurate and catches
zero laundering. Accuracy, and to a lesser extent ROC-AUC, are dominated by
the negative class and reward exactly that useless behaviour.

PR-AUC (average precision) summarises the precision/recall trade-off across
all thresholds **on the positive class only**, so it is sensitive to whether
we actually find laundering. It is the primary metric throughout. ROC-AUC,
precision, recall, F1, false-positive rate, alert volume and confusion
matrices are reported as secondary context. **Accuracy is intentionally
omitted from every report.**

---

## 2. Protocol (and why it differs from the deployed baseline)

| Aspect | This suite | Deployed baseline (`model_metrics.json`) |
|---|---|---|
| Split | **Temporal** 70/15/15 by timestamp | Stratified random over a 300k sample |
| Leakage control | Point-in-time features + no train/test time overlap | Point-in-time features, but time-overlapping splits |
| Feature set | Up to 32 features (4 ablation sets) | 32 features (full) |
| Model selection | Best validation PR-AUC | Best validation PR-AUC |
| Threshold | F1-optimal on validation, frozen before test | F1-optimal on validation |

Because the split protocols differ, the headline numbers here are **not
directly comparable** with `model_metrics.json`. The suite never overwrites
`model_metrics.json` or `ml/models/baseline_model.joblib` — the deployed
artefacts are untouched, so the backend/frontend/demo keep working exactly as
before.

The temporal split is the more honest protocol for AML: training on the past
and testing on the future is what a deployed system actually faces. Under it,
all four competitors score substantially higher PR-AUC than the legacy
baseline — most of that gain is the harder-but-fairer split plus the
point-in-time context features, **not** a claim of real-world performance.

### Leakage prevention

Every engineered feature is point-in-time, reusing the strictly-before
semantics already proven in `ml/scripts/build_graph_features.py`:

- Cumulative counts/sums use `cumcount()` / `cumsum() - current`, so a row
  never sees itself or any later row.
- Rolling 1h/24h windows query `t - window` via `merge_asof(direction=
  "backward")` — the window is open at both ends and excludes the current row.
- Val features are built with train prepended as history; test features with
  train+val prepended. History rows are stripped from the output. No feature
  uses a future transaction.

---

## 3. Model comparison (`model_comparison.{json,md}`)

Four competitors, identical untuned hyperparameters to
`ml/src/train_baseline.py` (this is a protocol comparison, not a tuning
exercise). LightGBM is added as an **optional** competitor: if the dependency
is missing the suite records a skip reason in the `availability` block and
proceeds with the rest — it never fabricates LightGBM results.

Held-out **test** PR-AUC (temporal split, threshold frozen on validation):

| Model | test PR-AUC | ROC-AUC | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|---|
| **lightgbm** (test-leader) | **0.6118** | 0.9832 | 0.636 | 0.556 | 0.594 | 0.00065 |
| xgboost | 0.5784 | 0.9859 | 0.617 | 0.550 | 0.581 | 0.00070 |
| random_forest (selected) | 0.5740 | 0.9658 | 0.574 | 0.543 | 0.558 | 0.00083 |
| logistic_regression | 0.0434 | 0.9587 | 0.047 | 0.464 | 0.085 | 0.01934 |

**Selected vs test-leader.** Model selection is on **validation** PR-AUC
(test stays held out), which picks `random_forest` by a razor-thin margin
(val 0.3860 vs LightGBM 0.3794 — within 0.007). On the unbiased held-out test
set, **LightGBM is clearly the strongest** (0.6118). The reports expose both:
`best_model` (validation-selected, the deployment candidate) and `test_leader`
(LightGBM). The near-tie on validation flipping on test is estimation noise
near the top, not a decisive gap — but the gradient-boosting models lead on
the honest test ranking, and the frontend evidence card reports the
test-leader as "best by PR-AUC".

Logistic regression collapses (PR-AUC 0.043, FPR ~2%): a linear model cannot
separate this class boundary and would bury analysts in false positives.

---

## 4. Per-typology recall (`per_typology_recall.{json,md}`)

> **Heuristic labels — not ground truth.** AMLworld does not ship per-typology
> annotations. The suite runs the `ml/src/pattern_library.py` detectors over
> test-period laundering neighbourhoods and assigns each laundering
> transaction the highest-priority typology that touches its accounts. These
> are inferred labels; the report states this in its `label_method` field and
> in every row's notes.

Recall by typology for the test-period laundering transactions (primary model
shown; per-model recall is in the JSON):

| Typology | Samples | Recall | Note |
|---|---|---|---|
| cross_bank_pass_through | 1335 | 0.56 | Dominant bucket; LightGBM strongest |
| rapid_sweep | 106 | 0.76 | Best-detected multi-step typology |
| mule_velocity | 62 | **0.05** | **Weakest** — fast-in/fast-out mules slip through |
| unknown_unmatched | 25 | 0.08 | No detector matched; model also struggles |
| fan_in / fan_out / simple_cycle | 8–16 each | 0.38–0.44 | Small samples — unstable estimates |
| scatter_gather / gather_scatter | 0 | — | No test-period positives matched |

**Takeaway:** the model is strong on cross-bank pass-through and rapid-sweep
typologies but weak on `mule_velocity` (rapid high-frequency forwarding) and
on laundering that matches no known pattern. Those are the priorities for the
GNN research phase, which is designed to learn multi-hop temporal structure
the current flat features cannot.

---

## 5. Feature ablation (`ablation_report.{json,md}`)

Four nested feature sets, same model family, point-in-time throughout:

| Feature set | #Feat | test PR-AUC | Δ vs transaction-only |
|---|---|---|---|
| transaction_only | 10 | 0.0766 | — |
| graph | 18 | 0.1790 | **+0.102** |
| graph_context | 30 | 0.5548 | **+0.478** |
| full_with_account_ids | 32 | 0.5740 | +0.497 |

**This is the strongest evidence in the phase.** Graph features more than
double PR-AUC over transactions alone; point-in-time **context** features
(rolling velocity windows, account-pair history, sweep ratio) more than triple
it again. Context is the single biggest lever.

The fourth set adds account-identifier encodings (as the deployed baseline
uses). Its lift over `graph_context` is small (+0.019) and is attributable to
**account-identity memorisation** — it would not transfer to unseen accounts,
so we flag it rather than celebrate it.

### Offline vs online context — a real limitation

The live feature store (`/api/features/*`, see [FEATURE_STORE.md](FEATURE_STORE.md))
computes context online from ingested events. This ablation uses the **offline
point-in-time equivalents** (`*_1h`, `*_24h`, `account_pair_*`, `sweep_ratio`,
`rapid_movement_flag` from `build_graph_features.py`), which follow the same
strictly-before discipline. The offline and online definitions are aligned in
intent but are computed by different code paths. That gap is now **measured** by
the feature contract + parity checker ([FEATURE_CONTRACT.md](FEATURE_CONTRACT.md)):
the windowed count/amount features match point-in-time across four scenarios, the
`fan_in_score`/`fan_out_score` name collisions are now **resolved** (online emits
`*_normalized_1h`), and the all-time cumulative features remain excluded from the
approved retraining
set (see §7).

---

## 6. Threshold analysis (`threshold_analysis.{json,md}`)

Three operating points for the test-leader, each selected on validation
(maximising F-beta) and frozen before touching test:

| Mode | Threshold | Precision | Recall | Alerts/100k | Use case |
|---|---|---|---|---|---|
| high_precision | 0.235 | 0.82 | 0.35 | 88 | Compliance escalation (SAR-style) |
| balanced | 0.125 | 0.57 | 0.54 | 194 | Analyst triage queue |
| high_recall | 0.080 | 0.41 | 0.66 | 333 | Monitoring watchlist only |

(Numbers shown are from the `random_forest` selected model; the regenerated
report reflects the current test-leader.) The high-recall mode roughly doubles
alert volume versus high-precision for ~30 extra recall points — the classic
AML trade-off. None of these are production thresholds; they are illustrative
operating points on a synthetic benchmark.

---

> **Shadow candidate (later phase).** A clean-room candidate trained on ONLY
> the 15 approved parity-clean features ([`CANDIDATE_MODEL.md`](CANDIDATE_MODEL.md))
> scores test PR-AUC **0.4247** (XGBoost) — below the `full_with_account_ids`
> ablation (0.574) because it drops the serve-only graph/context features and
> the account-id memorisation lift. It is a SHADOW evaluation, never deployed.

## 7. What improved, what's real vs heuristic, what remains

**Improved (real, on synthetic data):**
- LightGBM beats XGBoost on held-out PR-AUC (0.612 vs 0.578).
- Quantified, leakage-controlled proof that graph + context features drive
  almost all detection skill.
- Per-typology recall surfaces a concrete weakness (`mule_velocity`).
- Threshold menu maps model scores to operating policies.

**Real:** model metrics, feature ablation deltas, threshold trade-offs — all
computed on held-out test data with point-in-time features.

**Heuristic (clearly labelled):** the per-typology labels are inferred by the
pattern library, not AMLworld ground truth. Recall by typology is therefore an
estimate conditioned on the heuristic labelling.

**Remains before any production claim:**
- Out-of-time validation on real (not synthetic) supervised data under SAMA
  governance — nothing here transfers automatically.
- A single shared point-in-time context-feature definition reconciling the
  offline suite with the online feature store. **Progress:** the feature
  contract + parity checker ([FEATURE_CONTRACT.md](FEATURE_CONTRACT.md)) measure
  this across four scenarios; the `fan_in`/`fan_out` name collisions are now
  resolved and 15 features are parity-clean/approved. Still pending before a
  faithful retrain: the all-time cumulatives (kept excluded — no 30d online
  back-fill) and the serve-only graph/context features have no offline twin.
- Model drift monitoring, calibration, and human-review governance (Phase 7).
- Hyperparameter tuning (this phase deliberately did not tune).

**Why GNN is still a later research phase:** the weakest typologies
(`mule_velocity`, unmatched) involve multi-hop temporal structure that flat
per-transaction features approximate poorly. A graph neural network is the
natural next experiment, but it needs the point-in-time feature reconciliation
above and a leakage-audited temporal graph construction first — so it stays a
planned research phase, not part of this evaluation.

---

## 8. Reproducing

```bash
# Full run over ml/data/processed (writes the four report pairs):
python -m ml.src.evaluation_suite --train-sample 800000 --seed 42

# Fast tests (synthetic mini-dataset, no real data touched):
python -m pytest ml/tests/test_evaluation_suite.py backend/tests/test_model_reports.py
```

The suite is deterministic (`seed=42`). If LightGBM or XGBoost is not
installed it is skipped with a recorded reason — the run still completes and
the other models are reported.
