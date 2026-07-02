// Naseej demo — simulation stages, timings, and theme tokens.

export const STAGES = { IDLE: 0, ATTACK: 1, DETECTED: 2, BROADCASTING: 3, BLOCKED: 4 }

// Demo placeholder in the real engine's format (ml/src/privacy_hash.py):
// NSJ_<PATTERN_TYPE>_<16-hex-chars>. The live hash is returned by
// POST /api/analyze-pattern when the backend is running.
export const THREAT_HASH = 'NSJ_MULE_VELOCITY_8f9b2c4d1e7a3c5d'

// All simulation timings in one place so the demo choreography is auditable.
export const TIMINGS = {
  IDLE_TX_INTERVAL_MS: 1200,   // normal transaction cadence per bank
  ATTACK_TX_GAP_MS: 280,       // gap between injected attack transfers
  DETECT_AT_MS: 2500,          // graph analytics flags the mule pattern
  BROADCAST_AT_MS: 4000,       // zero-PII hash leaves Bank A
  BLOCK_AT_MS: 5500,           // Bank B flags the matching transaction for analyst review
  HASH_SCRAMBLE_MS: 1500,      // matrix-decode phase before hash reveal
}

// Theme tokens — single source for the palette used across components.
export const COLORS = {
  bg: '#07090f',
  cyan: '#4fc3f7',      // Bank A / primary accent
  violet: '#7c4dff',    // Bank B / network accent
  green: '#00e676',     // safe / compliant
  red: '#ff4d6b',       // threat / blocked
  amber: '#fbbf24',     // flagged / review
  textPrimary: '#e0e8ff',
  textMuted: '#8a9bbf',
  textDim: '#4a5a7a',
  textFaint: '#3a4a6a',
  line: 'rgba(255,255,255,0.06)',
  panelGlass: 'rgba(10,15,30,0.65)',
}

export const SCRAMBLE_CHARS =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789#$%@!&*^~<>?/'
