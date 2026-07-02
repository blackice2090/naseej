// Investigator view — status machine mirror, decision catalog, and copy.
//
// TRANSITIONS and DECISION_TO_STATUS mirror backend/app/services/
// case_service.py. The backend is authoritative (it rejects invalid
// transitions with 409); the mirror only decides which buttons to enable.

export const TRANSITIONS = {
  open: ['under_review', 'escalated', 'closed_no_action'],
  under_review: ['escalated', 'closed_confirmed', 'closed_false_positive', 'closed_no_action'],
  escalated: ['under_review', 'closed_confirmed', 'closed_false_positive', 'closed_no_action'],
  closed_confirmed: [],
  closed_false_positive: [],
  closed_no_action: [],
}

export const DECISIONS = [
  { id: 'take_under_review',   label: 'TAKE UNDER REVIEW', to: 'under_review' },
  { id: 'escalate',            label: 'ESCALATE',          to: 'escalated' },
  { id: 'confirm_fraud',       label: 'CONFIRM FRAUD',     to: 'closed_confirmed' },
  { id: 'mark_false_positive', label: 'FALSE POSITIVE',    to: 'closed_false_positive' },
  { id: 'close_no_action',     label: 'CLOSE — NO ACTION', to: 'closed_no_action' },
]

export const STATUS_META = {
  open:                  { label: 'OPEN',            color: '#4fc3f7' },
  under_review:          { label: 'UNDER REVIEW',    color: '#fbbf24' },
  escalated:             { label: 'ESCALATED',       color: '#7c4dff' },
  closed_confirmed:      { label: 'CONFIRMED FRAUD', color: '#ff4d6b' },
  closed_false_positive: { label: 'FALSE POSITIVE',  color: '#8a9bbf' },
  closed_no_action:      { label: 'NO ACTION',       color: '#5a6a8a' },
}

export const TIER_COLORS = {
  critical: '#ff4d6b',
  high: '#fbbf24',
  medium: '#4fc3f7',
  low: '#5a6a8a',
}

// Plain-language typology explanations for the "Why flagged?" panel.
export const TYPOLOGY_EXPLANATIONS = {
  fan_in: 'Multiple unrelated sources funnel funds into one account — the classic collection stage of a mule operation.',
  fan_out: 'One account rapidly distributes funds to many recipients — the dispersal stage of layering.',
  simple_cycle: 'Funds travel a closed loop of accounts and return near the origin — circular layering to obscure provenance.',
  mule_velocity: 'An account receives a burst of inflows and forwards the balance almost immediately — money is parked for minutes, not held.',
  rapid_sweep: 'An accumulated balance exits in a single large transfer shortly after collection — the cash-out step.',
  cross_bank_pass_through: 'Funds enter from one institution and exit to another with minimal dwell time — using the bank as a corridor.',
  scatter_gather: 'Funds split across many accounts, then reconverge at a new destination — split-and-merge layering.',
  gather_scatter: 'Funds converge into one account, then split outward to many — the inverse staging pattern.',
}

export const ACTION_META = {
  monitor: {
    label: 'MONITOR',
    explanation: 'Risk is below intervention thresholds. Keep the pattern under observation; no customer impact.',
  },
  request_step_up_verification: {
    label: 'REQUEST STEP-UP VERIFICATION',
    explanation: 'Ask the customer-facing channel to require additional verification before further transfers.',
  },
  delay_transaction: {
    label: 'DELAY TRANSACTION',
    explanation: 'Hold settlement within the regulatory window to allow analyst review before funds leave.',
  },
  freeze_for_review: {
    label: 'FREEZE FOR REVIEW',
    explanation: 'Critical risk: recommend a temporary administrative freeze pending senior analyst review.',
  },
  escalate_to_compliance: {
    label: 'ESCALATE TO COMPLIANCE',
    explanation: 'Cross-bank scope at high risk: route to the compliance function for inter-institution coordination.',
  },
}

export const HITL_NOTICE =
  'Recommendations only — no action is executed by Naseej. A human analyst must review, decide, and is accountable for every status change.'

// ── Identity & role-based UI gating ─────────────────────────────────────────
// The backend resolves identity from the API key (GET /api/auth/whoami) and
// enforces every rule server-side; these mirrors only decide what the UI
// disables. Offline mock identity matches the Bank A dev key's profile
// (analyst), so the mock behaves like the live backend would.

export const MOCK_IDENTITY = {
  node_id: 'NODE_A7C2F9E1',
  display_name: 'Bank A',
  node_type: 'bank',
  role: 'analyst',
  permissions: [
    'cases:close_no_action', 'cases:create', 'cases:note',
    'cases:take_under_review', 'patterns:publish', 'patterns:view_network',
  ],
}

// Decision id → permission string used by the backend.
export const decisionPermission = (decisionId) => `cases:${decisionId}`

// Lowest role that may take each decision — for "requires X" messages only.
export const DECISION_MIN_ROLE = {
  take_under_review: 'analyst',
  close_no_action: 'analyst',
  escalate: 'senior_analyst',
  mark_false_positive: 'senior_analyst',
  confirm_fraud: 'mlro',
}

export function canDecide(identity, caseItem, decisionId) {
  if (!identity) return false
  // Ownership: a node only works its own cases (legacy mocks without an
  // owner field fall back to the pattern's source node, like the backend).
  const owner = caseItem.owner_node_id || caseItem.source_node_id
  if (identity.node_id !== owner) return false
  return identity.permissions.includes(decisionPermission(decisionId))
}

export function canAddNote(identity, caseItem) {
  if (!identity) return false
  const owner = caseItem.owner_node_id || caseItem.source_node_id
  return identity.node_id === owner && identity.permissions.includes('cases:note')
}

// Minimal client-side PII screen for offline mock mode, mirroring the main
// rules of the backend guard (which remains authoritative when online).
const MOCK_PII_RULES = [
  /[؀-ۿ]/,                                  // Arabic script (may embed names)
  /\b[A-Z]{2}\d{2}[ -]?[A-Z0-9][ \-A-Z0-9]{8,}\b/,    // IBAN-like
  /\+\d[\d \-]{7,}|\b0\d{9,}\b/,                      // phone-like
  /\d{8,}/,                                           // long digit run
  /\bACC[_-][A-Za-z0-9_-]{2,}\b|\b0x[A-Za-z0-9_]{3,}\b/, // account handles
  /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/,   // email
]

export function mockPiiCheck(text) {
  return MOCK_PII_RULES.some((re) => re.test(text))
}
