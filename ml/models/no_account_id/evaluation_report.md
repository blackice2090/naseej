# Naseej — Model Evaluation Report

**Generated:** 2026-05-18 15:05
**Model type:** xgboost
**Active features:** 30 of 32
- `--drop_id_features` active: `source_account_enc` and `target_account_enc` excluded.

---

## 1. Dataset Overview

| Split | Total rows | Laundering | Prevalence |
|-------|-----------|------------|------------|
| Test  | 761,751 | 777 | 0.1020% |

The dataset is **severely class-imbalanced**: fewer than 0.11% of transactions are
money-laundering events. This reflects realistic AML conditions.

---

## 2. Why Accuracy Is Not Reported

A model that flags **zero** transactions would achieve:

> Accuracy = 99.8980%

That is a deceptively high figure. Accuracy rewards the model for correctly
identifying the ~99.9% of legitimate transactions while completely ignoring every
money-laundering event. In fraud detection, a false negative (missed laundering)
is far more costly than a false positive. Accuracy is therefore excluded.

---

## 3. Primary Metric: PR-AUC

**PR-AUC (Area Under the Precision-Recall Curve)** measures how well the model
ranks laundering transactions above legitimate ones across *all* thresholds.

- **Random baseline PR-AUC** = prevalence = 0.0010
- **This model's PR-AUC** = **0.3946**
- **Lift over random** = 386.9×

PR-AUC of 0.3946 indicates
MODERATE discrimination power —
approximately **387× better than random** at surfacing real laundering.

ROC-AUC (0.9854) is reported for completeness but is misleadingly optimistic
under high class imbalance. PR-AUC is the authoritative metric.

---

## 4. Confusion Matrix Interpretation

```
                     Predicted Legitimate   Predicted Laundering
Actual Legitimate               760,662                       312
Actual Laundering                   496                       281
```

| Cell | Count | Meaning |
|------|-------|---------|
| True Negative (TN) | 760,662 | Legitimate transactions correctly cleared — no analyst time wasted |
| False Positive (FP) | 312 | Legitimate transactions flagged — analyst reviews and closes as false alarm |
| False Negative (FN) | 496 | **Missed laundering** — criminal funds move undetected |
| True Positive (TP) | 281 | Laundering correctly caught — case opened, funds potentially frozen |

**Alert rate:** 0.0778% of all transactions flagged
**Investigation yield (precision):** 47.39% of alerts are real laundering
**Detection rate (recall):** 36.16% of all laundering caught

---

## 5. Threshold Analysis — Operating Modes

| Mode | Threshold | Alerts | TP | FP | FN | Precision | Recall | F1 |
|------|-----------|--------|----|----|-----|-----------|--------|----|
| conservative | 0.9970 | 198 | 161 | 37 | 616 | 0.8131 | 0.2072 | 0.3303 |
| balanced | 0.9935 | 552 | 273 | 279 | 504 | 0.4946 | 0.3514 | 0.4108 |
| aggressive | 0.9730 | 2,208 | 443 | 1,765 | 334 | 0.2006 | 0.5701 | 0.2968 |
| budget_0.05pct | 0.9951 | 380 | 230 | 150 | 547 | 0.6053 | 0.2960 | 0.3976 |
| budget_0.10pct | 0.9915 | 761 | 312 | 449 | 465 | 0.4100 | 0.4015 | 0.4057 |
| budget_0.25pct | 0.9774 | 1,904 | 429 | 1,475 | 348 | 0.2253 | 0.5521 | 0.3200 |
| budget_0.50pct | 0.9374 | 3,808 | 516 | 3,292 | 261 | 0.1355 | 0.6641 | 0.2251 |
| budget_1.00pct | 0.7646 | 7,617 | 613 | 7,004 | 164 | 0.0805 | 0.7889 | 0.1461 |

| Mode | Strategy |
|------|----------|
| **conservative** | Maximise precision, recall ≥ 20% — suits transaction holds |
| **balanced** | Maximise F1 — suits analyst triage |
| **aggressive** | Maximise recall, precision ≥ 20% — suits regulatory sweeps |
| **budget_X.XXpct** | Top X% highest-risk flagged — suits fixed alert budgets |

---

## 6. Suitability Assessment

### a) Analyst Triage
**Suitable.** The model provides a 387× lift over random sampling. At the
**balanced** threshold, analysts reviewing flagged transactions find real laundering
in ~49% of their queue — dramatically better than uninformed review.

### b) Transaction Hold
**Use with caution.** The **conservative** mode (precision=81.31%) improves
precision but any transaction hold requires compliance sign-off. False holds on
legitimate transactions create regulatory and reputational risk. Recommend pairing
holds with a mandatory human review step during the MVP phase.

### c) Automatic Blocking
**Not recommended at this stage.** PR-AUC of 0.3946 indicates moderate discrimination
power. Automatic blocking requires near-perfect precision (>95%) to avoid wrongful
account freezes. Defer until the model is validated on live traffic and extreme-
threshold precision is confirmed over time.

---

## 7. Recommended Operating Mode for MVP Demo

**Recommendation: Balanced threshold (F1-maximising)**

| Metric | Value |
|--------|-------|
| Threshold | 0.9935 |
| Alerts generated | 552 |
| True positives | 273 |
| False positives | 279 |
| Precision | 0.4946 |
| Recall | 0.3514 |
| F1 | 0.4108 |

The balanced mode is ideal for the Naseej MVP because:

1. **Demonstrates real value** — detecting 35% of laundering is compelling for a first-generation model.
2. **Explainable** — F1 maximisation is intuitive for non-technical stakeholders.
3. **Safe for demo** — 49% precision means most flagged transactions are genuine.
4. **Clear upgrade path** — future iterations can shift toward conservative mode for production holds.

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
