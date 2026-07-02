# Feature Contract — Offline/Online Reconciliation + Training Contract

**Status: research prototype · synthetic data · safety gate before any retrain/GNN · not production-ready**

This phase closes a documented gap: the OFFLINE features used for
training/evaluation and the ONLINE node-local feature store used at scoring
time were computed by different code paths, under different names, and — in two
cases — under the **same name with a different definition**. Before any
retraining, GNN, or production-like upgrade we need one contract that reconciles
them and a checker that proves parity point-in-time.

Nothing here retrains the deployed model, starts GNN/federated work, or claims
production readiness.

> **Reconciliation Fix Sprint (contract v2).** The `fan_in_score` / `fan_out_score`
> name collisions are now **resolved**: the online store emits distinctly named
> `fan_in_normalized_1h` / `fan_out_normalized_1h`, while the offline 24h integer
> counts keep their legacy column names under the canonical `fan_in_count_24h` /
> `fan_out_count_24h`. The replay harness runs **four deterministic scenarios** and
> the contract self-checks that no bare feature name maps to two different
> canonical meanings (`collisions_resolved: true`).

---

## 1. The artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Canonical contract (code source of truth) | `ml/src/feature_contract.py` | Defines every canonical feature + its offline/online names, definition, parity status, train/serve/explain flags |
| Canonical contract (generated JSON) | `ml/features/feature_contract.json` | The served artifact; regenerate with `python -m ml.src.feature_contract` |
| Contract JSON schema | `docs/schemas/feature_contract.schema.json` | Validates the contract document |
| Parity checker + replay harness | `ml/src/feature_parity_check.py` | Replays four deterministic scenarios through both paths, compares point-in-time |
| Parity report | `ml/reports/feature_parity_report.{json,md}` | Per-feature match / mismatch / train-only / serve-only |
| Training manifest | `ml/reports/training_feature_manifest.{json,md}` | Approved vs excluded training features + reasons |

Served read-only (no node auth — bucketed/structural metadata, no raw values):
`GET /api/model/feature-contract`, `/api/model/feature-parity`,
`/api/model/training-feature-manifest` (each degrades to a `source:"fallback"`
note when its file is absent).

Regenerate everything:

```bash
python -m ml.src.feature_contract          # writes ml/features/feature_contract.json
python -m ml.src.feature_parity_check       # writes parity + training manifest reports
```

---

## 2. Why offline/online parity matters

The model is trained on offline features and scored on online features. If the
two disagree — different window, different formula, different name mapped to the
wrong column — then **the model is served inputs it was never trained on**, and
its scores (and SHAP explanations of those scores) become meaningless. Worse,
the mismatch is silent: nothing crashes, the numbers just drift. A faithful
retrain is only safe once every training feature has a serving twin that
computes the *same value* point-in-time. This contract makes the gap explicit
and the parity checker measures it.

---

## 3. What the audit found

`parity_status` per feature (full table in the contract / parity report):

- **`match` / `name_only` (8 windowed features)** — identical definition,
  comparable. Offline `source_out_tx_count_1h` == online `source_out_degree_1h`;
  offline `source_out_amount_sum_1h` == online `amount_sent_1h`; and the 1h/24h
  in/out count+sum pairs. The replay harness confirms these match exactly
  point-in-time (`parity_targets_clean: true`).
- **NAME COLLISIONS — RESOLVED (sprint v2):** the online store no longer emits
  `fan_in_score`/`fan_out_score`. It emits `fan_in_normalized_1h` /
  `fan_out_normalized_1h` (`min(1, count_1h/5)`, `serve_only`); the offline 24h
  integer counts keep their legacy column names under canonical `fan_in_count_24h`
  / `fan_out_count_24h` (`train_only`). Offline `sweep_ratio` (all-time) and online
  `rolling_amount_ratio` (24h) already have distinct names — no collision.
- **`definition_mismatch` — encodings (4, the only remaining mismatches):**
  account-id and bank-id encodings use a training-time `LabelEncoder` offline but
  `-1` / a hash at serving — not reproducible. Flagged `identity_memorization_risk`
  and **permanently excluded**. Safe structural replacement: `is_cross_bank`
  (approved) for bank identity; serve-only newness buckets for counterparty.
- **`train_only` (12 features):** all-time cumulative (`*_total_before`),
  account-pair features, `fan_in_count_24h`/`fan_out_count_24h`,
  `sweep_ratio_all_time`, `rapid_movement_flag`. Not reproducible online (25h
  pruning, or no online twin). A 30d bounded equivalent was **not** created — the
  online store's 25h horizon can't hold 30 days of events without a
  retention/memory change that is out of scope and would not stay test-fast.
- **`serve_only` (13 features) — decision B:** online-only graph/context features
  (`fan_in/out_normalized_1h`, `scatter_gather_score`, `simple_cycle_score`,
  `account_velocity_zscore`, `rolling_amount_ratio_24h`, newness buckets,
  `sweep_after_fan_in_flag`, `cross_bank_transfer_count_24h`, the 1h `unique_*`).
  Each has **no offline point-in-time equivalent**; they power the rule layer and
  explanations, never the trained model. Parity is not faked.

---

## 4. Approved retraining features (the safety output)

The training manifest approves a feature **only if** it is `trainable` AND
`servable` AND not an identity-memorisation risk AND parity-clean in the latest
run. Result: **15 approved**, **29 excluded**.

**Approved (15):** `amount`, `is_cross_bank`, `hour_of_day`, `day_of_week`,
`is_weekend`, `currency_code`, `payment_type_code`, and the eight parity-clean
windowed count/amount features (`source_outflow_count_1h/24h`,
`target_inflow_count_1h/24h`, `source_outflow_amount_1h/24h`,
`target_inflow_amount_1h/24h`).

**Excluded — identity/memorisation risk:** `source_account_code`,
`target_account_code`, `source_bank_code`, `target_bank_code`. The ablation
(`MODEL_EVALUATION.md`) already showed the account-id lift does not generalise;
here they are excluded structurally because serving cannot reproduce them.

**Excluded — not servable (all-time / pair):** the six `*_all_time` cumulative
features and both `account_pair_*` features (online prunes >25h).

**Excluded — train-only (no servable twin):** `fan_in_count_24h`,
`fan_out_count_24h`, `sweep_ratio_all_time`, `rapid_movement_flag`, the six
`*_all_time` cumulatives, and both `account_pair_*` (12 total).

**Excluded — serve-only (decision B):** the 13 online-only features (no training
counterpart).

---

## 5. Point-in-time guarantee (the replay harness — 4 scenarios)

The harness (`build_scenarios()`) replays **four** deterministic synthetic
sequences — `fan_in_then_sweep`, `fan_out_dispersion`, `cross_bank_pass_through`,
`quiet_legitimate` — and for each reads the focus account's features at an
`as_of` that is **strictly after every event in that scenario**. Offline uses the
strictly-before builders from `build_graph_features.py`; online ingests the same
events in order and reads at the node's latest event timestamp. All eight
windowed parity-target features match (`matched`) in every scenario
(`parity_targets_clean: true`). A test adds a far-future event and confirms it
does not change the point-in-time features. No feature, on either path, uses a
future transaction.

---

## 6. Is GNN unblocked?

**Still blocked — but one blocker is removed.** The name collisions are resolved,
so the contract is now unambiguous and the eight windowed features are
parity-clean across all scenarios. GNN remains blocked because most training
features are still *not servable*: the all-time cumulatives and the 24h count
scores have no online twin (decision: kept excluded, not back-filled), and the
serve-only graph/context features have no offline twin. A GNN needs a
leakage-audited temporal graph built from features that are *both* trainable and
servable; today that set is the 15 approved tabular features only. The manifest
is the gating checklist; GNN stays a planned research track.

---

## 7. What remains before model retraining

1. ~~Reconcile the `fan_in_score` / `fan_out_score` name collisions~~ — **done
   (v2):** online emits `*_normalized_1h`, offline keeps `*_count_24h`.
2. Decide the all-time cumulative / pair features: they stay **excluded** (no
   30d online equivalent was built — 25h horizon). If they are wanted for
   training, add bounded running totals to the online store first.
3. Account/bank-id encodings stay **permanently excluded** (memorisation); use
   `is_cross_bank` + serve-only newness buckets as the structural replacement.
4. Re-run `feature_parity_check` and require `parity_targets_clean: true` over
   the full *approved* set as a pre-retrain gate (currently true for the 15).
5. Only then retrain — on the 15 approved features — and publish new reports.
   Until all of that lands, the deployed model is not retrained.

A **shadow candidate** has now been trained on exactly these 15 features
([`CANDIDATE_MODEL.md`](CANDIDATE_MODEL.md)) — test PR-AUC 0.4247 (XGBoost),
no identity encodings, SHAP explanations resolved through this contract. It is
documented for review and **not deployed**; it does not change the contract or
the deployed model. It can also be **scored live in shadow** beside the deployed
baseline (`POST /api/model/candidate/score-shadow`), building these same 15
features from the online feature path — comparison-only, never driving a
decision. The hard-blocked features (identity encodings, all-time cumulatives,
account-pair, serve-only) are rejected by an allow-list at serving time too.
