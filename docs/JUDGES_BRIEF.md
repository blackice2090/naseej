# نسيج | Naseej — Judges Brief

**Project:** نسيج | Naseej  
**UI Brand:** NASEEJ.AI  
**Track:** Amad Hackathon — FinTech / Fraud Intelligence  
**One-line description:** A privacy-preserving cross-bank fraud intelligence network that detects mule-account patterns using graph analytics, ML risk scoring, and zero-PII pattern sharing.

---

## 1. Executive Summary

**نسيج | Naseej** is a fraud intelligence layer for banks that helps detect and prevent mule-account and AML patterns across financial institutions without sharing customer personal data.

The core problem is that mule-account fraud rarely stays inside one bank. Fraudsters move stolen funds across multiple accounts and institutions, while each bank only sees its own internal activity. At the same time, banks cannot freely share customer names, account numbers, IBANs, national IDs, or other personal data because of privacy and regulatory requirements.

Naseej solves this by allowing each bank to analyze transactions locally, detect suspicious graph patterns, and share only a privacy-safe **Pattern Hash** with the federated network. Other banks can use this hash to identify similar topological fraud patterns before transactions are completed.

The MVP demonstrates this flow:

1. Bank A detects a mule-account pattern.
2. Bank A generates a zero-PII pattern hash.
3. The pattern is shared with the federated network.
4. Bank B receives the pattern.
5. Bank B blocks a matching transaction before execution.

---

## 2. Problem

### The Current Fraud Gap

Banks detect fraud mostly within their own environments. This creates three major problems:

| Problem | Why It Matters |
|---|---|
| Data silos | Each bank sees only part of the mule-account chain |
| Privacy restrictions | Banks cannot share raw customer PII |
| Fast fraud movement | Mule accounts can move money across banks before manual teams react |

### Why Mule Accounts Are Difficult

Mule accounts are often used to receive stolen funds, split them, move them quickly, and send them to external or international destinations. These patterns are not always visible from a single transaction. They become clear when viewed as a network:

- Many sources sending funds to one account
- One account rapidly forwarding funds
- Cross-bank movement
- Short time windows
- Repeated transaction structures
- International or high-risk destination movement

---

## 3. Solution

### What Naseej Does

Naseej provides a privacy-preserving fraud intelligence network for banks.

Instead of sharing customer data, banks share a **fraud pattern fingerprint**.

### Core Concept

```text
Local transaction data stays inside each bank.
Only the fraud pattern hash is shared.
```

### How It Works

| Step | Description |
|---|---|
| 1. Local Detection | Bank A monitors transactions locally |
| 2. Graph Analytics | Suspicious mule-account structure is detected |
| 3. ML Risk Scoring | XGBoost AML model scores the risk |
| 4. Pattern Hashing | The fraud topology is converted into a zero-PII hash |
| 5. Federated Sharing | The hash is sent to the network |
| 6. Cross-bank Prevention | Bank B blocks a matching transaction pattern |

---

## 4. Demo Flow

### Demo Scenario

The demo simulates two banks:

- **Bank A:** Local node where the fraud pattern is first detected
- **Bank B:** Receiving node that ingests the shared pattern hash and prevents a similar attack

### Demo Stages

| Stage | What Happens |
|---|---|
| IDLE | Normal transactions flow in both banks |
| ATTACK | Multiple micro-transfers move into a mule account |
| DETECTED | Bank A identifies a coordinated velocity breach |
| BROADCASTING | Naseej generates and shares a zero-PII pattern hash |
| BLOCKED | Bank B blocks a matching mule transaction |

### Key Demo Message

Naseej does not share the customer, the account, or the IBAN.  
It shares the **pattern of fraud**.

---

## 5. AI / ML Validation

Naseej is not only a visual simulation. The ML validation pipeline was built and tested using a realistic synthetic AML dataset.

### Dataset Used

**IBM Transactions for Anti-Money Laundering (AML)**

This dataset is suitable because it contains:

- Synthetic financial transactions
- AML labels
- Multiple accounts and banks
- Temporal transaction flows
- Graph-based transaction structure
- Severe class imbalance similar to real AML detection

### Dataset Scale Used

| Split | Rows | Laundering Transactions | Ratio |
|---|---:|---:|---:|
| Train | 3,554,834 | 3,624 | 0.102% |
| Validation | 761,751 | 776 | 0.102% |
| Test | 761,751 | 777 | 0.102% |

### Feature Engineering

The model uses transaction and graph-derived features such as:

- Payment type
- Amount
- Cross-bank transfer flag
- Source outgoing transaction count
- Target incoming transaction count
- Account pair history
- Fan-in score
- Fan-out score
- Sweep ratio
- Rapid movement flag
- Time-based velocity features

### Model

| Item | Value |
|---|---|
| Model | XGBoost AML Baseline |
| Use Case | Fraud analyst triage |
| Operating Mode | Balanced |
| Threshold | 0.9930 |
| Primary Metric | PR-AUC |

### Final MVP Metrics

| Metric | Result |
|---|---:|
| PR-AUC | 0.4271 |
| Precision | 54.5% |
| Recall | 38.5% |
| F1 | 0.4510 |
| Alerts Reviewed | 549 |
| Confirmed Mule Patterns | 299 |

### Why PR-AUC Instead of Accuracy?

AML datasets are highly imbalanced. In our test set, only about **0.102%** of transactions are laundering. A model can appear highly accurate by predicting every transaction as legitimate, but that would fail the actual fraud-detection goal.

Therefore, PR-AUC, precision, recall, and F1 are more meaningful than accuracy.

---

## 6. Model Interpretation

### What the Model Proves

The model proves that transaction behavior and graph features can identify mule-account risk under severe imbalance.

### What the Model Is Suitable For

| Use Case | Suitable? | Notes |
|---|---|---|
| Analyst triage | Yes | Best current use case |
| Risk prioritization | Yes | Helps reduce manual review burden |
| Early warning | Yes | Useful for suspicious patterns |
| Automatic blocking in production | Not yet | Requires policy controls and human review |
| Regulatory investigation support | Potentially | Needs explainability and audit workflow |

### Recommended MVP Positioning

Naseej should be presented as:

```text
AI-powered fraud triage and privacy-preserving cross-bank threat intelligence.
```

Not as:

```text
Fully autonomous production blocking.
```

---

## 7. Privacy and Compliance

### Privacy Principle

Naseej is designed around a simple rule:

```text
No raw customer data leaves the bank.
```

### What Is Not Shared

- Customer names
- National IDs
- IBANs
- Raw account numbers
- Phone numbers
- Personal transaction history
- Device identifiers in raw form

### What Is Shared

- A pattern hash
- Fraud topology fingerprint
- Risk typology
- Non-PII threat intelligence

### Compliance Alignment

| Area | Alignment |
|---|---|
| PDPL | Zero-PII sharing by design |
| SAMA Counter-Fraud Direction | Supports proactive early warning |
| Model Governance | Human review and audit trail recommended |
| Privacy-by-design | Local analysis and pattern-level exchange |

---

## 8. Technical Architecture

### MVP Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite |
| Styling | Tailwind CSS |
| Icons | Lucide React |
| ML Model | XGBoost |
| Feature Engineering | Python + Pandas |
| Dataset Format | Parquet |
| Graph Logic | Graph-derived features |
| Demo Simulation | Frontend scripted flow |

### MVP Architecture

```text
Bank A Local Node
    ↓
Local Graph Analytics
    ↓
ML Risk Scoring
    ↓
Zero-PII Pattern Hash
    ↓
Federated Intelligence Network
    ↓
Bank B Pattern Match
    ↓
Transaction Blocked / Analyst Review
```

---

## 9. Business Value

### For Banks

- Earlier detection of mule-account activity
- Better fraud analyst prioritization
- Lower investigation overload
- Cross-bank fraud pattern awareness
- Reduced dependency on static rules
- Privacy-safe collaboration

### For Regulators

- Stronger ecosystem-level fraud intelligence
- Privacy-preserving monitoring
- Better visibility into emerging typologies
- Supports responsible AI and model governance

### For Customers

- Better protection against social engineering scams
- Reduced fraud loss exposure
- More secure digital banking experience
- Less need for broad data sharing

---

## 10. Why Now?

Saudi banking is rapidly moving toward digital channels, instant payments, open banking, and fintech innovation. This increases speed and convenience, but also gives fraudsters faster paths to move funds.

Naseej addresses this by combining:

- AI-based detection
- Graph analytics
- Privacy-preserving collaboration
- Cross-bank intelligence
- Human-centered fraud review

---

## 11. Differentiation

| Traditional Fraud System | Naseej |
|---|---|
| Works inside one bank | Connects fraud intelligence across banks |
| Often rule-based | Uses ML risk scoring and graph features |
| May require manual investigation | Prioritizes alerts for analysts |
| Limited cross-bank view | Shares zero-PII pattern intelligence |
| Customer data sharing is risky | Shares only pattern hashes |

---

## 12. Roadmap

### Phase 1 — Hackathon MVP

- Frontend simulation
- Graph-based demo
- Pattern hash sharing
- ML validation metrics
- Judge-ready dashboard

### Phase 2 — Pilot Prototype

- Backend API
- Case management workflow
- Real-time transaction ingestion
- Explainability layer
- Audit logs
- Configurable thresholds

### Phase 3 — Controlled Banking Pilot

- Tokenized bank data
- Out-of-time validation
- Human review workflow
- SHAP explanations
- Model monitoring

### Phase 4 — Production Path

- SAMA sandbox exploration
- Privacy-preserving model updates
- Federated learning experiments
- Multi-bank threat intelligence exchange
- Governance and compliance documentation

---

## 13. Key Risks and Mitigation

| Risk | Mitigation |
|---|---|
| False positives | Use analyst triage and configurable thresholds |
| Privacy concerns | Share only zero-PII pattern hashes |
| Model overfitting | Temporal validation and no-ID model comparison |
| Regulatory concerns | Human review, audit logs, explainability |
| Integration complexity | Start with API-based pilot and simulated feeds |
| Trust from fraud teams | Explainable reason codes and case review workflow |

---

## 14. What We Will Say If Asked

### Is this real federated learning?

The MVP simulates federated intelligence at the pattern-sharing level. Production federated learning would be a future phase. The current MVP proves the most important concept: banks can collaborate without sharing PII.

### Is the model real?

Yes. The ML validation pipeline was built using the IBM AML dataset. We trained an XGBoost baseline and evaluated it on a held-out test set.

### Does Naseej share customer data?

No. Naseej shares only a pattern hash. Raw customer data remains inside the bank.

### Can it block transactions automatically?

The demo shows a block for storytelling. In production, we recommend analyst triage, step-up verification, delayed release, or policy-based review before hard blocking.

### Why is this useful if recall is not 100%?

Fraud systems do not need to replace investigators. They need to prioritize the riskiest cases. Naseej reduces review volume and surfaces high-risk mule-account patterns earlier.

---

## 15. One-Minute Pitch

السلام عليكم، نقدم لكم **نسيج | Naseej**، شبكة ذكاء احتيال تحفظ الخصوصية بين البنوك.

المشكلة أن حسابات الوسيط تتحرك بين أكثر من بنك بسرعة، وكل بنك يرى جزءًا فقط من الصورة. وفي نفس الوقت، لا يمكن مشاركة بيانات العملاء بسبب متطلبات الخصوصية والامتثال.

نسيج يحل هذه الفجوة. كل بنك يحلل عملياته محليًا باستخدام Graph Analytics وMachine Learning. وعند اكتشاف نمط احتيال، لا نرسل اسم العميل ولا رقم الحساب ولا أي بيانات شخصية. نرسل فقط Pattern Hash يمثل نمط الاحتيال.

في الديمو، Bank A يكتشف عدة تحويلات صغيرة إلى حساب Mule ثم تحويل دولي. النظام يولد Hash بدون PII. Bank B يستقبل نفس النمط ويمنع عملية مشابهة قبل تنفيذها.

تحققنا من الفكرة باستخدام IBM AML synthetic dataset بأكثر من 5 ملايين معاملة، ودربنا نموذج XGBoost حقق PR-AUC يساوي 0.4271 في بيئة شديدة الصعوبة بنسبة احتيال 0.102%.

نسيج ليس مجرد Dashboard. هو طبقة تعاون ذكية بين البنوك لكشف الاحتيال مع الحفاظ على الخصوصية والامتثال.

---

## 16. Closing Statement

Naseej does not ask banks to expose their customer data.

Naseej allows banks to collaborate through privacy-safe fraud pattern intelligence.

The result is faster detection, stronger privacy, and a safer financial ecosystem.

---
