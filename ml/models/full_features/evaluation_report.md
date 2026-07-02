# Naseej — Model Evaluation Report

**Generated:** 2026-05-18 14:52
**Model type:** xgboost
**Active features:** 32 of 32

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
- **This model's PR-AUC** = **0.4271**
- **Lift over random** = 418.7×

PR-AUC of 0.4271 indicates
MODERATE discrimination power —
approximately **419× better than random** at surfacing real laundering.

ROC-AUC (0.9856) is reported for completeness but is misleadingly optimistic
under high class imbalance. PR-AUC is the authoritative metric.

---

## 4. Confusion Matrix Interpretation

```
                     Predicted Legitimate   Predicted Laundering
Actual Legitimate               760,785                       189
Actual Laundering                   499                       278
```

| Cell | Count | Meaning |
|------|-------|---------|
| True Negative (TN) | 760,785 | Legitimate transactions correctly cleared — no analyst time wasted |
| False Positive (FP) | 189 | Legitimate transactions flagged — analyst reviews and closes as false alarm |
| False Negative (FN) | 499 | **Missed laundering** — criminal funds move undetected |
| True Positive (TP) | 278 | Laundering correctly caught — case opened, funds potentially frozen |

**Alert rate:** 0.0613% of all transactions flagged
**Investigation yield (precision):** 59.53% of alerts are real laundering
**Detection rate (recall):** 35.78% of all laundering caught

---

## 5. Threshold Analysis — Operating Modes

| Mode | Threshold | Alerts | TP | FP | FN | Precision | Recall | F1 |
|------|-----------|--------|----|----|-----|-----------|--------|----|
| conservative | 0.9975 | 197 | 168 | 29 | 609 | 0.8528 | 0.2162 | 0.3450 |
| balanced | 0.9930 | 549 | 299 | 250 | 478 | 0.5446 | 0.3848 | 0.4510 |
| aggressive | 0.9616 | 2,366 | 475 | 1,891 | 302 | 0.2008 | 0.6113 | 0.3023 |
| budget_0.05pct | 0.9948 | 380 | 250 | 130 | 527 | 0.6579 | 0.3218 | 0.4322 |
| budget_0.10pct | 0.9903 | 761 | 331 | 430 | 446 | 0.4350 | 0.4260 | 0.4304 |
| budget_0.25pct | 0.9716 | 1,904 | 445 | 1,459 | 332 | 0.2337 | 0.5727 | 0.3320 |
| budget_0.50pct | 0.9213 | 3,808 | 537 | 3,271 | 240 | 0.1410 | 0.6911 | 0.2342 |
| budget_1.00pct | 0.7332 | 7,617 | 613 | 7,004 | 164 | 0.0805 | 0.7889 | 0.1461 |

| Mode | Strategy |
|------|----------|
| **conservative** | Maximise precision, recall ≥ 20% — suits transaction holds |
| **balanced** | Maximise F1 — suits analyst triage |
| **aggressive** | Maximise recall, precision ≥ 20% — suits regulatory sweeps |
| **budget_X.XXpct** | Top X% highest-risk flagged — suits fixed alert budgets |

---

## 6. Suitability Assessment

### a) Analyst Triage
**Suitable.** The model provides a 419× lift over random sampling. At the
**balanced** threshold, analysts reviewing flagged transactions find real laundering
in ~54% of their queue — dramatically better than uninformed review.

### b) Transaction Hold
**Use with caution.** The **conservative** mode (precision=85.28%) improves
precision but any transaction hold requires compliance sign-off. False holds on
legitimate transactions create regulatory and reputational risk. Recommend pairing
holds with a mandatory human review step during the MVP phase.

### c) Automatic Blocking
**Not recommended at this stage.** PR-AUC of 0.4271 indicates moderate discrimination
power. Automatic blocking requires near-perfect precision (>95%) to avoid wrongful
account freezes. Defer until the model is validated on live traffic and extreme-
threshold precision is confirmed over time.

---

## 7. Recommended Operating Mode for MVP Demo

**Recommendation: Balanced threshold (F1-maximising)**

| Metric | Value |
|--------|-------|
| Threshold | 0.9930 |
| Alerts generated | 549 |
| True positives | 299 |
| False positives | 250 |
| Precision | 0.5446 |
| Recall | 0.3848 |
| F1 | 0.4510 |

The balanced mode is ideal for the Naseej MVP because:

1. **Demonstrates real value** — detecting 38% of laundering is compelling for a first-generation model.
2. **Explainable** — F1 maximisation is intuitive for non-technical stakeholders.
3. **Safe for demo** — 54% precision means most flagged transactions are genuine.
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
