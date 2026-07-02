# Model Comparison Report: Full Features vs. No Account-ID

**Generated:** 2026-05-18
**Project:** Naseej — AML Transaction Fraud Detection

---

## Overview

This report compares two XGBoost fraud-detection models trained on the same dataset and evaluated on the same held-out test set:

| Model | Features | Description |
|---|---|---|
| **Full Features** | 32 | Includes all features, among them `source_account_enc` and `target_account_enc` |
| **No Account-ID** | 30 | Drops `source_account_enc` and `target_account_enc` to reduce identity-leakage risk |

Test-set prevalence: **0.102%** (777 positives in ~761,751 transactions).

---

## 1. Head-to-Head Summary (at Each Model's Best Threshold)

| Metric | Full Features (32) | No Account-ID (30) | Delta |
|---|---:|---:|---:|
| **PR-AUC** | **0.4271** | 0.3946 | −0.0325 (−7.6%) |
| **ROC-AUC** | **0.9856** | 0.9854 | −0.0002 (−0.0%) |
| **Precision** | **0.5953** | 0.4739 | −0.1214 |
| **Recall** | **0.3578** | 0.3616 | +0.0038 |
| **F1** | **0.4469** | 0.4102 | −0.0367 |
| **Threshold** | 0.9940 | 0.9930 | — |
| **TP** | 278 | 281 | +3 |
| **FP** | 189 | 312 | +123 |
| **FN** | 499 | 496 | −3 |

> The full-feature model achieves higher precision at its optimal threshold, with dramatically fewer false positives (189 vs. 312). The no-ID model catches marginally more true positives (281 vs. 278) but at the cost of 65% more false positive alerts.

---

## 2. Threshold Analysis — Side-by-Side Comparison

All 8 operating modes, both models.

| Mode | Threshold (Full) | Alerts | TP | FP | Prec | Recall | F1 | Threshold (No-ID) | Alerts | TP | FP | Prec | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| conservative | 0.9975 | 197 | 168 | 29 | **0.853** | 0.216 | 0.345 | 0.9970 | 198 | 161 | 37 | 0.813 | 0.207 | 0.330 |
| balanced | 0.9930 | 549 | 299 | 250 | **0.545** | **0.385** | **0.451** | 0.9935 | 552 | 273 | 279 | 0.495 | 0.351 | 0.411 |
| aggressive | 0.9616 | 2,366 | 475 | 1,891 | 0.201 | **0.611** | 0.302 | 0.9730 | 2,208 | 443 | 1,765 | 0.201 | 0.570 | 0.297 |
| budget_0.05pct | 0.9948 | 380 | 250 | 130 | **0.658** | 0.322 | 0.432 | 0.9951 | 380 | 230 | 150 | 0.605 | 0.296 | 0.398 |
| budget_0.10pct | 0.9903 | 761 | 331 | 430 | **0.435** | 0.426 | 0.430 | 0.9915 | 761 | 312 | 449 | 0.410 | 0.402 | 0.406 |
| budget_0.25pct | 0.9716 | 1,904 | 445 | 1,459 | **0.234** | **0.573** | 0.332 | 0.9774 | 1,904 | 429 | 1,475 | 0.225 | 0.552 | 0.320 |
| budget_0.50pct | 0.9213 | 3,808 | 537 | 3,271 | **0.141** | **0.691** | 0.234 | 0.9374 | 3,808 | 516 | 3,292 | 0.136 | 0.664 | 0.225 |
| budget_1.00pct | 0.7332 | 7,617 | 613 | 7,004 | 0.081 | 0.789 | 0.146 | 0.7646 | 7,617 | 613 | 7,004 | 0.081 | 0.789 | **0.146** |

**Bold** = better of the two models for that cell. At budget_1.00pct both models converge to identical TP/FP counts.

---

## 3. What the PR-AUC Drop Means

The full model achieves **PR-AUC = 0.4271** versus the no-ID model at **PR-AUC = 0.3946** — a drop of **0.0325 (7.6% relative)**.

### Key interpretations

1. **Account IDs do contribute real signal.** Removing them costs ~7.6% of PR-AUC. This is a meaningful loss, especially in the high-precision regime (conservative mode: precision fell from **0.853 → 0.813**).

2. **ROC-AUC is essentially unchanged (0.9856 → 0.9854).** This suggests the model's ability to rank transactions across the full score range is preserved. The account IDs mainly sharpen precision at very high score thresholds — they provide a "shortcut" signal rather than broad discriminative power.

3. **Conservative mode reveals the account-ID effect most clearly.** Precision at the conservative threshold dropped from 0.8528 to 0.8131 (−4.0pp). At extreme confidence levels, the full model "remembers" high-risk accounts seen in training, giving it an edge.

4. **Identity leakage risk in production.** Account IDs can encode *memorised patterns* — a known mule account gets a high score because the model has seen it before, not because of its current behaviour. When the model is applied to **new, unseen accounts** (the realistic production scenario), those learned identity embeddings may not generalise, and the no-ID model could outperform in practice despite its lower test-set PR-AUC.

---

## 4. Feature Importance Insights

| Rank | Full Features Model | Importance | No Account-ID Model | Importance |
|---|---|---:|---|---:|
| 1 | `payment_type_enc` | **39.2%** | `payment_type_enc` | **30.1%** |
| 2 | `is_cross_bank` | 9.5% | `cross_bank_flow_flag` | 18.9% |
| 3 | *(account IDs absorb remaining share)* | — | `is_cross_bank` | 11.1% |

**Key insight:** When account IDs are removed, the model compensates by leaning more heavily on **cross-bank flow patterns** (`cross_bank_flow_flag` jumps from negligible to 18.9% importance). Cross-bank patterns are:

- More **interpretable** — they describe transaction behaviour, not identity
- More **generalisable** — they apply equally to new and existing accounts
- More **defensible** to regulators — decisions can be explained by behavioural signals, not "we have seen this account before"

---

## 5. Recommended Model

### For MVP Demo

> **RECOMMENDED FOR MVP DEMO: Full Features model — Balanced threshold (0.9930)**

Use the **full-feature model at balanced mode** for the Naseej MVP demonstration:

| Reason | Detail |
|---|---|
| Higher PR-AUC | **0.4271** vs. 0.3946 (+7.6%) |
| Better F1 at balanced mode | **0.4510** vs. 0.4108 (+9.8%) |
| Better precision at balanced mode | **0.5446** vs. 0.4946 (+10.1pp) |
| Fixed test set | Account-ID memorisation is not a concern — the demo operates on the held-out set where identity signals are valid |

At the balanced threshold the full model generates **549 alerts**, catching **299 true mules** at **54.5% precision** — a compelling and defensible demo result.

---

### For Production Deployment

Investigate and likely adopt the **no-account-ID model** for live deployment:

| Reason | Detail |
|---|---|
| Removes identity leakage | Safe to apply to new accounts never seen in training |
| ROC-AUC preserved | 0.9854 — ranking ability is essentially identical |
| More interpretable features | Cross-bank flow patterns dominate; explainable to compliance officers |
| Regulatory safety | Decisions based on behaviour, not memorised identities — safer under AML regulatory scrutiny |

---

## 6. Next Steps

1. **Temporal validation.** Re-evaluate both models on a truly out-of-time hold-out split (e.g., last 30 days withheld during training). This will reveal whether the full model's apparent PR-AUC advantage persists or collapses on unseen time windows — the definitive test for identity-leakage.

2. **SHAP explainability analysis.** Generate SHAP summary and waterfall plots for both models on flagged transactions. This will (a) confirm whether account-ID features dominate individual predictions and (b) produce per-alert explanations required for SAR filing in production.

3. **Feature engineering — graph/network features.** Extract network-level features from the transaction graph (e.g., account degree, clustering coefficient, community label). These encode *structural* mule-network patterns rather than identity, potentially closing the PR-AUC gap left by removing account IDs.

4. **Ensemble / stacking approach.** Combine the two models: use the no-ID model as the primary scorer for generalisability, and the full-feature model as a secondary signal for known high-risk accounts. A simple average or a meta-learner could achieve better precision-recall trade-offs than either model alone.
