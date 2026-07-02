// Naseej demo — backend API layer.
//
// Every call degrades to null on failure so the browser-only demo keeps
// working when the FastAPI backend (port 8000) is not running.

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// Bank-node API key. The default is the backend's local-simulation dev key
// (active only when the backend has no NASEEJ_NODE_KEYS configured); real
// deployments set VITE_NASEEJ_API_KEY. A wrong key means 401 → apiFetch
// returns null → the demo falls back to offline values, never breaks.
const API_KEY = import.meta.env.VITE_NASEEJ_API_KEY || 'dev-key-bank-a-local-only'

export const API_HOST_LABEL = API_BASE.replace(/^https?:\/\//, '')

async function apiFetch(path, init = {}) {
  try {
    const resp = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: AbortSignal.timeout(2500),
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
        ...(init.headers || {}),
      },
    })
    if (!resp.ok) return null
    return resp.json()
  } catch {
    return null
  }
}

// Backend-resolved identity (node, role, permissions). The UI only mirrors
// these to disable actions; the backend stays authoritative.
export function fetchWhoami() {
  return apiFetch('/api/auth/whoami')
}

export function fetchModelMetrics() {
  return apiFetch('/api/model/metrics')
}

export function fetchCrossBankResults() {
  return apiFetch('/api/cross-bank/results')
}

// ── ML evaluation reports (read-only research artefacts) ──────────────────

export function fetchModelComparison() {
  return apiFetch('/api/model/comparison')
}

export function fetchPerTypologyRecall() {
  return apiFetch('/api/model/per-typology-recall')
}

export function fetchThresholdAnalysis() {
  return apiFetch('/api/model/threshold-analysis')
}

// Shadow candidate model (read-only; NOT deployed).
export function fetchCandidateMetrics() {
  return apiFetch('/api/model/candidate/metrics')
}

// Live shadow score — comparison-only, never drives decisions. Node-keyed.
export function scoreShadow(tx) {
  return apiFetch('/api/model/candidate/score-shadow', {
    method: 'POST',
    body: JSON.stringify(tx),
  })
}

// Node-scoped aggregate shadow monitoring (bucketed; prototype only).
export function fetchShadowMonitoring() {
  return apiFetch('/api/model/candidate/shadow-monitoring')
}

// Node-scoped calibration dataset summary (aggregate; not production calibration).
export function fetchCalibrationDataset() {
  return apiFetch('/api/feedback/calibration-dataset')
}

// Public governance evidence pack (read-only; aggregate/structural only).
export function fetchGovernanceEvidence() {
  return apiFetch('/api/demo/governance-evidence')
}

// Capture analyst feedback from a closed case (calibration label). Node-keyed.
export function feedbackFromCase(caseId) {
  return apiSend(`/api/feedback/from-case/${caseId}`, { method: 'POST' })
}

// ── Explainability ("Why flagged?") ───────────────────────────────────────

export function fetchCaseExplanation(caseId) {
  return apiFetch(`/api/explain/case/${caseId}`)
}

export function fetchModelExplanation() {
  return apiFetch('/api/explain/model')
}

export function scoreTransaction(tx) {
  return apiFetch('/api/score-transaction', {
    method: 'POST',
    body: JSON.stringify(tx),
  })
}

// ── Feature store (node-local velocity/context features) ──────────────────
// Ingestion needs the authenticated node id as source_node_id; resolve it
// once via whoami and cache the promise. Offline → null → demo falls back.

let whoamiPromise = null
function cachedWhoami() {
  if (!whoamiPromise) whoamiPromise = apiFetch('/api/auth/whoami')
  return whoamiPromise
}

export async function ingestFeatureTransaction(tx) {
  const identity = await cachedWhoami()
  if (!identity?.node_id) return null
  return apiFetch('/api/features/ingest-transaction', {
    method: 'POST',
    body: JSON.stringify({ ...tx, source_node_id: identity.node_id }),
  })
}

export function scoreWithContext(tx) {
  return apiFetch('/api/features/score-with-context', {
    method: 'POST',
    body: JSON.stringify(tx),
  })
}

export function fetchFeatureStatus() {
  return apiFetch('/api/features/status')
}

export function analyzePattern(transactions) {
  return apiFetch('/api/analyze-pattern', {
    method: 'POST',
    body: JSON.stringify({ transactions }),
  })
}

// ── Case management ────────────────────────────────────────────────────────
// Mutations use apiSend (status-aware) so the UI can distinguish a PII-guard
// rejection (422, with reasons) from being offline (null).

async function apiSend(path, init = {}) {
  try {
    const resp = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: AbortSignal.timeout(2500),
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
        ...(init.headers || {}),
      },
    })
    const data = await resp.json().catch(() => null)
    return { ok: resp.ok, status: resp.status, data }
  } catch {
    return null // offline
  }
}

export function registerPattern(pattern) {
  return apiSend('/api/patterns', { method: 'POST', body: JSON.stringify(pattern) })
}

export function createCaseFromPattern(patternId) {
  return apiSend(`/api/cases/from-pattern/${patternId}`, { method: 'POST' })
}

export function fetchCases() {
  return apiFetch('/api/cases')
}

export function postCaseDecision(caseId, body) {
  return apiSend(`/api/cases/${caseId}/decision`, { method: 'POST', body: JSON.stringify(body) })
}

export function addCaseNote(caseId, body) {
  return apiSend(`/api/cases/${caseId}/notes`, { method: 'POST', body: JSON.stringify(body) })
}
