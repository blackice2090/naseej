# Candidate Calibration Readiness (SHADOW ONLY)

- Generated: 2026-06-13T16:56:41Z  ·  Calibrated for production: **False**  ·  Deployment recommended: **False**

The shadow candidate is NOT calibrated for production. Live shadow scoring produces no ground-truth labels, so candidate probabilities cannot be calibrated and no threshold can be validated against real outcomes. Shadow monitoring is comparison/observation only.

## Needed for calibration
- Labeled outcomes (confirmed fraud / confirmed legitimate) for shadow-scored transactions.
- Out-of-time validation on real (non-synthetic) supervised data under SAMA governance.
- Threshold tuning against those labels (precision/recall operating points re-derived on real data).
- An analyst feedback loop feeding confirmed dispositions back into evaluation.
- Drift monitoring on real distributions (the prototype drift signal is not sufficient).
- A SAMA-governed pilot validation with a documented rollback + human-in-the-loop plan.

## Drift status

Only a PROTOTYPE drift signal exists, computed from bucketed synthetic shadow observations. It is a coarse early-warning aid, not statistical production monitoring.

> SHADOW ONLY — no real labels in live shadow mode, no deployment recommendation. The deployed model, scoring endpoint, and explainability endpoints are unchanged.
