# Demo Script — نسيج | Naseej (Research Version)

**Audience:** Hackathon judges · Technical reviewers  
**Versions:** 3-minute (quick pitch) + 5-minute (full technical walkthrough)  
**Honest framing throughout:** Research prototype on synthetic data.

---

## Before You Start

**Have open on your screen:**
1. Browser tab: `http://localhost:5173` — the Naseej demo at IDLE stage
2. Terminal (hidden, running the backend on :8000) — so the API status dot shows **● LIVE**
3. This script on your phone or a second screen

**Check:** The research strip below the ML Validation card should show the cross-bank recall bars and the **● API LIVE** indicator. If not, the demo still works — fallback values are shown.

---

## 3-Minute Version

*Use for quick-pitch rounds, hallway conversations, or opening 5 minutes of a longer session.*

---

**[0:00 — PROBLEM]** *(30 seconds)*

> "Money-laundering mule accounts don't stay inside one bank. They move across institutions in coordinated chains that no single bank can fully see. At the same time, privacy law — Saudi PDPL and SAMA rules — prevents banks from freely sharing customer data. So banks are blind to cross-bank fraud patterns by design."

---

**[0:30 — SOLUTION CONCEPT]** *(30 seconds)*

> "Naseej solves this without sharing any customer data. When Bank A detects a suspicious transaction topology, it generates a cryptographic pattern hash — a fingerprint of the fraud shape, not the identity of the people involved. Bank B receives the hash and can immediately identify matching patterns."

Point to the research strip:

> "These are live numbers from our XGBoost model and our cross-bank experiment. Private banks catch 39% recall. When they share through Naseej pattern hashes, that rises to 67% — a 28-percentage-point gain, with zero PII crossing the bank boundary."

---

**[1:00 — DEMO]** *(60 seconds)*

Click **RUN SIMULATION**.

> "Watch Bank A's feed. Five micro-transfers are fanning into a mule account — this is the classic fan-in aggregation pattern before an international wire sweep."

*[ATTACK → DETECTED stage fires at ~2.5s]*

> "Graph analytics detected it. The mule node is highlighted. Now watch what happens next."

*[BROADCASTING stage — hash typewriter decodes, particles flow A→B]*

> "That hash is an NSJ pattern signature. It encodes the fraud topology — degree sequences, amount tiers, pattern type — but not a single account ID, name, or IBAN. Zero PII."

*[BLOCKED stage]*

> "Bank B matched the pattern and blocked an accomplice transaction before it executed. That's zero-day cross-bank fraud prevention."

---

**[2:00 — PROOF POINTS]** *(45 seconds)*

> "This is a research prototype, not a product claim. But the technical validation is real."

Point to the ML Validation card at the top:

> "XGBoost trained on 300,000 transactions from IBM's AMLworld synthetic AML dataset. PR-AUC of 0.23, ROC-AUC of 0.95. We use PR-AUC because at 0.1% laundering prevalence, accuracy is meaningless — a model that calls everything safe gets 99.9% accuracy and catches nothing."

Point to the cross-bank bars in the research strip:

> "Our cross-bank experiment ran three scenarios across 4 simulated banks. Private-only recall: 39%. Naseej pattern sharing: 67%. Five times the recall gain of simply pooling raw data."

---

**[2:45 — CLOSE]** *(15 seconds)*

> "Naseej proves the concept that works at the hardest part of the problem — the privacy constraint. Banks don't need to share customers. They need to share the shape of fraud. Thank you."

---

## 5-Minute Version

*Use for main judging sessions and technical review panels.*

---

**[0:00 — PROBLEM]** *(45 seconds)*

> "I want to start with a simple observation: mule-account fraud networks don't care about bank boundaries. A stolen fund arrives at Bank A, gets split to five micro-accounts, moves to a collector at Bank B, then sweeps internationally — all within a few minutes."

> "Each bank sees only its own slice. Bank A sees some micro-transfers. Bank B sees an incoming wire. Neither sees the full chain."

> "The natural solution — share the data — is blocked by SDAIA PDPL and SAMA confidentiality rules. And even if it weren't, pooling millions of transaction records creates massive privacy and security risks."

> "So the question Naseej answers is: can banks collaborate on fraud without sharing customer data at all?"

---

**[0:45 — WHAT NASEEJ DOES]** *(45 seconds)*

> "The answer is: share the pattern, not the data."

Draw attention to the research strip → cross-bank section:

> "When Bank A detects a suspicious topology — let's say five sources fanning into one mule account in sixty minutes — it runs our pattern hash engine. The engine strips every PII field: no names, no IBANs, no national IDs, no account numbers. It then bucketes the continuous values — 7,500 SAR becomes 'small-amount-tier' — and SHA-256 hashes the canonical JSON of the pure topology."

> "The output is a 16-hex NSJ signature. Bank B receives that signature. If Bank B sees the same topology — different accounts, similar amounts — its local engine produces the same hash. Pattern matched. Transaction flagged."

---

**[1:30 — RUN THE DEMO]** *(90 seconds)*

Point to screen.

> "Let me show you the flow. Both banks are currently in IDLE — processing normal transactions."

Click **RUN SIMULATION**.

> "A mule-account attack is now running in Bank A. Watch the transaction feed: five micro-transfers from different sources, all flowing to the same mule account. Then a sweep — eleven-thousand SAR — to an international destination."

*[ATTACK stage — watch transaction feed]*

> "The attack sequence maps exactly to the fan-in → rapid-sweep AML typology: aggregate, collect, move."

*[DETECTED stage fires — mule node turns red, alert banner appears]*

> "Graph analytics caught it. The mule node is pulsing red. Now look at the Pattern Analysis panel in the research strip — it's filling in live from our backend."

*[BROADCASTING stage — hash decodes, particles flow]*

> "The hash is generating. NSJ-mule-velocity — no account IDs, no names, just the structural fingerprint. The particles you see represent the federated broadcast from Bank A to Bank B."

> "The pattern hash at the bottom: that's the actual output of our privacy_hash engine running server-side. Formally proved zero-PII by 136 automated tests."

*[BLOCKED stage — stamp appears]*

> "Bank B matched the pattern and blocked the accomplice transaction — preemptively, before execution. That's the core value proposition."

Click **RESET DEMO**.

---

**[3:00 — TECHNICAL VALIDATION]** *(60 seconds)*

Point to MLValidationCard.

> "The model is real. We trained XGBoost on the IBM AMLworld HI-Small dataset — 475 megabytes of synthetic AML transactions, 5 million rows, 0.1% laundering prevalence. That prevalence is realistic for real banking environments."

> "PR-AUC of 0.23, ROC-AUC of 0.95. We chose XGBoost over logistic regression and random forest because it had the best PR-AUC on the validation set. Threshold is optimised by F1 on the validation split."

Point to cross-bank bars.

> "The cross-bank experiment is the most important number. We split the dataset across 4 simulated banks, trained XGBoost under three scenarios: private only, pooled raw features, and Naseej pattern sharing. Private recall: 39%. Shared raw data: 44%. Naseej: 67%. That's a 28-percentage-point gain over private-only — achieved with zero raw data sharing."

> "For context: our pattern hash approach delivers 500% of the recall gain that raw data pooling achieves, at zero privacy cost."

---

**[4:00 — PRIVACY PROOF]** *(30 seconds)*

> "Privacy isn't a claim here. We prove it in 136 automated tests. Every field in our PII registry — names, IBANs, national IDs, phones, emails, account numbers, IP addresses — is formally tested to ensure it never appears in any hash or API response."

> "The central test: Bank A identifies a mule account as ACC-MULE-SA-001. Bank B identifies the same account pattern as IBAN SA44-2000-0001-2345. After normalisation, both produce an identical hash. The topology matches. The identities don't cross the boundary."

---

**[4:30 — CLOSE]** *(30 seconds)*

> "Naseej is a research prototype. We're not claiming production readiness. But we have demonstrated three things that are technically hard to do simultaneously: cross-bank fraud detection, zero customer PII exposure, and measurable recall improvement — all in a single system."

> "The path to production is clear: feature store for velocity features, tokenised real data with SAMA supervision, and a federated learning layer. The privacy architecture is already there. Thank you."

---

## Key Talking Points (Quick Reference)

| Topic | Key sentence |
|-------|-------------|
| The problem | "Each bank sees one slice. Fraud crosses all of them." |
| The solution | "Share the pattern, not the data." |
| How the hash works | "Strip PII → bucket values → SHA-256 canonical JSON → 16-hex signature." |
| Cross-bank result | "67% recall vs 39% private-only. +28 pp. Zero PII shared." |
| Model | "XGBoost, PR-AUC 0.23, trained on 300k rows of IBM AMLworld." |
| Data | "Synthetic AML dataset — not real banking data. Research prototype." |
| Privacy proof | "136 automated tests. Every PII field formally excluded." |
| Production gap | "Feature store, tokenised real data, federated learning, SAMA supervision." |

---

## What to Show on Screen at Each Stage

| Moment | Point to |
|--------|---------|
| Opening | Research strip → cross-bank recall bars; API ● LIVE dot |
| IDLE | Transaction feed — normal activity |
| ATTACK | TX feed — micro-transfers flagging CLEAR → FLAGGED |
| DETECTED | Mule node (red, pulsing); alert banner; Pattern Analysis panel filling in |
| BROADCASTING | Hash typewriter decoding; particle flow A→B; LiveScoreSection |
| BLOCKED | BLOCKED stamp; Bank B shake; confirmed detection |
| After demo | ML Validation card metrics; cross-bank recall comparison |

---

## How to Explain the ML Metrics

**If a judge asks: "Why is recall only 20%?"**

> "Good question. The threshold is set to maximise F1 on the validation set — which balances precision and recall. At lower thresholds we get higher recall but many more false alerts. At higher thresholds we get fewer alerts but miss more cases. For analyst triage, 33 alerts catching 9 confirmed laundering cases is a useful prioritisation signal, not a complete detection system. In the cross-bank experiment, Naseej recall reaches 67% because the cross-bank features give the model visibility into patterns that the local model simply can't see."

**If a judge asks: "Why is PR-AUC only 0.23?"**

> "PR-AUC is hard to achieve at 0.1% prevalence. A random classifier would get 0.001. Our XGBoost at 0.23 represents meaningful signal — it's roughly 230× better than random under the PR curve. The primary value is risk prioritisation, not autonomous blocking."

**If a judge asks: "Have you validated this on real data?"**

> "No — and we're transparent about that. AMLworld is a high-quality synthetic benchmark, but performance on real Saudi banking transactions is unknown. That validation would require SAMA-supervised data-sharing agreements and out-of-time testing on real transaction flows. We've designed the system so that plugging in a real data source doesn't require architectural changes."

---

## How to Explain Zero PII

**One-sentence version:**

> "The hash encodes the shape of the fraud — how many transactions, in what direction, in what amount tiers — but never the name, IBAN, or account number of any person."

**Technical version:**

> "Our privacy_hash engine strips 25 PII field types before hashing. It then buckets continuous values — 7,800 SAR becomes 'small' — so minor cross-bank differences don't prevent matching. The result is a SHA-256 hash of the canonical JSON of the pure fraud topology. We formally prove this property in 136 automated tests: every category of PII field causes verify_zero_pii() to return False."

**If a judge challenges: "Couldn't the hash be reversed?"**

> "Not in a useful way. SHA-256 is a one-way function. The pre-image would be the bucketed, PII-stripped topology — which contains no customer identifiable data even before hashing. What you'd reconstruct is the pattern shape, not any individual's information."

---

## Likely Judge Questions and Answers

| Question | Answer |
|----------|--------|
| Is this federated learning? | "The pattern-sharing concept is inspired by federated learning principles. The current MVP simulates the federation in the frontend. Production FL would use Flower or OpenFL with gradient aggregation. We've designed the hash schema to be compatible with future FL integration." |
| What's the business model? | "SaaS network layer for participating banks — subscription per institution, tiered by transaction volume. Or a central infrastructure model operated by a neutral body like SAMA's fintech sandbox." |
| Who owns the hash network? | "In the MVP, it's simulated locally. In production, a neutral governance body — potentially SAMA or an industry consortium — would operate the secure aggregator. No single bank controls the network." |
| How do you prevent false positives? | "Configurable thresholds per operating mode (Conservative / Balanced / Aggressive) visible in the ML Validation card. Analyst review before any hard block in production. SHAP explainability is on the roadmap for every alert." |
| Is this patentable? | "The combination of topology-only pattern hashing with cross-bank federated recall improvement is a novel research contribution. Formal IP analysis hasn't been conducted yet." |
| Why XGBoost and not a neural network? | "For a 0.1% prevalence AML problem with 32 tabular features, gradient-boosted trees are state-of-the-art. A Graph Neural Network baseline is on the roadmap — initial tests showed similar or marginally better PR-AUC on transaction subgraphs, but at far higher infrastructure cost." |
| What happens when a bank leaves the network? | "Their previously broadcast hashes remain valid for other banks. Future transactions from that bank stop flowing in. Hash revocation is a future governance question." |

---

## Closing Statement (for any length)

> "Naseej does not ask banks to expose their customer data. It asks them to share the shape of fraud they've already seen. The result is faster detection, stronger privacy, and a safer financial ecosystem — without violating a single regulatory requirement."

---

*Script version: Phase 10. All numbers sourced from live reports in `ml/reports/`. Cross-bank figures from `cross_bank_results.json`. Model metrics from `model_metrics.json`.*
