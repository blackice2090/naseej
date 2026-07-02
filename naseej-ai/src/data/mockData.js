// Naseej demo — synthetic simulation data and offline fallbacks.
//
// Privacy rule: even the mock data carries no PII — account handles only,
// no names, IBANs, or identifiers that resemble real ones.

// Fan-in mule pattern: five micro-transfers into one account, then a sweep.
export const ATTACK_SEQUENCE = [
  { from: '0xSRC_A1', to: '0xMULE_01', amount: 2400, label: 'Micro-transfer 1/5' },
  { from: '0xSRC_A2', to: '0xMULE_01', amount: 1850, label: 'Micro-transfer 2/5' },
  { from: '0xSRC_A3', to: '0xMULE_01', amount: 3100, label: 'Micro-transfer 3/5' },
  { from: '0xSRC_A4', to: '0xMULE_01', amount: 990,  label: 'Micro-transfer 4/5' },
  { from: '0xSRC_A5', to: '0xMULE_01', amount: 1760, label: 'Micro-transfer 5/5' },
  { from: '0xMULE_01', to: '0xINTL_DEST', amount: 11200, label: 'SWEEP — International Wire' },
]

// Synthetic account handles for the idle transaction feeds.
export const TX_POOL_A = ['0xA1B2', '0xC3D4', '0xE5F6', '0xG7H8', '0xI9J0']
export const TX_POOL_B = ['0xB1C2', '0xD3E4', '0xF5G6', '0xH7I8']

// The accomplice transaction Bank B flags for analyst review via hash match.
export const ACCOMPLICE_TX = {
  id: 'TX#ACC_01',
  from: '0xACCOMPLICE',
  to: '0xINTL_DEST',
  amount: 9800,
  status: 'FLAGGED',
}

let txSeq = 1000

export function generateRandomTx(pool) {
  const from = pool[Math.floor(Math.random() * pool.length)]
  let to = pool[Math.floor(Math.random() * pool.length)]
  while (to === from) to = pool[Math.floor(Math.random() * pool.length)]
  return {
    id: `TX#${(txSeq++).toString(16).toUpperCase()}`,
    from,
    to,
    amount: Math.floor(Math.random() * 4800) + 200,
    status: 'CLEAR',
    ts: Date.now(),
  }
}

// ── Offline fallbacks ────────────────────────────────────────────────────
// These mirror the real evaluation reports (ml/reports/model_metrics.json,
// ml/reports/cross_bank_results.json) so the demo never overstates the
// model when the backend is offline. Update them when the model is retrained.

export const FALLBACK_METRICS = {
  model_name: 'xgboost',
  pr_auc: 0.2275,
  precision: 0.2727,
  recall: 0.1957,
  f1: 0.2278,
  threshold: 0.0606,
  n_alerts: 33,
  n_confirmed_laundering: 9,
}

// What the live feature store reports for the demo attack (5 fan-in
// transfers then the sweep). Shown only when the backend is offline,
// always labelled SIMULATED — mirrors the rule layer in
// backend/app/api/routes_features.py, never overstating it.
export const FALLBACK_CONTEXT_EXPLANATIONS = [
  '5 inbound transfers within 10 minutes',
  'International sweep after fan-in',
  'New beneficiary bucket',
  'Cross-bank velocity spike',
]

export const FALLBACK_CROSS_BANK = {
  avg_recall_A_private: 0.3889,
  avg_recall_B_shared:  0.4444,
  avg_recall_C_naseej:  0.6667,
  gain_recall_C_over_A: 0.2778,
}

// Offline mirror of the ML evaluation reports (ml/reports/model_comparison.json,
// per_typology_recall.json, threshold_analysis.json). Shown only when the
// backend is offline, always labelled as the synthetic-benchmark result it is.
// Mirrors the held-out test leader; update when the suite is re-run.
export const FALLBACK_MODEL_EVIDENCE = {
  bestModel: 'lightgbm',
  prAuc: 0.6118,
  f1: 0.5935,
  thresholdMode: 'balanced',
  weakestTypology: 'mule_velocity',
  lightgbmEvaluated: true,
}
