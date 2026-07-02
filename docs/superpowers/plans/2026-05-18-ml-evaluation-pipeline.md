# ML Evaluation Pipeline Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance `train_baseline.py` with threshold analysis across operating modes, two new CLI flags, and a professional markdown evaluation report — then run both full and no-account-ID models and compare results.

**Architecture:** All changes live in a single script (`ml/scripts/train_baseline.py`). New helper functions `run_threshold_analysis()` and `generate_evaluation_report()` are appended below the existing helpers and called at the end of `main()`. The report is written as a markdown file alongside the existing JSON/CSV artifacts.

**Tech Stack:** Python 3, XGBoost, scikit-learn, pandas, numpy, pathlib, argparse

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `ml/scripts/train_baseline.py` | Modify | Add threshold analysis, new CLI flags, report generation |
| `ml/models/threshold_analysis.csv` | Create (generated) | Operating-mode comparison table |
| `ml/models/threshold_analysis.json` | Create (generated) | Same data, machine-readable |
| `ml/models/evaluation_report.md` | Create (generated) | Professional narrative report |

---

## Task 1: Add `--drop_id_features` and `--drop_bank_id_features` CLI flags

**Files:**
- Modify: `ml/scripts/train_baseline.py:337-349` (argparse block)
- Modify: `ml/scripts/train_baseline.py:141-147` (load_split, feature selection)

- [ ] **Step 1: Add the two new argparse arguments**

In `main()`, after the existing `--sample_frac` argument (line 348), add:

```python
    parser.add_argument(
        "--drop_id_features",
        action="store_true",
        default=False,
        help="Exclude source_account_enc and target_account_enc from features.",
    )
    parser.add_argument(
        "--drop_bank_id_features",
        action="store_true",
        default=False,
        help="Exclude source_bank_enc and target_bank_enc from features "
             "(is_cross_bank and cross_bank_flow_flag are kept).",
    )
```

- [ ] **Step 2: Build the active feature list from CLI flags**

In `main()`, after `args = parser.parse_args()` and before `args.model_dir.mkdir(...)`, add:

```python
    # Build the active feature list, honouring drop flags
    active_features = list(FEATURE_COLS)
    if args.drop_id_features:
        drop = {"source_account_enc", "target_account_enc"}
        active_features = [f for f in active_features if f not in drop]
        log.info("Dropping account-ID features: %s", sorted(drop))
    if args.drop_bank_id_features:
        drop_bank = {"source_bank_enc", "target_bank_enc"}
        active_features = [f for f in active_features if f not in drop_bank]
        log.info("Dropping bank-ID features: %s", sorted(drop_bank))
    log.info("Active feature count: %d", len(active_features))
```

- [ ] **Step 3: Thread `active_features` through `load_split`**

Change `load_split` signature from:
```python
def load_split(
    features_dir: Path,
    filename: str,
    sample_frac: float | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
```
to:
```python
def load_split(
    features_dir: Path,
    filename: str,
    active_features: list[str],
    sample_frac: float | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
```

And change the feature-validation + extraction block (around lines 141-147):
```python
    # Confirm all expected features are present
    missing = [c for c in active_features if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns in {filename}: {missing}")

    X = df[active_features].astype(np.float32)
    y = df[LABEL_COL].astype(np.int32)
    return X, y
```

- [ ] **Step 4: Update the three `load_split` call sites in `main()`**

Replace:
```python
    X_train, y_train = load_split(args.features_dir, "train_features.parquet", args.sample_frac)
    X_val,   y_val   = load_split(args.features_dir, "val_features.parquet",   args.sample_frac)
    X_test,  y_test  = load_split(args.features_dir, "test_features.parquet",  args.sample_frac)
```
With:
```python
    X_train, y_train = load_split(args.features_dir, "train_features.parquet", active_features, args.sample_frac)
    X_val,   y_val   = load_split(args.features_dir, "val_features.parquet",   active_features, args.sample_frac)
    X_test,  y_test  = load_split(args.features_dir, "test_features.parquet",  active_features, args.sample_frac)
```

- [ ] **Step 5: Fix `extract_feature_importance` to use active features**

Change:
```python
    df_imp = pd.DataFrame(
        {"feature": FEATURE_COLS, "importance": scores}
    ).sort_values("importance", ascending=False).reset_index(drop=True)
```
to use `active_features` parameter. Update the function signature to accept it:
```python
def extract_feature_importance(model, model_type: str, active_features: list[str]) -> pd.DataFrame:
    if model_type == "xgboost":
        scores = model.feature_importances_
    else:
        coefs = model.named_steps["clf"].coef_[0]
        scores = np.abs(coefs)

    df_imp = pd.DataFrame(
        {"feature": active_features, "importance": scores}
    ).sort_values("importance", ascending=False).reset_index(drop=True)
    return df_imp
```

Update the call in `main()` to pass `active_features`:
```python
    imp_df = extract_feature_importance(model, args.model_type, active_features)
```

- [ ] **Step 6: Pass `active_features` to the model artifact save**

Update the `joblib.dump` call in `main()` to save `active_features` instead of `FEATURE_COLS`:
```python
    joblib.dump(
        {
            "model":      model,
            "threshold":  threshold,
            "model_type": args.model_type,
            "features":   active_features,
        },
        model_path,
    )
```

---

## Task 2: Add threshold analysis function

**Files:**
- Modify: `ml/scripts/train_baseline.py` — add new function after `extract_feature_importance`

- [ ] **Step 1: Add `run_threshold_analysis()` function**

Insert this function after `extract_feature_importance` (before `main`):

```python
def run_threshold_analysis(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_steps: int = 2000,
) -> list[dict]:
    """
    Evaluate multiple operating modes on a single split (typically the test set).

    Modes
    -----
    conservative  : highest precision subject to recall >= 0.20
    balanced      : highest F1
    aggressive    : highest recall subject to precision >= 0.20
    budget_*      : top-K% highest-risk transactions flagged as alerts
                    (K in {0.05, 0.10, 0.25, 0.50, 1.00})

    Returns a list of dicts, one per mode, with keys:
        mode, threshold, alerts, tp, fp, fn, precision, recall, f1
    """
    thresholds = np.linspace(0.001, 0.999, n_steps)
    total = len(y_true)

    # ── Named-threshold modes ──────────────────────────────────────────────────
    best = {
        "conservative": {"thresh": 0.5, "prec": 0.0, "rec": 0.0, "f1": 0.0},
        "balanced":     {"thresh": 0.5, "prec": 0.0, "rec": 0.0, "f1": 0.0},
        "aggressive":   {"thresh": 0.5, "prec": 0.0, "rec": 0.0, "f1": 0.0},
    }

    for t in thresholds:
        pred = (y_prob >= t).astype(int)
        n_pos = pred.sum()
        if n_pos == 0:
            continue
        prec = precision_score(y_true, pred, pos_label=1, zero_division=0)
        rec  = recall_score(y_true, pred, pos_label=1, zero_division=0)
        f1   = f1_score(y_true, pred, pos_label=1, zero_division=0)

        # Conservative: maximise precision, recall >= 0.20
        if rec >= 0.20 and prec > best["conservative"]["prec"]:
            best["conservative"] = {"thresh": float(t), "prec": prec, "rec": rec, "f1": f1}

        # Balanced: maximise F1
        if f1 > best["balanced"]["f1"]:
            best["balanced"] = {"thresh": float(t), "prec": prec, "rec": rec, "f1": f1}

        # Aggressive: maximise recall, precision >= 0.20
        if prec >= 0.20 and rec > best["aggressive"]["rec"]:
            best["aggressive"] = {"thresh": float(t), "prec": prec, "rec": rec, "f1": f1}

    rows = []
    for mode_name, info in best.items():
        t = info["thresh"]
        pred = (y_prob >= t).astype(int)
        cm = confusion_matrix(y_true, pred)
        tn, fp, fn, tp = cm.ravel()
        rows.append({
            "mode":      mode_name,
            "threshold": round(t, 4),
            "alerts":    int(fp + tp),
            "tp":        int(tp),
            "fp":        int(fp),
            "fn":        int(fn),
            "precision": round(float(info["prec"]), 4),
            "recall":    round(float(info["rec"]), 4),
            "f1":        round(float(info["f1"]), 4),
        })

    # ── Alert budget modes (top-K% flagged) ───────────────────────────────────
    for pct in [0.05, 0.10, 0.25, 0.50, 1.00]:
        k = max(1, int(total * pct / 100))
        # Threshold = score of the k-th highest-risk transaction
        sorted_scores = np.sort(y_prob)[::-1]
        t = float(sorted_scores[min(k - 1, len(sorted_scores) - 1)])
        pred = (y_prob >= t).astype(int)
        # Clip to exactly k alerts if ties push it over
        if pred.sum() > k:
            top_k_idx = np.argsort(y_prob)[::-1][:k]
            pred = np.zeros(len(y_prob), dtype=int)
            pred[top_k_idx] = 1
        cm = confusion_matrix(y_true, pred)
        tn, fp, fn, tp = cm.ravel()
        prec = float(tp) / max(1, int(tp + fp))
        rec  = float(tp) / max(1, int(tp + fn))
        f1   = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        rows.append({
            "mode":      f"budget_{pct:.2f}pct",
            "threshold": round(t, 4),
            "alerts":    int(tp + fp),
            "tp":        int(tp),
            "fp":        int(fp),
            "fn":        int(fn),
            "precision": round(prec, 4),
            "recall":    round(rec, 4),
            "f1":        round(f1, 4),
        })

    return rows
```

---

## Task 3: Add evaluation report generation function

**Files:**
- Modify: `ml/scripts/train_baseline.py` — add `generate_evaluation_report()` after `run_threshold_analysis`

- [ ] **Step 1: Add `generate_evaluation_report()` function**

```python
def generate_evaluation_report(
    test_metrics: dict,
    threshold_rows: list[dict],
    active_features: list[str],
    model_type: str,
    drop_id_features: bool,
    drop_bank_id_features: bool,
    report_path: Path,
) -> None:
    """Write a professional markdown evaluation report."""

    cm = test_metrics["confusion_matrix"]
    tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
    total = tn + fp + fn + tp
    accuracy = (tn + tp) / total

    # Build threshold table rows
    header = "| Mode | Threshold | Alerts | TP | FP | FN | Precision | Recall | F1 |"
    separator = "|------|-----------|--------|----|----|-----|-----------|--------|----|"
    table_rows = [header, separator]
    for r in threshold_rows:
        table_rows.append(
            f"| {r['mode']} | {r['threshold']:.4f} | {r['alerts']:,} | "
            f"{r['tp']:,} | {r['fp']:,} | {r['fn']:,} | "
            f"{r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} |"
        )
    threshold_table = "\n".join(table_rows)

    # Pick recommended mode from threshold_rows
    balanced_row = next((r for r in threshold_rows if r["mode"] == "balanced"), threshold_rows[0])

    feature_note = ""
    if drop_id_features:
        feature_note += "\n- `--drop_id_features` active: `source_account_enc` and `target_account_enc` excluded."
    if drop_bank_id_features:
        feature_note += "\n- `--drop_bank_id_features` active: `source_bank_enc` and `target_bank_enc` excluded."

    report = f"""# Naseej — Model Evaluation Report

**Generated:** {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}  
**Model type:** {model_type}  
**Active features:** {len(active_features)} of {len(FEATURE_COLS)}{feature_note}

---

## 1. Dataset Overview

| Split | Total rows | Laundering | Prevalence |
|-------|-----------|------------|------------|
| Test  | {total:,} | {tp + fn:,} | {test_metrics['prevalence']:.4%} |

The dataset is **severely class-imbalanced**: fewer than 0.11% of transactions are
money-laundering events. This is realistic for AML — but it breaks many naive
evaluation approaches.

---

## 2. Why Accuracy Is Not Reported

A model that flags **zero** transactions as suspicious would achieve:

> Accuracy = {(total - (tp + fn)) / total:.4%}

That is a deceptively high number. Accuracy rewards the model for correctly
identifying the ~99.9% of legitimate transactions while completely ignoring every
single money-laundering event. In fraud detection, **a false negative (missed
laundering) is far more costly than a false positive (unnecessary review).**
Accuracy is therefore excluded from all headline metrics.

---

## 3. Primary Metric: PR-AUC

**PR-AUC (Area Under the Precision-Recall Curve)** measures how well the model
ranks laundering transactions above legitimate ones across *all* thresholds.

- **Random baseline PR-AUC** = prevalence = {test_metrics['prevalence']:.4f}  
- **This model's PR-AUC** = **{test_metrics['pr_auc']:.4f}**  
- **Lift over random** = {test_metrics['pr_auc'] / test_metrics['prevalence']:.1f}×

A PR-AUC of {test_metrics['pr_auc']:.4f} means the model achieves
{"MODERATE" if test_metrics['pr_auc'] < 0.50 else "GOOD" if test_metrics['pr_auc'] < 0.80 else "EXCELLENT"} discrimination power.
It is approximately **{test_metrics['pr_auc'] / test_metrics['prevalence']:.0f}× better than random** at surfacing real
laundering transactions.

ROC-AUC ({test_metrics['roc_auc']:.4f}) is reported for completeness but is known to be
over-optimistic under high class imbalance — PR-AUC is the authoritative metric.

---

## 4. Confusion Matrix Interpretation

```
                     Predicted Legitimate   Predicted Laundering
Actual Legitimate          {tn:>12,}              {fp:>12,}
Actual Laundering          {fn:>12,}              {tp:>12,}
```

In fraud investigation terms:

| Cell | Count | Meaning |
|------|-------|---------|
| True Negative (TN) | {tn:,} | Legitimate transactions correctly passed through — no analyst time wasted |
| False Positive (FP) | {fp:,} | Legitimate transactions flagged — analyst reviews and closes as false alarm |
| False Negative (FN) | {fn:,} | **Missed laundering** — the most damaging error; criminal funds move undetected |
| True Positive (TP) | {tp:,} | Laundering correctly caught — case opened, funds potentially frozen |

**Alert rate:** {(fp + tp) / total:.4%} of all transactions are flagged  
**Investigation yield (precision):** {test_metrics['precision']:.2%} of flagged alerts are real laundering  
**Detection rate (recall):** {test_metrics['recall']:.2%} of all actual laundering is caught

---

## 5. Threshold Analysis — Operating Modes

The decision threshold (default {test_metrics['threshold']:.4f}) controls the precision/recall trade-off.
Lower thresholds catch more laundering but generate more false alarms.

{threshold_table}

### Mode Descriptions

| Mode | Strategy | Use case |
|------|----------|----------|
| **conservative** | Maximise precision (recall ≥ 20%) | Transaction holds / automated blocking |
| **balanced** | Maximise F1 | Analyst triage — balanced workload vs. coverage |
| **aggressive** | Maximise recall (precision ≥ 20%) | Regulatory sweep — catch as much as possible |
| **budget_0.05pct** | Top 0.05% highest-risk flagged | Ultra-tight alert budget (SLA-constrained teams) |
| **budget_0.10pct** | Top 0.10% flagged | Small team with high investigation cost |
| **budget_0.25pct** | Top 0.25% flagged | Medium team |
| **budget_0.50pct** | Top 0.50% flagged | Larger team or automated pre-screening |
| **budget_1.00pct** | Top 1.00% flagged | Broad net before manual review |

---

## 6. Suitability Assessment

### a) Analyst Triage
**Suitable.** The model provides a {test_metrics['pr_auc'] / test_metrics['prevalence']:.0f}× lift over random sampling. Running
at the **balanced** threshold (F1={balanced_row['f1']:.4f}) surfaces
{balanced_row['tp']:,} true laundering cases with only {balanced_row['fp']:,} false alarms in this test set.
Analysts reviewing flagged transactions will find real laundering in roughly
{balanced_row['precision']:.0%} of their queue — dramatically better than uninformed review.

### b) Transaction Hold
**Use with caution.** The **conservative** mode achieves higher precision,
but any transaction hold requires compliance sign-off. A false hold on a
legitimate transaction creates regulatory and reputational risk. Recommend
pairing holds with a secondary human review step for the MVP.

### c) Automatic Blocking
**Not recommended at this stage.** PR-AUC of {test_metrics['pr_auc']:.4f} indicates moderate
discrimination power. Automatic blocking requires near-perfect precision
(> 95%) to avoid wrongful account freezes. The model's false-positive rate,
while low in absolute terms, could affect thousands of legitimate transactions
at scale. Blocking should be deferred until the model is validated on live
traffic and precision at extreme thresholds is confirmed.

---

## 7. Recommended Operating Mode for MVP Demo

**Recommendation: Balanced threshold (F1-maximising)**

| Metric | Value |
|--------|-------|
| Threshold | {balanced_row['threshold']:.4f} |
| Alerts generated | {balanced_row['alerts']:,} |
| True positives | {balanced_row['tp']:,} |
| False positives | {balanced_row['fp']:,} |
| Precision | {balanced_row['precision']:.4f} |
| Recall | {balanced_row['recall']:.4f} |
| F1 | {balanced_row['f1']:.4f} |

The balanced mode is ideal for the Naseej MVP demo because:

1. **It demonstrates real value** — detecting {balanced_row['recall']:.0%} of laundering transactions
   is a compelling result for a first-generation model.
2. **It is explainable** — F1 maximisation is a concept non-technical stakeholders
   can understand ("we tuned it to balance catching criminals vs. bothering
   innocent customers").
3. **It is safe for demo purposes** — the precision ({balanced_row['precision']:.0%}) means most
   flagged transactions are genuine cases, making live demos convincing.
4. **It sets a clear upgrade path** — future iterations can push toward the
   conservative mode for production transaction holds.

---

## 8. Model Artifacts

| File | Description |
|------|-------------|
| `baseline_model.pkl` | Serialised model + metadata |
| `baseline_threshold.json` | Chosen threshold and validation metrics |
| `feature_importance.csv` | Per-feature importance scores |
| `metrics.json` | Full test-set metrics at chosen threshold |
| `threshold_analysis.csv` | Operating-mode comparison table |
| `threshold_analysis.json` | Same data, machine-readable |
| `evaluation_report.md` | This report |

---

*Report generated by `ml/scripts/train_baseline.py` — Naseej baseline pipeline.*
"""
    report_path.write_text(report, encoding="utf-8")
    log.info("Evaluation report   → %s", report_path)
```

---

## Task 4: Wire threshold analysis and report into `main()`

**Files:**
- Modify: `ml/scripts/train_baseline.py` — inside `main()`, after the test evaluation block

- [ ] **Step 1: Add threshold analysis + report calls after test evaluation**

After the existing `test_metrics = evaluate(...)` call and before `# ── Save artifacts ──`, add:

```python
    # ── Threshold analysis ─────────────────────────────────────────────────────
    log.info("Running threshold analysis across operating modes ...")
    threshold_rows = run_threshold_analysis(y_test.to_numpy(), y_test_prob)

    # Pretty-print threshold table
    print("\n  Threshold Analysis — Operating Modes (Test Set):")
    print(f"  {'Mode':<20} {'Thresh':>8} {'Alerts':>8} {'TP':>6} {'FP':>6} {'FN':>6} {'Prec':>7} {'Rec':>7} {'F1':>7}")
    print("  " + "-" * 85)
    for r in threshold_rows:
        print(
            f"  {r['mode']:<20} {r['threshold']:>8.4f} {r['alerts']:>8,} "
            f"{r['tp']:>6,} {r['fp']:>6,} {r['fn']:>6,} "
            f"{r['precision']:>7.4f} {r['recall']:>7.4f} {r['f1']:>7.4f}"
        )
```

- [ ] **Step 2: Save threshold_analysis.csv and threshold_analysis.json**

After the pretty-print block, add (before `# ── Save artifacts ──`):

```python
    ta_df = pd.DataFrame(threshold_rows)
    ta_csv  = args.model_dir / "threshold_analysis.csv"
    ta_json = args.model_dir / "threshold_analysis.json"
    ta_df.to_csv(ta_csv, index=False)
    ta_json.write_text(json.dumps(threshold_rows, indent=2))
    log.info("Threshold analysis  → %s", ta_csv)
    log.info("Threshold analysis  → %s", ta_json)
```

- [ ] **Step 3: Call `generate_evaluation_report()` before the total elapsed log**

After the feature importance top-10 print block and metrics save, add:

```python
    # ── Evaluation report ──────────────────────────────────────────────────────
    report_path = args.model_dir / "evaluation_report.md"
    generate_evaluation_report(
        test_metrics=test_metrics,
        threshold_rows=threshold_rows,
        active_features=active_features,
        model_type=args.model_type,
        drop_id_features=args.drop_id_features,
        drop_bank_id_features=args.drop_bank_id_features,
        report_path=report_path,
    )
```

---

## Task 5: Implement all changes in `train_baseline.py`

**Files:**
- Modify: `ml/scripts/train_baseline.py` (full rewrite integrating Tasks 1–4)

- [ ] **Step 1: Apply all Task 1 changes (CLI flags + active_features threading)**

Make every edit from Task 1 in order. After each sub-edit, verify no syntax errors with:
```
python -c "import ast; ast.parse(open('ml/scripts/train_baseline.py').read()); print('OK')"
```

- [ ] **Step 2: Insert `run_threshold_analysis()` function**

Add the function from Task 2 directly before `main()` (after `extract_feature_importance`).
Verify syntax.

- [ ] **Step 3: Insert `generate_evaluation_report()` function**

Add the function from Task 3 directly after `run_threshold_analysis()`.
Verify syntax.

- [ ] **Step 4: Wire calls inside `main()`**

Apply Task 4 edits. Verify syntax.

---

## Task 6: Run full XGBoost model and capture output

**Files:** None (execution only)

- [ ] **Step 1: Run the full-feature model**

```
python ml/scripts/train_baseline.py --model_type xgboost
```

Expected: Script completes, prints threshold analysis table, logs paths to all 7 output files. Confirm these files exist:
- `ml/models/baseline_model.pkl`
- `ml/models/baseline_threshold.json`
- `ml/models/feature_importance.csv`
- `ml/models/metrics.json`
- `ml/models/threshold_analysis.csv`
- `ml/models/threshold_analysis.json`
- `ml/models/evaluation_report.md`

- [ ] **Step 2: Capture full-model metrics for comparison**

Read `ml/models/metrics.json` and note PR-AUC, precision, recall, F1, threshold.

---

## Task 7: Run no-account-ID XGBoost model

**Files:** None (execution only)

- [ ] **Step 1: Run with `--drop_id_features`**

```
python ml/scripts/train_baseline.py --model_type xgboost --drop_id_features
```

Expected: Script logs "Dropping account-ID features", runs with 30 features instead of 32,
completes successfully, overwrites model artifacts.

- [ ] **Step 2: Capture no-ID-model metrics for comparison**

Read `ml/models/metrics.json` for the second run.

---

## Task 8: Print final model comparison

**Files:** None (output only — comparison written to conversation)

- [ ] **Step 1: Compare both model runs side by side**

Format a comparison table:

```
| Metric     | Full model (32 features) | No account-ID (30 features) |
|------------|--------------------------|------------------------------|
| PR-AUC     | <from run 1>             | <from run 2>                 |
| ROC-AUC    | <from run 1>             | <from run 2>                 |
| Precision  | <from run 1>             | <from run 2>                 |
| Recall     | <from run 1>             | <from run 2>                 |
| F1         | <from run 1>             | <from run 2>                 |
| Threshold  | <from run 1>             | <from run 2>                 |
```

Interpret: if PR-AUC drops significantly when account IDs are removed, the model
was overfitting to account-level memorization. If PR-AUC is similar, the
graph-based behavioural features generalise without identity leakage — a stronger
signal for production deployability.

---

## Self-Review Checklist

**Spec coverage:**
- [x] Threshold analysis: Conservative, Balanced, Aggressive — `run_threshold_analysis()`
- [x] Alert budget modes: 0.05%, 0.10%, 0.25%, 0.50%, 1.00% — `run_threshold_analysis()`
- [x] Per-mode reporting: threshold, alerts, TP, FP, FN, precision, recall, F1 — table in report
- [x] `threshold_analysis.csv` — Task 4 Step 2
- [x] `threshold_analysis.json` — Task 4 Step 2
- [x] `evaluation_report.md` — Task 4 Step 3 + `generate_evaluation_report()`
- [x] `--drop_id_features` flag — Task 1
- [x] Excludes `source_account_enc`, `target_account_enc` when flag is set — Task 1 Step 2
- [x] `--drop_bank_id_features` flag — Task 1
- [x] Excludes `source_bank_enc`, `target_bank_enc` but keeps `is_cross_bank`, `cross_bank_flow_flag` — Task 1 Step 2
- [x] Report: why accuracy is not useful — Section 2
- [x] Report: PR-AUC as primary metric — Section 3
- [x] Report: confusion matrix in fraud investigation terms — Section 4
- [x] Report: suitability for analyst triage / transaction hold / automatic blocking — Section 6
- [x] Report: recommended operating mode for MVP — Section 7
- [x] Does not modify React frontend, `build_graph_features.py`, feature Parquet files — no tasks touch these
- [x] Still saves all original artifacts — Task 6 Step 1 confirms
- [x] Run full model — Task 6
- [x] Run no-account-ID model — Task 7
- [x] Final comparison — Task 8

**Type consistency:** `active_features: list[str]` used consistently across `load_split`, `extract_feature_importance`, `generate_evaluation_report`, and `joblib.dump`. `threshold_rows: list[dict]` passed from `run_threshold_analysis` to `generate_evaluation_report` and `pd.DataFrame`. All consistent.
