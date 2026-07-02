# نسيج | Naseej Pitch Deck Content Guide

**Project:** نسيج | Naseej  
**Team:** Madar  
**Event:** AMAD Hackathon | FinTech Track  
**Purpose:** This file is the single source of truth for building and reviewing the pitch deck content. It includes the approved bilingual slide copy, design direction, visual suggestions, and Claude review prompts.

---

## 0. Global Deck Rules | قواعد عامة للعرض

1. Keep every slide bilingual Arabic-English.
2. Keep the wording concise. The slides should look premium, not text-heavy.
3. Arabic comes first when the slide title is bilingual, then English.
4. Use the project name consistently: **نسيج | Naseej**.
5. Use the team name consistently: **Team Madar | فريق مدار**.
6. Do not use **MuleHunter.AI** as the project name. Use “mule account” only as a fraud typology.
7. Do not claim the MVP is a production banking system. It is a validated hackathon MVP / research prototype.
8. Keep technical metrics as **MVP validation baseline signals**, not production performance claims.
9. Maintain a premium dark fintech design: deep navy/black background, subtle graph/network lines, blue/violet accents, green for privacy/prevention, red only for fraud risk.
10. Do not overcrowd slides. Details belong in the presenter speech, not the visual deck.
11. **Metric-sync rule (important):** Any ML number shown in the deck must exactly mirror the deployed baseline report `ml/reports/model_metrics.json`. Never show older or inflated values. The current honest baseline is **PR-AUC 0.2275 · Precision 27.3% · Recall 19.6% · F1 0.2278** (threshold 0.0606, 33 alerts, 9 confirmed on 45,001 synthetic test transactions). If the report changes, update the deck.
12. **No “federated learning” claim.** The mechanism is privacy-preserving **pattern-hash sharing**, not federated learning. Describe it as shared pattern intelligence. “Federated learning” may appear only as an explicitly future/exploratory direction, never as a current capability.
13. The project’s strongest message is:

> **البيانات تبقى داخل البنك. الذكاء ينتقل بين البنوك.**  
> **Data stays inside the bank. Intelligence moves across banks.**

---

## Recommended Final Deck Structure | هيكلة العرض النهائية المقترحة

The original template has 14 slides. This content guide keeps the original flow and adds one credibility slide plus optional demo sub-slides.

| Final # | Slide | Notes |
|---|---|---|
| 01 | Cover | اسم المشروع والفريق |
| 02 | Team Members | أعضاء الفريق |
| 03 | Agenda | المحتويات كما في القالب |
| 04 | Problem & Solution | من أهم الشرائح |
| 05 | Data Used | حسب تسلسل القالب |
| 06 | Technologies Used | حسب تسلسل القالب |
| 07 | Idea Overview | من أهم الشرائح |
| 08 | Data Sourcing & Usage | حسب القالب |
| 09 | Idea Alignment | مواءمة الفكرة |
| 10 | Backed by Science & Regulation | شريحة إضافية موصى بها |
| 11 | Summary | الملخص |
| 12 | Validation | الاختبار / التحقق |
| 13-A | Demo Preview | صورة واجهة كاملة |
| 13-B | Simulation Flow | 4 صور لمراحل المحاكاة |
| 13-C | Demo Video | فيديو / QR / رابط |
| 14 | Challenges & Future Plans | التحديات والخطط المستقبلية |
| 15 | Thank You | شكر وختام |

> If the deck must stay short, merge 13-A, 13-B, and 13-C into one demo slide. The preferred version is to keep them as three visual slides because they rely on screenshots/video, not heavy text.

---

# Slide 01 — Cover

## Title

**نسيج | Naseej**

## Subtitle

**شبكة ذكاء احتيالي تحفظ الخصوصية بين البنوك السعودية**  
**Privacy-Preserving Fraud Intelligence Network for Saudi Banks**

## Value Line

**اكتشاف أنماط حسابات الاحتيال بين البنوك دون كشف بيانات العملاء**  
**Detecting cross-bank mule account patterns without exposing customer PII**

## Footer

**فريق مدار | Team Madar**  
**AMAD Hackathon | FinTech Track**

## Design Direction

- Make **نسيج | Naseej** the visual hero.
- Use a dark premium fintech background.
- Add subtle connected nodes behind the title.
- Add a soft glowing line representing a privacy-safe intelligence signal moving between banks.
- Do not add paragraphs.

## Presenter Script

Today, we are presenting Naseej, a privacy-preserving fraud intelligence network for Saudi banks. Naseej helps banks detect mule account patterns locally, share only an anonymous pattern hash, and prevent similar fraud attempts across the banking network without exposing customer data.

---

# Slide 02 — أعضاء الفريق | Team Members

## Title

**فريق مدار | Team Madar**

## Content

| Name | Role |
|---|---|
| **OBAID ALMUTAIRI** | Founder & Product Lead |
| **AMAL ALMUTAIRI** | AI / Data Lead |
| **SADEEM ALMUTAIRI** | UI/UX Designer |
| **ASEEL ALMUTAIRI** | Full-Stack Developer |
| **ABDULLMALIK ALMUTAIRI** | Business & Partnerships Lead |

## Footer Line

**فريق يجمع المنتج، الذكاء الاصطناعي، التصميم، التطوير، والشراكات**  
**A team combining product, AI, design, engineering, and partnerships**

## Design Direction

- Use five clean member cards.
- Put the name in bold uppercase.
- Put the role below in smaller text.
- Keep the slide elegant and clean.

---

# Slide 03 — المحتويات | Agenda

## Title

**المحتويات | Agenda**

## Content

The agenda follows the actual deck flow (Problem → Data → Technologies → Idea → Alignment → Validation → Summary), grouped so the slide stays uncrowded.

| # | العربية | English |
|---|---|---|
| 01 | أعضاء الفريق | Team Members |
| 02 | المشكلة والحل | Problem & Solution |
| 03 | البيانات والتقنيات | Data & Technologies |
| 04 | وصف الفكرة | Idea Overview |
| 05 | المواءمة والمصداقية | Alignment & Credibility |
| 06 | التحقق والعرض التوضيحي | Validation & Demo |
| 07 | الملخص والخطوات القادمة | Summary & Next Steps |

## Design Direction

- Keep the agenda close to the original template.
- Keep the order aligned with the actual slide flow.
- Avoid adding unnecessary topics.
- Use clear numbering and generous spacing.

---

# Slide 04 — المشكلة وحلّها | Problem & Solution

## Main Headline

**المشكلة ليست في كشف الاحتيال داخل بنك واحد**  
**The real challenge is detecting fraud across banks**

## Problem Section

**الاحتيال يتحرك بين البنوك أسرع من أنظمة المراقبة المنعزلة.**  
**Fraud moves across banks faster than isolated monitoring systems.**

- **كل بنك يرى جزءًا من الشبكة فقط**  
  **Each bank sees only part of the network**

- **مشاركة بيانات العملاء غير ممكنة قانونيًا**  
  **Customer PII cannot be legally shared**

- **حسابات وسيطة تخفي مسار الأموال**  
  **Mule accounts hide the money trail**

## Solution Section

**نسيج يحوّل نمط الاحتيال إلى ذكاء مشترك بدون كشف البيانات.**  
**Naseej turns fraud patterns into shared intelligence without exposing data.**

- **اكتشاف محلي داخل البنك**  
  **Local detection inside each bank**

- **مشاركة Hash للنمط فقط**  
  **Only the pattern hash is shared**

- **منع مبكر عبر الشبكة**  
  **Early prevention across the network**

## Footer Statement

**من بيانات معزولة إلى ذكاء احتيالي مشترك وآمن**  
**From isolated data to secure shared fraud intelligence**

## Visual Layout

Split the slide into two halves:

Left side: **Problem | المشكلة**
- Darker area.
- Broken / isolated bank nodes.
- Three compact problem cards.

Right side: **Solution | الحل**
- Connected bank nodes.
- One glowing line called **Naseej Pattern Hash**.
- Cards for local detection, pattern hash, and early prevention.

Suggested visual flow:

**Bank A** → Transactions → Suspicious Mule Pattern → **Pattern Hash**  
**Zero PII Shared**  
**Bank B** → Hash Match → Transaction Blocked

## Presenter Script

Today, banks are not only fighting fraud inside their own systems. The real problem is that mule account networks move across banks, while each bank sees only a small part of the pattern. Naseej solves this by letting each bank detect suspicious behavior locally, convert the pattern into a privacy-safe hash, and share that intelligence with the network. So other banks can prevent the same fraud pattern before it happens, without exposing customer PII.

---

# Slide 05 — البيانات المستخدمة | Data Used

## Main Headline

**بيانات اصطناعية آمنة لإثبات الفكرة**  
**Synthetic, privacy-safe data for MVP validation**

## Data Types

### 1. سجلات تحويلات مالية  
**Financial transaction records**  
Amount, time, source, destination, bank ID

### 2. علاقات شبكية بين الحسابات  
**Account relationship graph**  
Nodes = accounts, Edges = transfers

### 3. أنماط احتيال محاكية  
**Simulated mule patterns**  
5 micro-transfers + international sweep

### 4. بصمة نمط آمنة  
**Privacy-safe pattern hash**  
Shared intelligence, zero customer PII

## Footer Statement

**لم نستخدم أي بيانات عملاء حقيقية في النموذج الأولي**  
**No real customer data was used in the MVP**

## Visual Layout

Create a simple data flow:

**Synthetic Transactions** → **Graph Mapping** → **Mule Pattern Detection** → **Pattern Hash**

Add a strong privacy badge:

**0 Real PII**  
**صفر بيانات شخصية حقيقية**

## Claude Design Prompt

```text
Create slide 05 for a bilingual Arabic-English hackathon pitch deck.

Project: نسيج | Naseej
Team: Madar
Slide title:
البيانات المستخدمة | Data Used

Design style:
Premium dark fintech style, clean and minimal, matching a privacy-preserving AI banking platform. Use deep navy/black background, subtle graph lines, blue and violet accents, green for privacy/safe indicators, and red only for suspicious fraud signals. Keep the slide elegant with strong spacing and no clutter.

Slide content:
Main headline:
بيانات اصطناعية آمنة لإثبات الفكرة
Synthetic, privacy-safe data for MVP validation

Create four small data cards:
1. سجلات تحويلات مالية
   Financial transaction records
   Amount, time, source, destination, bank ID

2. علاقات شبكية بين الحسابات
   Account relationship graph
   Nodes = accounts, Edges = transfers

3. أنماط احتيال محاكية
   Simulated mule patterns
   5 micro-transfers + international sweep

4. بصمة نمط آمنة
   Privacy-safe pattern hash
   Shared intelligence, zero customer PII

Add a strong footer statement:
لم نستخدم أي بيانات عملاء حقيقية في النموذج الأولي
No real customer data was used in the MVP

Visual layout:
Show a simple flow from left to right:
Synthetic Transactions → Graph Mapping → Mule Pattern Detection → Pattern Hash
On the right side, add a large privacy badge:
0 Real PII
صفر بيانات شخصية حقيقية

Keep all text readable, bilingual, and concise. Do not add extra paragraphs.
```

---

# Slide 06 — التقنيات المستخدمة | Technologies Used

## Main Headline

**تقنيات خفيفة لإثبات فكرة ثقيلة**  
**Lightweight stack for a high-impact fraud intelligence demo**

## MVP Stack | تقنيات النموذج الأولي

### React + Vite  
واجهة تفاعلية سريعة  
Fast interactive prototype

### Tailwind CSS  
تصميم FinTech داكن واحترافي  
Dark professional fintech UI

### Lucide React  
أيقونات واضحة للحماية والشبكات  
Clean security & network icons

### CSS / SVG Graph  
تمثيل العلاقات بين الحسابات  
Account relationship visualization

## Intelligence Layer | طبقة الذكاء

### Graph Analytics  
كشف العلاقات وأنماط حسابات Mule  
Detect mule-account relationships

### Pattern Hashing  
مشاركة بصمة النمط فقط  
Share only the pattern signature

### Privacy-Safe Sharing  
ذكاء مشترك بدون نقل بيانات العملاء  
Shared intelligence without moving customer data

### Rule-Based Simulation  
محاكاة مباشرة لمسار الهجوم والمنع  
Live simulation of attack and prevention

## Footer Statement

**النموذج لا يثبت التقنية فقط، بل يثبت طريقة التعاون الآمن بين البنوك**  
**The MVP proves not only the technology, but the secure collaboration model**

## Visual Layout

Place **Naseej Core** in the center. Surround it with four technology layers:

1. **Interface Layer** — React + Tailwind
2. **Graph Layer** — CSS/SVG + Nodes/Edges
3. **Privacy Layer** — Pattern Hash + Zero PII
4. **Intelligence Layer** — Graph Analytics + Pattern-Hash Sharing

## Claude Design Prompt

```text
Create slide 06 for a bilingual Arabic-English hackathon pitch deck.

Project: نسيج | Naseej
Team: Madar
Slide title:
التقنيات المستخدمة | Technologies Used

Design style:
Premium dark fintech design, clean, minimal, elegant. Use deep navy/black background with subtle graph lines. Use blue for interface, violet for intelligence, green for privacy/safe, and red only for risk signals. Keep the slide visually strong and uncluttered.

Main headline:
تقنيات خفيفة لإثبات فكرة ثقيلة
Lightweight stack for a high-impact fraud intelligence demo

Create two clean sections:

Section 1:
MVP Stack | تقنيات النموذج الأولي

Cards:
1. React + Vite
واجهة تفاعلية سريعة
Fast interactive prototype

2. Tailwind CSS
تصميم FinTech داكن واحترافي
Dark professional fintech UI

3. Lucide React
أيقونات واضحة للحماية والشبكات
Clean security & network icons

4. CSS / SVG Graph
تمثيل العلاقات بين الحسابات
Account relationship visualization

Section 2:
Intelligence Layer | طبقة الذكاء

Cards:
1. Graph Analytics
كشف العلاقات وأنماط حسابات Mule
Detect mule-account relationships

2. Pattern Hashing
مشاركة بصمة النمط فقط
Share only the pattern signature

3. Privacy-Safe Sharing
ذكاء مشترك بدون نقل بيانات العملاء
Shared intelligence without moving customer data

4. Rule-Based Simulation
محاكاة مباشرة لمسار الهجوم والمنع
Live simulation of attack and prevention

Footer statement:
النموذج لا يثبت التقنية فقط، بل يثبت طريقة التعاون الآمن بين البنوك
The MVP proves not only the technology, but the secure collaboration model

Visual layout:
Put “Naseej Core” in the center, surrounded by four technology layers:
Interface Layer, Graph Layer, Privacy Layer, Intelligence Layer.
Keep bilingual text short, readable, and aligned.
Do not add extra paragraphs.
Do not use the term “federated learning”; describe the mechanism as privacy-safe pattern-hash sharing.
```

---

# Slide 07 — وصف الفكرة | Idea Overview

## Main Headline

**نسيج: طبقة ذكاء مشتركة فوق أنظمة الاحتيال البنكية**  
**Naseej: A shared intelligence layer above bank fraud systems**

## Core Idea

**نسيج يمكّن البنوك من التعاون ضد أنماط الاحتيال دون تبادل بيانات العملاء.**  
**Naseej enables banks to collaborate against fraud patterns without exchanging customer data.**

## How It Works | كيف تعمل؟

### 1. يكتشف البنك النمط محليًا  
**Detect the pattern locally**

### 2. يحوّله إلى بصمة آمنة  
**Convert it into a privacy-safe hash**

### 3. يشارك البصمة عبر الشبكة  
**Share the hash across the network**

### 4. يمنع بنك آخر النمط نفسه مبكرًا  
**Prevent the same pattern in another bank**

## Core Value | القيمة

**البيانات تبقى داخل البنك. الذكاء ينتقل بين البنوك.**  
**Data stays inside the bank. Intelligence moves across banks.**

## Visual Layout

Create a clean concept model:

**Bank A** → **Local Detection** → **Pattern Hash** → **Naseej Intelligence Layer** → **Bank B** → **Early Prevention**

Add a badge:

**Zero PII Shared**  
**لا مشاركة لبيانات العملاء**

## Presenter Script

نسيج ليس نظام كشف احتيال تقليدي داخل بنك واحد. نسيج هو طبقة ذكاء مشتركة تسمح للبنوك بالتعلم من أنماط الاحتيال لدى بعضها دون كشف بيانات العملاء. عندما يكتشف بنك نمطًا خطيرًا، لا يرسل أسماء أو أرقام حسابات، بل يرسل بصمة آمنة للنمط. بهذه الطريقة، يتحول الاحتيال من تهديد ينتقل بين البنوك إلى معرفة أمنية تنتقل أسرع منه.

## Claude Design Prompt

```text
Create slide 07 for a bilingual Arabic-English hackathon pitch deck.

Project:
نسيج | Naseej

Team:
Madar

Slide title:
وصف الفكرة | Idea Overview

Design style:
Premium dark fintech design, elegant and minimal. Use deep black/navy background, subtle banking network lines, blue for Bank A, violet for Naseej intelligence layer, green for privacy and prevention, red only for fraud signals. The slide should look like a serious national fintech security concept, not a generic startup slide.

Main headline:
نسيج: طبقة ذكاء مشتركة فوق أنظمة الاحتيال البنكية
Naseej: A shared intelligence layer above bank fraud systems

Core idea:
نسيج يمكّن البنوك من التعاون ضد أنماط الاحتيال دون تبادل بيانات العملاء.
Naseej enables banks to collaborate against fraud patterns without exchanging customer data.

Create a clean visual model in the center:
Bank A → Local Detection → Pattern Hash → Naseej Intelligence Layer → Bank B → Early Prevention

Add four concise bilingual steps:
1. يكتشف البنك النمط محليًا
   Detect the pattern locally

2. يحوّله إلى بصمة آمنة
   Convert it into a privacy-safe hash

3. يشارك البصمة عبر الشبكة
   Share the hash across the network

4. يمنع بنك آخر النمط نفسه مبكرًا
   Prevent the same pattern in another bank

Footer statement:
البيانات تبقى داخل البنك. الذكاء ينتقل بين البنوك.
Data stays inside the bank. Intelligence moves across banks.

Add a small badge:
Zero PII Shared
لا مشاركة لبيانات العملاء

Keep the slide concise, bilingual, highly readable, and visually polished.
Do not add extra explanations or paragraphs.
```

---

# Slide 08 — كيفية توفير البيانات واستخدامها | Data Sourcing & Usage

## Main Headline

**نولّد البيانات بأمان، ونستخدمها لاختبار نمط الاحتيال**  
**We generate safe data to validate fraud-pattern detection**

## How We Sourced the Data | كيف وفرنا البيانات؟

- **بيانات تحويلات اصطناعية داخل النموذج الأولي**  
  **Synthetic transaction data generated inside the MVP**

- **سيناريو احتيال محاكى: تحويلات صغيرة ثم تحويل خارجي**  
  **Simulated fraud scenario: micro-transfers followed by an international sweep**

- **لا توجد بيانات عملاء حقيقية أو PII**  
  **No real customer data or PII used**

## How We Used It | كيف استخدمناها؟

- **تحويل العمليات إلى شبكة حسابات**  
  **Convert transactions into an account graph**

- **كشف نمط Mule عبر العلاقات والسرعة**  
  **Detect mule behavior through graph and velocity signals**

- **توليد بصمة آمنة للنمط**  
  **Generate a privacy-safe pattern hash**

- **اختبار المنع المبكر في بنك آخر**  
  **Test early prevention in another bank**

## Footer Statement

**البيانات للاختبار فقط، أما القيمة فهي في طريقة مشاركة الذكاء دون مشاركة البيانات**  
**The data validates the demo. The value is sharing intelligence without sharing data**

## Visual Layout

Create a left-to-right flow:

**Generate** → **Model** → **Detect** → **Share** → **Prevent**

Under each step:

- Generate: **Synthetic Transactions | توليد تحويلات اصطناعية**
- Model: **Account Graph | بناء شبكة الحسابات**
- Detect: **Mule Pattern | كشف نمط الاحتيال**
- Share: **Pattern Hash | مشاركة بصمة النمط**
- Prevent: **Early Block | منع مبكر**

Add a clear privacy badge:

**0 Real PII**  
**صفر بيانات شخصية حقيقية**

## Claude Design Prompt

```text
Review and update slide 08 in the Naseej hackathon pitch deck.

Project:
نسيج | Naseej

Team:
Madar

Slide title:
كيفية توفير البيانات واستخدامها | Data Sourcing & Usage

Important:
If the current slide content differs from the approved content below, replace it.
Do not add extra paragraphs.
Do not change the project meaning.
Keep the slide bilingual Arabic-English, concise, premium, and visually clean.

Approved main headline:
نولّد البيانات بأمان، ونستخدمها لاختبار نمط الاحتيال
We generate safe data to validate fraud-pattern detection

Approved content:

Section 1:
كيف وفرنا البيانات؟ | How we sourced the data

1. بيانات تحويلات اصطناعية داخل النموذج الأولي
   Synthetic transaction data generated inside the MVP

2. سيناريو احتيال محاكى: تحويلات صغيرة ثم تحويل خارجي
   Simulated fraud scenario: micro-transfers followed by an international sweep

3. لا توجد بيانات عملاء حقيقية أو PII
   No real customer data or PII used

Section 2:
كيف استخدمناها؟ | How we used it

1. تحويل العمليات إلى شبكة حسابات
   Convert transactions into an account graph

2. كشف نمط Mule عبر العلاقات والسرعة
   Detect mule behavior through graph and velocity signals

3. توليد بصمة آمنة للنمط
   Generate a privacy-safe pattern hash

4. اختبار المنع المبكر في بنك آخر
   Test early prevention in another bank

Footer statement:
البيانات للاختبار فقط، أما القيمة فهي في طريقة مشاركة الذكاء دون مشاركة البيانات
The data validates the demo. The value is sharing intelligence without sharing data

Design direction:
Use a premium dark fintech style. Deep navy/black background, subtle graph lines, blue and violet accents, green for privacy and prevention, red only for fraud risk.

Visual layout:
Create a clean left-to-right flow:
Generate → Model → Detect → Share → Prevent

Under each step:
Generate: Synthetic Transactions | توليد تحويلات اصطناعية
Model: Account Graph | بناء شبكة الحسابات
Detect: Mule Pattern | كشف نمط الاحتيال
Share: Pattern Hash | مشاركة بصمة النمط
Prevent: Early Block | منع مبكر

Add a clear privacy badge:
0 Real PII
صفر بيانات شخصية حقيقية

Keep all text readable and aligned. Do not overcrowd the slide.
```

---

# Slide 09 — مواءمة الفكرة | Idea Alignment

## Main Headline

**نسيج في قلب أمد: ذكاء اصطناعي، امتثال، وحماية للقطاع المالي**  
**Naseej aligns with AMAD: AI, compliance, and financial protection**

## Primary Track | المسار الأقرب

**التشريعات المالية والامتثال**  
**Financial Regulations & Compliance**

**حل يحمي البنوك من الاحتيال مع احترام خصوصية بيانات العملاء**  
**A solution that fights fraud while preserving customer data privacy**

## Why It Fits AMAD | لماذا يناسب أمد؟

- **يوظّف الذكاء الاصطناعي وتحليل الشبكات**  
  **Uses AI and graph analytics**

- **يرفع كفاءة كشف الاحتيال المالي**  
  **Improves financial fraud detection efficiency**

- **يدعم التعاون بين البنوك دون مشاركة PII**  
  **Enables cross-bank collaboration without sharing PII**

- **يتماشى مع التوجه التنظيمي لحماية البيانات**  
  **Aligns with privacy-by-design and regulatory needs**

## Footer Statement

**نسيج لا يضيف أداة جديدة فقط، بل يقترح نموذج تعاون آمن للقطاع المالي**  
**Naseej is not just a tool. It is a secure collaboration model for the financial sector**

## Visual Layout

Place **Naseej** in the center. Around it, create four orbit cards:

1. **AI & Data Analytics**  
   الذكاء الاصطناعي وتحليل البيانات

2. **Financial Compliance**  
   الامتثال المالي

3. **Fraud Prevention**  
   منع الاحتيال

4. **Privacy by Design**  
   الخصوصية من التصميم

Bottom line:

**AMAD FinTech Track → Saudi Financial Sector Impact**

## Claude Design Prompt

```text
Review and update slide 09 in the Naseej hackathon pitch deck.

Project:
نسيج | Naseej

Team:
Madar

Slide title:
مواءمة الفكرة | Idea Alignment

Important:
If the current slide content differs from the approved content below, replace it.
Keep the slide bilingual Arabic-English.
Do not add extra paragraphs.
Keep it concise, premium, and visually clean.
The slide must show that Naseej strongly fits AMAD Hackathon and the FinTech track.

Approved main headline:
نسيج في قلب أمد: ذكاء اصطناعي، امتثال، وحماية للقطاع المالي
Naseej aligns with AMAD: AI, compliance, and financial protection

Approved content:

Section 1:
المسار الأقرب | Primary Track

التشريعات المالية والامتثال
Financial Regulations & Compliance

حل يحمي البنوك من الاحتيال مع احترام خصوصية بيانات العملاء
A solution that fights fraud while preserving customer data privacy

Section 2:
لماذا يناسب أمد؟ | Why it fits AMAD

1. يوظّف الذكاء الاصطناعي وتحليل الشبكات
   Uses AI and graph analytics

2. يرفع كفاءة كشف الاحتيال المالي
   Improves financial fraud detection efficiency

3. يدعم التعاون بين البنوك دون مشاركة PII
   Enables cross-bank collaboration without sharing PII

4. يتماشى مع التوجه التنظيمي لحماية البيانات
   Aligns with privacy-by-design and regulatory needs

Footer statement:
نسيج لا يضيف أداة جديدة فقط، بل يقترح نموذج تعاون آمن للقطاع المالي
Naseej is not just a tool. It is a secure collaboration model for the financial sector

Design direction:
Use a premium dark fintech style. Deep navy/black background, subtle banking network lines, elegant spacing, blue and violet accents, green for privacy and protection. Avoid clutter.

Visual layout:
Place “Naseej” in the center.
Around it, create four elegant orbit cards:
1. AI & Data Analytics
   الذكاء الاصطناعي وتحليل البيانات

2. Financial Compliance
   الامتثال المالي

3. Fraud Prevention
   منع الاحتيال

4. Privacy by Design
   الخصوصية من التصميم

Bottom line:
AMAD FinTech Track → Saudi Financial Sector Impact

Make the slide look like a strategic alignment slide, not a technical diagram.
```

---

# Slide 10 — مدعوم علميًا وتنظيميًا | Backed by Science & Regulation

## Main Headline

**فكرة نسيج ليست مجرد ديمو، بل نموذج مبني على مشكلة مثبتة**  
**Naseej is not only a demo. It is built on a validated financial security gap**

## Credibility Cards

### 1. Research-backed  
مدعوم بحثيًا  
Graph Analytics for mule-network detection

### 2. Privacy-by-design  
الخصوصية من التصميم  
Zero PII, pattern hash only

### 3. Regulation-aware  
واعٍ تنظيميًا  
PDPL-by-design · SAMA counter-fraud direction

### 4. Globally relevant  
مشكلة عالمية  
Mule accounts are a central-bank priority

## Footer Statement

**مدعوم علميًا. واعٍ تنظيميًا. جاهز للتجربة.**  
**Research-backed. Regulation-aware. Pilot-ready.**

## Visual Layout

Use four credibility pillars around **نسيج | Naseej**.

Optional placeholders:

- SAMA logo
- SDAIA logo
- Research paper thumbnail
- Global mule-account reference / RBI-style reference

Do not overcrowd the slide.

## Claude Design Prompt

```text
Create an additional bilingual Arabic-English slide for the Naseej hackathon pitch deck.

Slide title:
مدعوم علميًا وتنظيميًا | Backed by Science & Regulation

Project:
نسيج | Naseej

Team:
Madar

Design style:
Premium dark fintech design, elegant and minimal. Use deep navy/black background, subtle graph network lines, blue and violet accents, green for compliance/privacy, and red only for risk. The slide should feel credible, serious, and suitable for judges in a fintech hackathon.

Main headline:
فكرة نسيج ليست مجرد ديمو، بل نموذج مبني على مشكلة مثبتة
Naseej is not only a demo. It is built on a validated financial security gap

Create four elegant cards:

1. Research-backed
   مدعوم بحثيًا
   Graph Analytics for mule-network detection

2. Privacy-by-design
   الخصوصية من التصميم
   Zero PII, pattern hash only

3. Regulation-aware
   واعٍ تنظيميًا
   PDPL-by-design · SAMA counter-fraud direction

4. Globally relevant
   مشكلة عالمية
   Mule accounts are a central-bank priority

Footer statement:
مدعوم علميًا. واعٍ تنظيميًا. جاهز للتجربة.
Research-backed. Regulation-aware. Pilot-ready.

Wording rule:
Use “regulation-aware” and “PDPL-by-design”, not “certified” or “compliant”. Naseej is a research prototype, not a certified banking system.

Visual suggestion:
Use four credibility pillars around the Naseej logo/name.
Optionally include small placeholders for:
SAMA logo, SDAIA logo, research paper thumbnail, and global mule-account reference.
Do not overcrowd the slide.
Keep the text concise and bilingual.
```

---

# Slide 11 — الملخص | Summary

## Main Headline

**نسيج يحمي القطاع المالي من الاحتيال العابر للبنوك دون كشف البيانات**  
**Naseej protects banks from cross-bank fraud without exposing data**

## Cards

### ما بنيناه | What we built

**نموذج أولي يحاكي شبكة ذكاء احتيالي بين البنوك السعودية**  
**An MVP simulating a fraud intelligence network between Saudi banks**

### ما يميّزه | Why it matters

**كل بنك يحتفظ ببياناته، ويشارك فقط بصمة النمط الاحتيالي**  
**Each bank keeps its data and shares only the fraud-pattern hash**

### ما أثبتناه | What we proved

**اكتشاف محلي، مشاركة آمنة، ومنع مبكر في بنك آخر**  
**Local detection, secure sharing, and early prevention in another bank**

## Footer Statement

**نسيج ينقل الذكاء، لا ينقل بيانات العملاء**  
**Naseej moves intelligence, not customer data**

## Visual Layout

Create three large cards:

1. **Detect | اكتشاف**  
   Local mule pattern detection

2. **Share | مشاركة**  
   Zero-PII pattern hash

3. **Prevent | منع**  
   Early cross-bank blocking

Add badge:

**Zero PII Shared | لا مشاركة لبيانات العملاء**

## Claude Design Prompt

```text
Review and update slide 11 in the Naseej hackathon pitch deck.

Project:
نسيج | Naseej

Team:
Madar

Slide title:
الملخص | Summary

Important:
If the current slide content differs from the approved content below, replace it.
Keep the slide bilingual Arabic-English.
Keep it concise, premium, and visually clean.
Do not add extra paragraphs.
This slide should feel like an executive summary before validation and demo.

Approved main headline:
نسيج يحمي القطاع المالي من الاحتيال العابر للبنوك دون كشف البيانات
Naseej protects banks from cross-bank fraud without exposing data

Approved content:

Card 1:
ما بنيناه | What we built
نموذج أولي يحاكي شبكة ذكاء احتيالي بين البنوك السعودية
An MVP simulating a fraud intelligence network between Saudi banks

Card 2:
ما يميّزه | Why it matters
كل بنك يحتفظ ببياناته، ويشارك فقط بصمة النمط الاحتيالي
Each bank keeps its data and shares only the fraud-pattern hash

Card 3:
ما أثبتناه | What we proved
اكتشاف محلي، مشاركة آمنة، ومنع مبكر في بنك آخر
Local detection, secure sharing, and early prevention in another bank

Footer statement:
نسيج ينقل الذكاء، لا ينقل بيانات العملاء
Naseej moves intelligence, not customer data

Design direction:
Premium dark fintech style. Deep navy/black background, subtle graph network lines, blue and violet accents, green for privacy and prevention, red only for fraud risk. Strong spacing, high readability, minimal text.

Visual layout:
Create three large cards:
Detect | اكتشاف
Local mule pattern detection

Share | مشاركة
Zero-PII pattern hash

Prevent | منع
Early cross-bank blocking

Add a small badge:
Zero PII Shared
لا مشاركة لبيانات العملاء

Do not overcrowd the slide.
```

---

# Slide 12 — الاختبار / التحقق | Validation

## Main Headline

**تحققنا من المسار الكامل: اكتشاف، مشاركة، منع**  
**We validated the full flow: detect, share, prevent**

## What We Tested | ما اختبرناه

### 1. سيناريو احتيال محاكى  
**Simulated fraud scenario**  
5 micro-transfers + international sweep

### 2. كشف نمط Mule عبر Graph Analytics  
**Mule pattern detection through graph analytics**

### 3. مشاركة بصمة آمنة بدون PII  
**Zero-PII pattern hash sharing**

### 4. منع معاملة مشابهة في بنك آخر  
**Blocking a matching transaction in another bank**

## Validation Signals | نتائج التحقق

- **Detected** — تم اكتشاف النمط
- **Hashed** — تم توليد البصمة
- **Zero PII** — لم تتم مشاركة بيانات العملاء
- **Blocked** — تم منع العملية المشابهة

## ML Baseline Strip | مؤشر النموذج الأولي

**PR-AUC: 0.2275 | Precision: 27.3% | Recall: 19.6% | F1: 0.2278**

Optional secondary values if space allows:

**Threshold: 0.0606 | Alerts: 33 | Confirmed: 9**

> These numbers are the deployed MVP baseline on synthetic AMLworld-style data (45,001 test transactions, ~0.1% fraud prevalence). They must always match `ml/reports/model_metrics.json`.

## Footer Statement

**هذه مؤشرات أساس للنموذج الأولي على بيانات اصطناعية؛ والقيمة الأساسية في نموذج التعاون الآمن بين البنوك**  
**These are MVP baseline signals on synthetic data; the core value is the secure cross-bank collaboration model**

## Visual Layout

Top horizontal validation flow:

**Attack Simulation → Detection → Hash Sharing → Bank B Block**

Below it, four validation cards:

1. **Detected | اكتشاف**
2. **Hashed | بصمة آمنة**
3. **Zero PII | صفر بيانات شخصية**
4. **Blocked | منع مبكر**

Bottom compact strip:

**PR-AUC 0.2275 | Precision 27.3% | Recall 19.6% | F1 0.2278**

## Important Wording Rule

Do not present the ML metrics as production performance. Present them as:

**MVP validation baseline**  
**مؤشر تحقق للنموذج الأولي**

Never round up or reuse older values. The figures must mirror the deployed baseline report `ml/reports/model_metrics.json` exactly.

## Claude Design Prompt

```text
Review and update slide 12 in the Naseej hackathon pitch deck.

Project:
نسيج | Naseej

Team:
Madar

Slide title:
الاختبار / التحقق | Validation

Important:
If the current slide content differs from the approved content below, replace it.
Keep the slide bilingual Arabic-English.
Keep it concise, premium, and visually clean.
Do not add extra paragraphs.
This slide must show that Naseej has a working MVP validation, not only an idea.

Approved main headline:
تحققنا من المسار الكامل: اكتشاف، مشاركة، منع
We validated the full flow: detect, share, prevent

Approved content:

Section 1:
ما اختبرناه | What we tested

1. سيناريو احتيال محاكى
   Simulated fraud scenario
   5 micro-transfers + international sweep

2. كشف نمط Mule عبر Graph Analytics
   Mule pattern detection through graph analytics

3. مشاركة بصمة آمنة بدون PII
   Zero-PII pattern hash sharing

4. منع معاملة مشابهة في بنك آخر
   Blocking a matching transaction in another bank

Section 2:
نتائج التحقق | Validation Signals

Detected
تم اكتشاف النمط

Hashed
تم توليد البصمة

Zero PII
لم تتم مشاركة بيانات العملاء

Blocked
تم منع العملية المشابهة

ML Baseline strip (must match ml/reports/model_metrics.json exactly):
PR-AUC: 0.2275
Precision: 27.3%
Recall: 19.6%
F1: 0.2278

Footer statement:
هذه مؤشرات أساس للنموذج الأولي على بيانات اصطناعية؛ والقيمة الأساسية في نموذج التعاون الآمن بين البنوك
These are MVP baseline signals on synthetic data; the core value is the secure cross-bank collaboration model

Design direction:
Premium dark fintech style. Deep navy/black background, subtle transaction graph lines, blue for detection, violet for hash/pattern sharing, green for privacy and blocked/prevented success, red only for fraud risk. Strong spacing, clean hierarchy, no clutter.

Visual layout:
Create a top horizontal validation flow:
Attack Simulation → Detection → Hash Sharing → Bank B Block

Below it, create four validation cards:
1. Detected | اكتشاف
2. Hashed | بصمة آمنة
3. Zero PII | صفر بيانات شخصية
4. Blocked | منع مبكر

At the bottom, add a compact ML Baseline strip:
PR-AUC 0.2275 | Precision 27.3% | Recall 19.6% | F1 0.2278

Important wording rule:
Do not present the ML metrics as production performance.
Present them as “MVP validation baseline” or “ML baseline signal”.
Do not invent or inflate numbers; use the exact values above.
Keep all Arabic and English text readable.
```

---

# Slide 13-A — العرض التوضيحي | Demo Preview

## Purpose

Use this as a visual proof slide. Do not add much text.

## Title

**العرض التوضيحي | Demo Preview**

## Subtitle

**Live simulation of privacy-preserving cross-bank fraud detection**  
**محاكاة مباشرة لكشف احتيال عابر للبنوك مع حفظ الخصوصية**

## Image to Place

A full screenshot of the Naseej interface in **IDLE / Normal Transactions** mode.

## Footer

**Detect → Share → Prevent**  
**اكتشاف → مشاركة → منع**

## Design Direction

- Use one large screenshot occupying most of the slide.
- Add a thin premium frame around the screenshot.
- Keep title small and clean.
- The screenshot should show Bank A and Bank B clearly.

---

# Slide 13-B — مراحل المحاكاة | Simulation Flow

## Title

**مراحل المحاكاة | Simulation Flow**

## Main Line

**من اكتشاف محلي إلى منع مبكر عبر بنك آخر**  
**From local detection to early prevention across another bank**

## Images to Place

Place four screenshots from left to right:

1. **Attack | الهجوم**  
   Screenshot showing micro-transfers in Bank A.

2. **Detected | الاكتشاف**  
   Screenshot showing red alert and Graph Analytics.

3. **Hash Shared | مشاركة البصمة**  
   Screenshot showing the pattern hash or broadcast moment.

4. **Blocked | المنع**  
   Screenshot showing Bank B with the transaction blocked.

## Design Direction

- Make it a clean four-step storyboard.
- Each image should have a short bilingual label.
- Use arrows between screenshots.
- Do not add paragraphs.

---

# Slide 13-C — فيديو الديمو | Demo Video

## Title

**فيديو الديمو | Demo Video**

## Subtitle

**90-second walkthrough of Naseej MVP**  
**استعراض سريع للنموذج الأولي خلال 90 ثانية**

## What to Place

- Video thumbnail, QR code, or demo link area in the center.
- If QR is used, place a small label below it.
- If no QR is available, place a clean screenshot with a play icon.

## Footer

**No real PII used | لم تُستخدم بيانات عملاء حقيقية**

## Design Direction

- Keep this slide simple and confident.
- Let the video thumbnail or QR be the hero.
- Use the same dark fintech styling.

---

# Slide 14 — التحديات والخطط المستقبلية | Challenges & Future Plans

## Main Headline

**من نموذج أولي متحقَّق إلى شبكة قابلة للتجربة البنكية**  
**From a validated MVP to a bank-ready pilot network**

## Challenges | التحديات

- **الوصول إلى بيانات بنكية حقيقية بشكل آمن**  
  **Secure access to real banking data**

- **اختبار النموذج تحت سيناريوهات احتيال أوسع**  
  **Testing against broader fraud scenarios**

- **حوكمة القرار وتقليل الإنذارات الخاطئة**  
  **Decision governance and false-positive control**

- **التكامل مع أنظمة البنوك الحالية**  
  **Integration with existing banking systems**

## Future Plan | الخطة المستقبلية

### 1. Open Banking Integration  
ربط آمن مع واجهات البيانات المالية  
Secure financial data integration

### 2. Advanced Fraud Intelligence  
توسيع Graph Analytics ونماذج المخاطر  
Expand graph analytics and risk models

### 3. Arabic Scam Intelligence  
تحليل رسائل الاحتيال العربية  
Analyze Arabic scam messages

### 4. SAMA Sandbox & Bank Pilot  
اختبار منظم مع الجهات والبنوك  
Controlled sandbox and bank pilot

## Support Needed | ما نحتاجه

**بيانات اختبار، خبراء امتثال، وشركاء تجريبيون من القطاع المالي**  
**Test data, compliance experts, and financial-sector pilot partners**

## Footer Statement

**الخطوة القادمة ليست بناء واجهة أكبر، بل إثبات الثقة على بيانات وتجارب أعمق**  
**The next step is not a bigger UI, but deeper trust through data and pilots**

## Visual Layout

Split into two columns:

Left column: **Challenges**
- Four compact cards: Data Access, Scenario Testing, Governance, Integration

Right column: **Future Plan**
- Roadmap: Open Banking → Graph Intelligence → Arabic NLP → SAMA Sandbox

Bottom strip:

**Support Needed**  
Test data | Compliance experts | Pilot partners

## Claude Design Prompt

```text
Review and update slide 14 in the Naseej hackathon pitch deck.

Project:
نسيج | Naseej

Team:
Madar

Slide title:
التحديات والخطط المستقبلية | Challenges & Future Plans

Important:
If the current slide content differs from the approved content below, replace it.
Keep the slide bilingual Arabic-English.
Do not add extra paragraphs.
Keep it concise, premium, and visually clean.
The tone must be realistic: Naseej is a validated MVP/prototype, not a production banking system yet.

Approved main headline:
من نموذج أولي متحقَّق إلى شبكة قابلة للتجربة البنكية
From a validated MVP to a bank-ready pilot network

Section 1:
التحديات | Challenges

1. الوصول إلى بيانات بنكية حقيقية بشكل آمن
   Secure access to real banking data

2. اختبار النموذج تحت سيناريوهات احتيال أوسع
   Testing against broader fraud scenarios

3. حوكمة القرار وتقليل الإنذارات الخاطئة
   Decision governance and false-positive control

4. التكامل مع أنظمة البنوك الحالية
   Integration with existing banking systems

Section 2:
الخطة المستقبلية | Future Plan

1. Open Banking Integration
   ربط آمن مع واجهات البيانات المالية
   Secure financial data integration

2. Advanced Fraud Intelligence
   توسيع Graph Analytics ونماذج المخاطر
   Expand graph analytics and risk models

3. Arabic Scam Intelligence
   تحليل رسائل الاحتيال العربية
   Analyze Arabic scam messages

4. SAMA Sandbox & Bank Pilot
   اختبار منظم مع الجهات والبنوك
   Controlled sandbox and bank pilot

Section 3:
ما نحتاجه | Support Needed

بيانات اختبار، خبراء امتثال، وشركاء تجريبيون من القطاع المالي
Test data, compliance experts, and financial-sector pilot partners

Footer statement:
الخطوة القادمة ليست بناء واجهة أكبر، بل إثبات الثقة على بيانات وتجارب أعمق
The next step is not a bigger UI, but deeper trust through data and pilots

Design direction:
Premium dark fintech style. Deep navy/black background, subtle graph network lines, blue for technical integration, violet for intelligence, green for privacy and pilot readiness, red only for risk/challenges. Keep strong spacing and clean hierarchy.

Visual layout:
Split the slide into two main columns.

Left column:
Challenges
Create four compact cards:
Data Access
Scenario Testing
Governance
Integration

Right column:
Future Plan
Create a clean horizontal or vertical roadmap:
Open Banking → Graph Intelligence → Arabic NLP → SAMA Sandbox

Bottom strip:
Support Needed
Test data | Compliance experts | Pilot partners

Do not overcrowd the slide. Make it look like a strategic roadmap slide.
```

---

# Slide 15 — شكراً | Thank You

## Title

**شكراً | Thank You**

## Closing Line

**نسيج ينقل الذكاء, لا ينقل بيانات العملاء**  
**Naseej moves intelligence, not customer data**

## Footer

**Team Madar | فريق مدار**

Optional placeholders:

- Demo QR
- GitHub QR
- Contact / LinkedIn

## Design Direction

- Do not leave it as a generic thank-you slide.
- Make the closing line the hero.
- Keep the visual clean and confident.
- Add QR codes only if available and readable.

---

# Best Screenshots to Capture for Demo Slides | أفضل لقطات للديمو

Capture these from the Naseej MVP:

1. **الواجهة قبل التشغيل | Interface before running**  
   Shows Bank A and Bank B clearly.

2. **لحظة ظهور الهجوم في Bank A | Attack in Bank A**  
   Shows the micro-transfers.

3. **لحظة Graph Analytics والتنبيه الأحمر | Graph Analytics and red alert**  
   This is the strongest visual moment.

4. **لحظة ظهور Pattern Hash | Pattern Hash reveal**  
   Focus on Zero PII.

5. **لحظة وصول البصمة إلى Bank B | Hash arriving to Bank B**  
   Capture animation or a still if possible.

6. **لحظة Blocked في Bank B | Blocked transaction in Bank B**  
   This is the strongest closing screenshot.

---

# Master Claude Review Prompt | برومبت مراجعة شامل لكلود

Use this prompt after attaching this markdown file and the PowerPoint template to Claude or Claude Design.

```text
I have attached a markdown file titled “Naseej Pitch Deck Content Guide” and a PowerPoint template for the AMAD Hackathon pitch deck.

Your task is to review, refine, and prepare the final pitch deck content and slide-by-slide design plan using the markdown file as the single source of truth.

Project:
نسيج | Naseej

Team:
Madar

Event:
AMAD Hackathon | FinTech Track

Important rules:
1. Do not change the project name. Use: نسيج | Naseej.
2. Do not use MuleHunter.AI as the project name. Mule accounts are only a fraud typology.
3. Keep all slide content bilingual Arabic-English.
4. Keep the wording concise and presentation-friendly.
5. Do not add long paragraphs to slides.
6. Preserve the strategic message: data stays inside the bank, intelligence moves across banks.
7. Keep the tone realistic: this is a validated hackathon MVP/prototype, not a production banking system.
8. Treat ML metrics as MVP validation baseline signals, not production performance claims. Use the exact values from ml/reports/model_metrics.json (PR-AUC 0.2275, Precision 27.3%, Recall 19.6%, F1 0.2278). Never inflate or reuse older numbers.
9. Do not describe the mechanism as “federated learning”. It is privacy-safe pattern-hash sharing.
10. Use “regulation-aware” and “PDPL-by-design”, not “certified” or “compliant”.
11. Maintain a premium dark fintech visual identity: deep navy/black, subtle graph/network lines, blue/violet accents, green for privacy/prevention, red only for fraud risk.
12. If the template has placeholder text that conflicts with the approved content in the markdown file, replace it.
13. If the slide order differs from the markdown file, reorganize it to match the recommended final deck structure.
14. Do not overcrowd any slide. If the demo slide is crowded, split it into 13-A, 13-B, and 13-C as described.
15. Keep slide titles, key messages, and footer statements exactly aligned with the approved markdown content unless a minor wording edit improves clarity without changing meaning.
16. Make the deck visually powerful for hackathon judges: clear problem, credible solution, working MVP, privacy-by-design, and strong roadmap.

Required output:
1. A final slide-by-slide content review.
2. A list of any wording issues or inconsistencies found.
3. A clean final slide structure with slide numbers.
4. Specific design instructions for each slide.
5. A final checklist before exporting the presentation.

Do not invent new claims, statistics, or regulatory statements beyond what is in the markdown file unless you clearly label them as suggestions requiring verification.
```

---

# Final Review Checklist | قائمة مراجعة نهائية

Before submitting the deck:

- [ ] Project name is **نسيج | Naseej** everywhere.
- [ ] Team name is **Madar** everywhere.
- [ ] All slides are bilingual Arabic-English.
- [ ] No slide is overcrowded.
- [ ] Agenda order matches the actual slide flow.
- [ ] Problem slide clearly says the real issue is cross-bank fraud visibility.
- [ ] Data slide clearly says no real PII was used.
- [ ] Technology slide separates MVP stack from intelligence layer.
- [ ] No slide claims “federated learning”; sharing is described as privacy-safe pattern-hash sharing.
- [ ] Idea slide clearly explains Detect → Hash → Share → Prevent.
- [ ] Alignment slide clearly maps Naseej to Financial Regulations & Compliance.
- [ ] Science & Regulation slide uses “regulation-aware / PDPL-by-design”, not “certified”.
- [ ] Summary slide is strong and executive.
- [ ] Validation slide shows the exact baseline metrics from `ml/reports/model_metrics.json` (PR-AUC 0.2275, Precision 27.3%, Recall 19.6%, F1 0.2278) and does not overclaim production accuracy.
- [ ] Demo slides show real screenshots or video, not only mockups.
- [ ] Roadmap is realistic and mentions pilot readiness.
- [ ] Thank-you slide ends with a strong message and QR/contact if available.
- [ ] The final exported presentation is visually checked from first slide to last slide.
