// Naseej — Network Intelligence dashboard data model.
//
// ONE deterministic synthetic source of truth for every section of the
// Network Intelligence page. Nothing here is random: the same filters always
// produce the same numbers, so KPIs, the cross-bank map, the trend chart, the
// typology ranking and the decision summary always tell one consistent story.
//
// Privacy rule (same as the rest of the demo): NO PII, ever. Banks are
// fictional single letters; there are no accounts, names, IBANs, national IDs,
// phone numbers or raw transactions in this file — only fraud-pattern
// intelligence counts (privacy-safe pattern hashes and confirmed matches).

export const BANKS = ['Bank A', 'Bank B', 'Bank C', 'Bank D']

export const PATTERNS = ['Fan-in', 'Rapid Sweep', 'Gather-Scatter', 'Cycle']

export const PATTERN_EXPLANATIONS = {
  'Fan-in': 'Multiple source accounts transfer into one destination account.',
  'Rapid Sweep': 'Funds are moved out shortly after being received.',
  'Gather-Scatter': 'Funds are gathered into one account and redistributed.',
  Cycle: 'Funds move through multiple accounts and return to the origin.',
}

export const TIME_RANGES = [
  { id: '24h', label: 'Last 24 Hours', days: 1, medianDetection: 1.8 },
  { id: '7d', label: '7 Days', days: 7, medianDetection: 2.1 },
  { id: '30d', label: '30 Days', days: 30, medianDetection: 2.4 },
]

export const BANK_FILTERS = ['All Banks', ...BANKS]
export const PATTERN_FILTERS = ['All Patterns', ...PATTERNS]

// ── Event source ──────────────────────────────────────────────────────────
// A flat list of detection events across 30 days. Each event is one locally
// detected suspicious pattern. `matchBank` (when set) means a privacy-safe
// hash matched a pattern at another bank — i.e. a confirmed cross-bank match.

// Day 0 (the "Last 24 Hours" slice) is pinned by hand so the headline demo
// numbers are exact: 18 suspicious patterns, 6 cross-bank matches, and a
// typology split of Fan-in 7 · Rapid Sweep 5 · Gather-Scatter 4 · Cycle 2.
const DAY0 = [
  // Fan-in (7)
  { pattern: 'Fan-in', bank: 'Bank A', matchBank: 'Bank B', risk: 0.94, ms: 1500 },
  { pattern: 'Fan-in', bank: 'Bank B', matchBank: null, risk: 0.61, ms: 1650 },
  { pattern: 'Fan-in', bank: 'Bank C', matchBank: null, risk: 0.58, ms: 1720 },
  { pattern: 'Fan-in', bank: 'Bank A', matchBank: 'Bank B', risk: 0.88, ms: 1800 },
  { pattern: 'Fan-in', bank: 'Bank B', matchBank: null, risk: 0.55, ms: 1810 },
  { pattern: 'Fan-in', bank: 'Bank A', matchBank: null, risk: 0.63, ms: 1900 },
  { pattern: 'Fan-in', bank: 'Bank C', matchBank: 'Bank A', risk: 0.81, ms: 2100 },
  // Rapid Sweep (5)
  { pattern: 'Rapid Sweep', bank: 'Bank B', matchBank: null, risk: 0.6, ms: 1550 },
  { pattern: 'Rapid Sweep', bank: 'Bank A', matchBank: null, risk: 0.66, ms: 1700 },
  { pattern: 'Rapid Sweep', bank: 'Bank D', matchBank: 'Bank B', risk: 0.79, ms: 1780 },
  { pattern: 'Rapid Sweep', bank: 'Bank B', matchBank: null, risk: 0.52, ms: 1850 },
  { pattern: 'Rapid Sweep', bank: 'Bank A', matchBank: null, risk: 0.57, ms: 2000 },
  // Gather-Scatter (4)
  { pattern: 'Gather-Scatter', bank: 'Bank A', matchBank: 'Bank C', risk: 0.72, ms: 1600 },
  { pattern: 'Gather-Scatter', bank: 'Bank C', matchBank: null, risk: 0.64, ms: 1750 },
  { pattern: 'Gather-Scatter', bank: 'Bank A', matchBank: null, risk: 0.59, ms: 1880 },
  { pattern: 'Gather-Scatter', bank: 'Bank D', matchBank: 'Bank A', risk: 0.68, ms: 2050 },
  // Cycle (2)
  { pattern: 'Cycle', bank: 'Bank D', matchBank: null, risk: 0.62, ms: 1700 },
  { pattern: 'Cycle', bank: 'Bank B', matchBank: null, risk: 0.54, ms: 1950 },
]

// Deterministic generator for days 1..29. Pure integer arithmetic — no RNG —
// so the wider windows (7d / 30d) are always identical between renders.
function buildEvents() {
  const events = DAY0.map((e, i) => ({ ...e, day: 0, seq: i }))
  for (let d = 1; d < 30; d++) {
    const counts = d <= 6
      ? { 'Fan-in': 3, 'Rapid Sweep': 2, 'Gather-Scatter': 2, Cycle: 1 }
      : { 'Fan-in': 2, 'Rapid Sweep': 1, 'Gather-Scatter': 1, Cycle: 1 }
    let seq = 0
    PATTERNS.forEach((pattern, pIdx) => {
      const n = counts[pattern]
      for (let i = 0; i < n; i++) {
        const bank = BANKS[(d + i + pIdx) % 4]
        // Roughly one in three detections matches a pattern at another bank.
        const isMatch = (d + i + pIdx) % 3 === 0
        let matchBank = null
        if (isMatch) {
          matchBank = BANKS[(d + i + pIdx + 1) % 4]
          if (matchBank === bank) matchBank = BANKS[(d + i + pIdx + 2) % 4]
        }
        const risk = 0.5 + ((d * 7 + i * 13 + pIdx * 5) % 40) / 100
        const ms = 1500 + ((d * 3 + i * 7 + pIdx) % 20) * 60
        events.push({ pattern, bank, matchBank, risk: Math.round(risk * 100) / 100, ms, day: d, seq: seq++ })
      }
    })
  }
  return events
}

const ALL_EVENTS = buildEvents()

// Extra privacy-safe hashes shared on an edge beyond the confirmed matches —
// deterministic, so "shared hashes ≥ matches" always holds on the map. Tuned
// so the headline Bank A → Bank B edge reads "5 hashes · 2 matches" at 24h.
const EDGE_BASE_HASHES = {
  'Bank A->Bank B': 3,
  'Bank C->Bank A': 2,
  'Bank D->Bank B': 2,
  'Bank A->Bank C': 2,
  'Bank D->Bank A': 2,
}

// ── Curated priority cases ────────────────────────────────────────────────
// Five deterministic synthetic cases. These are the exact rows from the spec;
// IDs and scores are fixed. They link into the existing Investigator flow.
export const PRIORITY_CASES = [
  { id: 'NSJ-1042', bank: 'Bank B', pattern: 'Fan-in + Rapid Sweep', patternTag: 'Fan-in', risk: 0.94, crossBank: true, status: 'Critical', action: 'Review Now' },
  { id: 'NSJ-1038', bank: 'Bank A', pattern: 'Gather-Scatter', patternTag: 'Gather-Scatter', risk: 0.88, crossBank: true, status: 'High', action: 'Escalate' },
  { id: 'NSJ-1035', bank: 'Bank C', pattern: 'Fan-in', patternTag: 'Fan-in', risk: 0.81, crossBank: false, status: 'High', action: 'Analyst Review' },
  { id: 'NSJ-1032', bank: 'Bank D', pattern: 'Cycle', patternTag: 'Cycle', risk: 0.72, crossBank: true, status: 'Medium', action: 'Monitor' },
  { id: 'NSJ-1029', bank: 'Bank A', pattern: 'Velocity Anomaly', patternTag: null, risk: 0.65, crossBank: false, status: 'Medium', action: 'Observe' },
]

// ── Selectors ─────────────────────────────────────────────────────────────

const median = (arr) => {
  if (!arr.length) return 0
  const s = [...arr].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

function filterEvents({ timeRange, bank, pattern }) {
  const range = TIME_RANGES.find(r => r.id === timeRange) || TIME_RANGES[0]
  return ALL_EVENTS.filter(e =>
    e.day < range.days &&
    (bank === 'All Banks' || e.bank === bank) &&
    (pattern === 'All Patterns' || e.pattern === pattern),
  )
}

// Cross-bank map edges derived from the confirmed matches in the window. When
// a bank is filtered, only its incident edges are shown.
function buildEdges(events, bank) {
  const map = {}
  for (const e of events) {
    if (!e.matchBank) continue
    const key = `${e.bank}->${e.matchBank}`
    if (!map[key]) map[key] = { from: e.bank, to: e.matchBank, matches: 0, critical: false }
    map[key].matches += 1
    if (e.risk >= 0.9) map[key].critical = true
  }
  return Object.entries(map)
    .map(([key, v]) => ({ ...v, hashes: v.matches + (EDGE_BASE_HASHES[key] || 1) }))
    .filter(edge => bank === 'All Banks' || edge.from === bank || edge.to === bank)
    .sort((a, b) => b.matches - a.matches || b.hashes - a.hashes)
}

// Trend series: the four typologies counted across evenly-sized buckets of the
// window. Bucket count/label adapts to the range so the x-axis stays readable.
function buildTrend(events, range) {
  const buckets = range.days === 1
    ? { count: 6, span: 1, label: (i) => `${(5 - i) * 4}h` } // 4-hour buckets across a day
    : range.days === 7
      ? { count: 7, span: 1, label: (i) => `D${range.days - i}` }
      : { count: 5, span: 6, label: (i) => `W${5 - i}` } // ~weekly buckets across 30d
  const series = Array.from({ length: buckets.count }, (_, i) => {
    const row = { label: buckets.label(i) }
    PATTERNS.forEach(p => { row[p] = 0 })
    return row
  })
  for (const e of events) {
    // Map an event's day to a bucket index (older days → earlier buckets).
    const idx = range.days === 1
      ? Math.min(buckets.count - 1, Math.floor((e.seq / DAY0.length) * buckets.count))
      : Math.min(buckets.count - 1, Math.floor(e.day / buckets.span))
    const b = buckets.count - 1 - idx
    if (series[b]) series[b][e.pattern] += 1
  }
  return series
}

export function buildDashboard(filters) {
  const range = TIME_RANGES.find(r => r.id === filters.timeRange) || TIME_RANGES[0]
  const events = filterEvents(filters)
  const crossBankEvents = events.filter(e => e.matchBank)

  const typologyCounts = {}
  PATTERNS.forEach(p => { typologyCounts[p] = 0 })
  events.forEach(e => { typologyCounts[e.pattern] += 1 })

  const typologies = PATTERNS
    .map(p => ({ pattern: p, count: typologyCounts[p], explanation: PATTERN_EXPLANATIONS[p] }))
    .sort((a, b) => b.count - a.count)

  const kpis = {
    suspiciousPatterns: events.length,
    crossBankMatches: crossBankEvents.length,
    // Median detection is a window-level characteristic; when the exact spec
    // window is unfiltered we surface the pinned figure, otherwise the derived
    // median of the filtered events (kept honest either way).
    medianDetection: events.length
      ? (filters.bank === 'All Banks' && filters.pattern === 'All Patterns'
          ? range.medianDetection
          : Math.round(median(events.map(e => e.ms)) / 100) / 10)
      : 0,
    zeroPii: 100,
  }

  const edges = buildEdges(events, filters.bank)
  const trend = buildTrend(events, range)

  // Priority cases respect the bank / pattern filters but not time (they are
  // the current standing queue). Filtered to nothing → show all (never empty).
  let cases = PRIORITY_CASES.filter(c =>
    (filters.bank === 'All Banks' || c.bank === filters.bank) &&
    (filters.pattern === 'All Patterns' || c.patternTag === filters.pattern),
  )
  if (cases.length === 0) cases = PRIORITY_CASES

  const criticalCount = cases.filter(c => c.status === 'Critical').length

  // Decision summary derived from the current window.
  const riskStatus = kpis.crossBankMatches >= 4 ? 'ELEVATED'
    : kpis.crossBankMatches >= 1 ? 'GUARDED' : 'STABLE'

  return {
    range,
    filters,
    kpis,
    typologies,
    topPattern: typologies[0],
    edges,
    trend,
    cases,
    criticalCount,
    riskStatus,
    // Governance numbers — deterministic synthetic evidence (labelled as such
    // in the UI). Real live governance flags come from the backend separately.
    governance: {
      zeroPii: 100,
      piiBlocked: 7,
      auditedActions: 248,
      humanReview: 100,
      hashIntegrity: 'Verified',
      sharingScope: 'Network Approved',
    },
  }
}

export const DEFAULT_FILTERS = { timeRange: '24h', bank: 'All Banks', pattern: 'All Patterns' }
