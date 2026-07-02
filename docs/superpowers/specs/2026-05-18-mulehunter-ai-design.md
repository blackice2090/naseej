# Naseej | نسيج — Design Spec
**Date:** 2026-05-18  
**Status:** Approved  
**Event:** Amad Hackathon — FinTech Track (48-hour MVP)

---

## 1. What We're Building

A single-page React application that simulates Naseej | نسيج: a privacy-preserving, federated fraud detection network for Saudi banks. The app is a live demo tool — not a production system. All data is simulated in the frontend. No backend required.

The demo proves the concept: Bank A detects a Mule Account pattern, generates a cryptographic hash (zero PII), broadcasts it to the federated network, and Bank B automatically blocks a matching transaction in real time.

---

## 2. Project Structure

```
naseej-ai/
├── src/
│   └── App.jsx          ← all logic, all components, everything
├── index.html           ← minimal Vite boilerplate
├── main.jsx             ← ReactDOM.createRoot only
├── index.css            ← Tailwind directives (@tailwind base/components/utilities)
├── tailwind.config.js   ← custom color tokens
└── package.json
```

**Stack:** Vite + React 18, Tailwind CSS, Lucide React icons.  
No additional runtime dependencies. Graph visualization is pure CSS/SVG — no Vis.js or react-force-graph.

---

## 3. App.jsx Internal Structure

Everything in App.jsx is defined top-to-bottom in this order:

### 3.1 Constants & Data

```js
// Stage enum
const STAGES = { IDLE: 0, ATTACK: 1, DETECTED: 2, BROADCASTING: 3, BLOCKED: 4 }

// Scripted attack: 5 micro-transfers into mule account, then international sweep
const ATTACK_SEQUENCE = [
  { from: "0xSRC_A1", to: "0xMULE_01", amount: 2400, label: "Micro-transfer 1/5" },
  { from: "0xSRC_A2", to: "0xMULE_01", amount: 1850, label: "Micro-transfer 2/5" },
  { from: "0xSRC_A3", to: "0xMULE_01", amount: 3100, label: "Micro-transfer 3/5" },
  { from: "0xSRC_A4", to: "0xMULE_01", amount: 990,  label: "Micro-transfer 4/5" },
  { from: "0xSRC_A5", to: "0xMULE_01", amount: 1760, label: "Micro-transfer 5/5" },
  { from: "0xMULE_01", to: "0xINTL_DEST", amount: 11200, label: "SWEEP — International Wire" },
]

// Pool of random TX participants (Bank A shows names; hash has zero PII)
const TX_POOL = [
  { id: "0xA1B2", name: "Mohammed Al-Qahtani", iban: "SA03 8000 0000 6080 1016 7519" },
  { id: "0xC3D4", name: "Fatima Al-Zahrani",   iban: "SA56 2000 0001 8123 4567 8901" },
  { id: "0xE5F6", name: "Ahmed Al-Ghamdi",     iban: "SA44 0533 1234 5678 9012 3456" },
  { id: "0xG7H8", name: "Sara Al-Otaibi",      iban: "SA72 1000 0508 0000 6454 5108" },
  { id: "0xI9J0", name: "Khalid Al-Shehri",    iban: "SA62 0500 0000 0021 0697 2014" },
]
// Note: TX_POOL names/IBANs are displayed only in Bank A's local feed.
// The broadcast hash contains zero PII — this separation is the core PDPL compliance demo.

// Threat hash (deterministic for demo)
const THREAT_HASH = "0x8F9B2C_MULE_VELOCITY"
```

### 3.2 Utilities

- `generateRandomTx()` — picks two entries from TX_POOL, random amount 200–5000 SAR, returns `{ from, to, amount, status: "CLEAR" }`
- `generateHash()` — returns `THREAT_HASH` (fixed for demo reproducibility)

### 3.3 Sub-Components

| Component | Purpose |
|---|---|
| `<StatCard />` | Single metric tile: value + label |
| `<TxRow />` | One row in the transaction feed (color-coded by status) |
| `<GraphNode />` | Circle node with label + border color driven by stage |
| `<GraphView />` | Three `<GraphNode>` instances connected by SVG dashed lines; nodes pulse red in DETECTED+ |
| `<AlertBanner />` | Red pulsing banner: "⚠ MULE PATTERN DETECTED — Velocity Breach / Graph Analytics Triggered" — hidden until DETECTED |
| `<HashDisplay />` | Reveals `0x8F9B2C_MULE_VELOCITY` character-by-character via a `useEffect` that appends one character every 60ms to a `displayedHash` state string. Starts when stage enters DETECTED. Shows "PDPL: Zero PII Exported" label below once the full hash is rendered. |
| `<BroadcastPulse />` | A `position:absolute` div with a glowing dot that translates from the center of the left panel to the center of the right panel using a CSS `@keyframes` animation (0% → translateX(0), 100% → translateX(50vw)). Duration: 1200ms, ease-in-out. Visible only during BROADCASTING stage. |
| `<BankAPanel />` | Left panel — receives `{ stage, txList }` props |
| `<BankBPanel />` | Right panel — receives `{ stage, blockedTx }` props |
| `<ControlBar />` | Bottom bar — RUN SIMULATION / RESET button + current stage label |

### 3.4 Root Component: `<App />`

State:
```js
const [stage, setStage] = useState(STAGES.IDLE)
const [bankATxs, setBankATxs] = useState([])
const [bankBTxs, setBankBTxs] = useState([])
const [blockedTx, setBlockedTx] = useState(null)
```

Effects:
- **Random TX interval** — `setInterval(1200ms)` adds a `generateRandomTx()` to each bank's feed while stage is `IDLE`. Clears on stage change.
- **Stage auto-advance** — When stage enters `ATTACK`, a series of `setTimeout` calls:
  - t+0ms: inject ATTACK_SEQUENCE TXs into Bank A feed
  - t+2500ms: `setStage(DETECTED)`
  - t+4000ms: `setStage(BROADCASTING)`
  - t+5500ms: `setStage(BLOCKED)` + set `blockedTx`

Renders:
```jsx
<div className="...full screen, dark bg...">
  <TopNav />
  <div className="...split grid cols-2...">
    <BankAPanel stage={stage} txList={bankATxs} />
    <BankBPanel stage={stage} blockedTx={blockedTx} txList={bankBTxs} />
    {stage === STAGES.BROADCASTING && <BroadcastPulse />}
  </div>
  <ControlBar stage={stage} onRun={handleRun} onReset={handleReset} />
</div>
```

---

## 4. Simulation Flow

| Stage | Trigger | Bank A | Bank B |
|---|---|---|---|
| `IDLE` | App load | Random TXs every 1.2s, all CLEAR | Random TXs every 1.2s, all CLEAR |
| `ATTACK` | "RUN SIMULATION" click | 6 scripted TXs injected rapidly | Continues random noise |
| `DETECTED` | Auto, 2.5s post-ATTACK | Red alert banner + graph nodes pulse red + hash typewriter reveal | Log: "Receiving threat intelligence..." |
| `BROADCASTING` | Auto, 1.5s post-DETECTED | HashDisplay shows "Exporting Pattern — Zero PII Shared" | Animated pulse arrives, log: "Pattern 0x8F9B2C received from Bank A" |
| `BLOCKED` | Auto, 1.5s post-BROADCASTING | Status locked | Accomplice TX stamped red: "BLOCKED — Zero-Day Prevention via Federated Learning. Privacy Maintained." |

---

## 5. Visual Design

**Color tokens (tailwind.config.js custom extension):**

| Token | Hex | Usage |
|---|---|---|
| `bg-base` | `#07090f` | App background |
| `bg-panel` | `#0d1525` | Panel backgrounds, nav, control bar |
| `bg-card` | `#0a0f1e` | Stat cards, feed containers |
| `border-dim` | `#1a2744` | All borders |
| `accent-a` | `#4fc3f7` | Bank A (blue-400) |
| `accent-b` | `#7c4dff` | Bank B (violet-500) |
| `green` | `#00e676` | CLEAR status, safe indicators |
| `red` | `#ff4d6b` | THREAT, BLOCKED, alert banners |
| `violet` | `#7c4dff` | Hash display, PII-free labels |

**Aesthetic rules:**
- All text: monospace or `font-mono` for feeds/hashes; `font-sans` for labels
- Pulsing green dot in top nav = federated network active
- Neon glow on stat values using `drop-shadow` or `box-shadow` inline
- `animate-pulse` on alert banner and graph nodes during DETECTED+
- Tailwind `transition-all duration-500` on TX rows changing status

---

## 6. Academic Terminology Injection

All UI copy must use exact terminology from the research paper and References.md:

| UI Element | Text |
|---|---|
| Top nav | "FEDERATED NETWORK ACTIVE · SAMA COMPLIANT · PDPL CERTIFIED" |
| Alert banner | "⚠ MULE PATTERN DETECTED — Coordinated Velocity Breach / Graph Analytics Engine Triggered" |
| Graph label | "GRAPH ANALYTICS — MULE NETWORK MAP" |
| Hash label | "PATTERN HASH ENGINE — Zero PII Exported to Central Network" |
| Broadcast log (Bank B) | "Federated Threat Hash Received — Topological Pattern Match Initiated" |
| Block stamp | "BLOCKED — Zero-Day Fraud Prevention via Federated Learning. Privacy Maintained. (PDPL Art. 4 Compliant)" |
| Stats card (Bank B) | "0ms PII SHARED" |
| Control bar | "SAMA · PDPL · FL-COMPLIANT" |

---

## 7. What's Out of Scope

- Real backend or API calls
- Actual cryptography (hash is hardcoded string for demo)
- Mobile/responsive layout (optimized for 1920×1080 projector)
- Authentication or multi-user state
- react-force-graph or Vis.js (CSS/SVG graph is sufficient and avoids dependency risk)
