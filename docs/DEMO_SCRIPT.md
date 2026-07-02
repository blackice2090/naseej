# Naseej — 5-Minute Judge Demo Script

**نسيج | Naseej — privacy-preserving cross-bank AML & fraud intelligence (research prototype).**

> Say up front, once: *"Everything you'll see runs on synthetic AMLworld data —
> zero real PII anywhere. This is a research prototype, PDPL-by-design and a
> SAMA-aligned prototype — not certified, not production-ready."* Then never
> overclaim again.

Two screens: **Demo** (Bank A → Bank B story) and **Investigator** (case queue).
Have the backend running so the live strips light up; if it's offline the demo
still runs on labelled fallbacks.

---

## 0:00 — The problem (30s)

> "Money mules move stolen funds across banks in minutes. No single bank sees
> the whole chain, and they legally can't share raw transactions. So cross-bank
> laundering stays invisible until after the cash-out. Naseej fixes the
> *sharing* problem without sharing any customer data."

---

## 0:30 — Bank A detects (45s)

Click **RUN** on the Demo screen.

> "Bank A is watching live transactions. Watch the left panel: five small
> transfers fan into one account, then a sweep to an international wire — a
> classic mule pattern. Our XGBoost model scores it, and the graph engine
> confirms the fan-in→sweep topology against real rolling-window features."

Point at the **ML Baseline** + **Evaluation Evidence** strips: real model,
PR-AUC primary, honest synthetic-benchmark labelling.

---

## 1:15 — Shared without PII (45s)

> "Here's the key move. Bank A does NOT send the transaction. It generates a
> zero-PII pattern hash — `NSJ_…` — names, accounts, amounts are gone. Only the
> *shape* of the threat crosses the boundary."

Point at the hash panel and the **ZERO PII VERIFIED** label.

---

## 2:00 — Bank B benefits (30s)

> "Bank B receives that hash and matches it against its own traffic. It flags a
> matching accomplice transaction for analyst review — cross-bank intelligence,
> with zero PII exchanged. The cross-bank intelligence strip shows the recall
> lift versus a bank acting alone."

---

## 2:30 — Investigator opens the case (40s)

Switch to the **Investigator** tab. The flagged detection has become a case.

> "Detection is never the end — a human decides. Here's the case queue. Open the
> top case."

Open it. Point at **Why Flagged?**

> "This explanation is SHAP-based on the deployed model, but every value is
> bucketed — `large amount`, `cross-bank`, `unseen account` — never a raw figure.
> PII-safe by construction, and it cites the typology and its limitations."

---

## 3:10 — Analyst decision + feedback (40s)

> "The analyst reviews and decides — say, confirm fraud. Roles are enforced
> server-side; only an MLRO can confirm. Every decision is attributed and
> written to a hash-chained audit log."

Make the decision. Point at the **OUTCOME CAPTURED FOR CALIBRATION DATASET** note.

> "And the outcome is captured as a calibration label — a PII-safe, node-scoped
> record. That's the human-in-the-loop feedback a model would need before anyone
> could even think about calibrating it."

---

## 3:50 — Shadow candidate, monitored not deployed (35s)

Back to the Demo screen. Point at **Candidate Model** + **Shadow Monitoring**.

> "We trained a cleaner candidate on only the parity-clean, non-identity
> features. It runs in *shadow* beside the deployed model — we compare scores,
> track agreement and drift — but it does NOT make decisions and is NOT deployed.
> Calibration here is a *dataset*, not production calibration. We refuse to
> deploy until the evidence justifies it."

---

## 4:25 — Governance evidence (25s)

Point at the **Governance Evidence** strip.

> "Everything I claimed is checkable: zero-PII active, human-in-the-loop active,
> audit trail active, RBAC active, shadow model NOT deployed, calibration dataset
> only, production-ready NO. There's a `/api/demo/governance-evidence` endpoint
> behind this — each item names what it proves and its limitation."

---

## 4:50 — Close (10s)

> "Naseej turns isolated bank silos into a privacy-preserving threat network:
> zero-PII sharing, honest ML, human-in-the-loop governance, and a tamper-evident
> audit trail. PDPL-by-design, SAMA-aligned — a credible prototype for Saudi
> cross-bank AML. Thank you."

---

## If a judge interrupts

- *"Is this production-ready?"* → "No, and we're explicit about that. It's a
  research prototype on synthetic data, not certified."
- *"Is this federated learning?"* → "No — we share pattern *hashes*, not model
  gradients. We don't claim FL."
- *"Did you deploy the new model?"* → "No. It's shadow-only; the deployed model
  is unchanged. We have the monitoring and feedback loop to justify a future
  decision, but we haven't made it."
- *"How do you know there's no PII?"* → "A fail-closed guard rejects PII shapes
  at the boundary, plus the pattern hashes are tested zero-PII. See
  `/api/demo/governance-evidence`."
