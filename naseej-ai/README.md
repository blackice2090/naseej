# Naseej | نسيج — Demo Frontend

**Privacy-preserving cross-bank AML and fraud intelligence for Saudi financial institutions.**

> Research prototype — originally built at the Amad Hackathon (FinTech track).
> The original hackathon concept was inspired by mule-account detection
> (working title *MuleHunter.AI*); the product is now **Naseej | نسيج**.

---

## What It Does

Naseej simulates a cross-bank threat intelligence network that detects and blocks **mule-account** money-laundering chains across multiple banks — without sharing any customer PII.

When Bank A detects a suspicious transaction topology, it generates a cryptographic pattern hash (`NSJ_<PATTERN_TYPE>_<16-hex>`) encoding only the structural shape of the fraud — zero personal data — and broadcasts it to the network. Bank B matches its own incoming transactions against the hash and blocks the matching transaction before it executes.

This is a **simulation** built for demonstration: the two banks run in one browser window, and the "network" is in-memory. The privacy-hash engine, XGBoost model, and cross-bank experiment behind the numbers on screen are real and live in `../ml/` and `../backend/`.

---

## Live Demo Flow

| Stage | What Happens |
|---|---|
| **IDLE** | Both banks process randomized normal transactions |
| **ATTACK** | Click **RUN SIMULATION** — 5 micro-transfers fan into a mule account in Bank A, followed by an international sweep |
| **DETECTED** | Bank A's graph analytics engine flags the topological anomaly. The mule network lights up red. A zero-PII pattern hash decodes on screen |
| **BROADCASTING** | The hash travels across the network to Bank B — no customer data crosses the boundary |
| **BLOCKED** | An accomplice in Bank B attempts a matching wire — blocked via pattern match before execution |
| **RESET** | Click **RESET DEMO** to restart cleanly from any stage |

---

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+

### Install & Run

```bash
cd naseej-ai
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

The demo runs entirely in the browser. If the FastAPI backend (`uvicorn backend.app.main:app --port 8000`, run from the repo root) is up, the metric cards switch from fallback values to live model output and the strip shows `API LIVE`.

For the best presentation experience, open fullscreen on a **1920×1080** display.

### Build for Production

```bash
npm run build
npm run preview
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 18 + Vite |
| Styling | Tailwind CSS (JIT, arbitrary values) |
| Animation | Framer Motion |
| Icons | Lucide React |
| Graph Visualization | Pure CSS/SVG — no external library |
| State Management | React `useState` + `useRef` (no Redux) |
| Simulation Engine | Rule-based frontend logic — backend optional |

---

## Project Structure

```
naseej-ai/
├── src/
│   ├── App.jsx                    # Thin composition root
│   ├── main.jsx                   # ReactDOM.createRoot entry point
│   ├── index.css                  # Tailwind directives + scrollbar styles
│   ├── config/
│   │   ├── constants.js           # Stages, timings, theme tokens, demo hash
│   │   ├── copy.js                # All user-facing copy (honest wording)
│   │   └── investigator.js        # Status machine mirror, decisions, typology copy
│   ├── data/
│   │   ├── mockData.js            # Synthetic attack sequence + offline fallbacks
│   │   ├── mockCases.js           # Offline investigator cases (zero PII)
│   │   └── demoPattern.js         # Demo detection → schema-valid pattern object
│   ├── lib/
│   │   └── api.js                 # Backend fetch layer (degrades gracefully offline)
│   ├── hooks/
│   │   ├── useSimulation.js       # Reset-safe 5-stage simulation engine
│   │   ├── useBackendData.js      # Model metrics + cross-bank enrichment
│   │   └── useCases.js            # Case state: live API or labelled mock fallback
│   └── components/
│       ├── ui/                    # CountUp, StatCard, TxRow, BlockedStamp, SectionLabel
│       ├── graph/                 # GraphNode, GraphView, BroadcastPulse
│       ├── panels/                # TopNav, MLValidationCard, ResearchStrip,
│       │                          # BankAPanel, BankBPanel, HashDisplay,
│       │                          # IntelFeed, AlertBanner, ControlBar
│       └── investigator/          # InvestigatorView, CaseQueue, CaseDetail
├── index.html
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── package.json
```

Simulation logic, UI copy, mock data, and components are separated so the
demo choreography is auditable and copy changes never touch component code.

---

## Key Technical Design Decisions

### 1. Zero PII — even in mock data
The synthetic transaction feeds use account handles only (`0xA1B2`), never names, IBANs, or realistic identifiers. The hash broadcast to Bank B encodes topology shape only, demonstrating PDPL-by-design.

### 2. Honest copy by construction
All user-facing strings live in `src/config/copy.js` with explicit wording rules: "aligned" and "by design", never "certified" or "compliant" as a finished claim; "pattern-hash sharing", not "federated learning". The fallback metrics in `src/data/mockData.js` mirror the real evaluation reports in `../ml/reports/` so the demo never overstates the model when the backend is offline.

### 3. Bulletproof demo reset
All `setTimeout` IDs are tracked in a `useRef` array inside `useSimulation`. Reset clears every pending timeout before resetting state — no ghost transitions if a presenter restarts mid-demo.

### 4. Hash decode synced to the stage machine
The pattern hash scrambles for 1.5s, then reveals left-to-right within the DETECTED window. If the stage advances early, the full hash snaps in immediately. When the backend is live, the real `NSJ_*` hash from `/api/analyze-pattern` replaces the placeholder.

### 5. Radar ripple (graph analytics visual)
The mule node uses three staggered ripple rings to create a radar-scanning effect during DETECTED and BROADCASTING.

---

## Regulatory Posture

| Framework | Posture |
|---|---|
| **PDPL** (Saudi Personal Data Protection Law) | Zero PII leaves Bank A by design — only structural pattern hashes are shared |
| **SAMA Counter-Fraud Framework** | Aligned with the early-warning and cross-bank threat intelligence mandate |
| **Model governance** | Analyst triage only — no autonomous blocking is claimed or implemented |

This is a research prototype on synthetic data. It is **not** certified, audited, or production-ready. See `../docs/SECURITY_COMPLIANCE.md`.

---

## Background

- **"AI-Driven Fraud Detection and Financial Security Framework for Saudi Banking Systems"** — Malik Ashfaq Ur Rahman (2026): graph analytics for mule networks, privacy-preserving cross-bank typology sharing
- **RBI Innovation Hub — MuleHunter Initiative** (external RBI project): validates the global priority of the mule-accounts problem
