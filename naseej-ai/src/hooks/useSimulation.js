// Naseej demo — simulation engine.
//
// Owns the five-stage state machine (IDLE → ATTACK → DETECTED →
// BROADCASTING → BLOCKED), the idle transaction feeds, and the live
// backend scoring calls. Reset-safe: every pending timeout is tracked
// and cleared so the demo can be restarted mid-run without ghost
// transitions.

import { useState, useEffect, useRef, useCallback } from 'react'
import { STAGES, TIMINGS } from '../config/constants'
import {
  ATTACK_SEQUENCE, TX_POOL_A, TX_POOL_B, ACCOMPLICE_TX, generateRandomTx,
} from '../data/mockData'
import {
  scoreTransaction, analyzePattern, ingestFeatureTransaction, scoreWithContext, scoreShadow,
} from '../lib/api'

// The demo replays the attack against synthetic AMLworld bank ids.
const BANK_A_ID = '101'
const BANK_B_ID = '28856'

function attackTxToApiPayload(tx, isSweep) {
  return {
    timestamp: new Date().toISOString(),
    from_bank: BANK_A_ID,
    from_account: tx.from,
    to_bank: isSweep ? BANK_B_ID : BANK_A_ID,
    to_account: tx.to,
    amount: tx.amount,
    currency: 'US Dollar',
    payment_format: isSweep ? 'Wire' : 'ACH',
  }
}

let demoTxSeq = 0

export function useSimulation() {
  const [stage, setStage] = useState(STAGES.IDLE)
  const [bankATxs, setBankATxs] = useState([])
  const [bankBTxs, setBankBTxs] = useState([])
  const [blockedTx, setBlockedTx] = useState(null)
  const [liveScore, setLiveScore] = useState(null)
  const [livePattern, setLivePattern] = useState(null)
  const [liveContextScore, setLiveContextScore] = useState(null)
  const [liveShadowScore, setLiveShadowScore] = useState(null)

  const timeoutIds = useRef([])

  const schedule = useCallback((fn, delay) => {
    const id = setTimeout(fn, delay)
    timeoutIds.current.push(id)
    return id
  }, [])

  // Idle feeds: both banks process normal synthetic transactions.
  useEffect(() => {
    if (stage !== STAGES.IDLE) return
    const id = setInterval(() => {
      setBankATxs(prev => [...prev.slice(-49), generateRandomTx(TX_POOL_A)])
      setBankBTxs(prev => [...prev.slice(-49), generateRandomTx(TX_POOL_B)])
    }, TIMINGS.IDLE_TX_INTERVAL_MS)
    return () => clearInterval(id)
  }, [stage])

  // Score the sweep transaction the moment the attack starts (live XGBoost
  // inference when the backend is up; silently skipped when offline).
  useEffect(() => {
    if (stage !== STAGES.ATTACK) return
    const sweep = ATTACK_SEQUENCE[ATTACK_SEQUENCE.length - 1]
    scoreTransaction(attackTxToApiPayload(sweep, true))
      .then(data => { if (data?.risk_score != null) setLiveScore(data) })
  }, [stage])

  // Analyze the full attack topology when detection fires — this is the
  // call that produces the real NSJ_* pattern hash. The feature store
  // (fed during ATTACK) lets the backend confirm fan-in/sweep against
  // real rolling windows; score-with-context returns the contextual
  // velocity explanations shown in the research strip.
  useEffect(() => {
    if (stage !== STAGES.DETECTED) return
    const transactions = ATTACK_SEQUENCE.map((tx, i) =>
      attackTxToApiPayload(tx, i === ATTACK_SEQUENCE.length - 1))
    analyzePattern(transactions)
      .then(data => { if (data?.risk_score != null) setLivePattern(data) })
    const sweep = ATTACK_SEQUENCE[ATTACK_SEQUENCE.length - 1]
    scoreWithContext(attackTxToApiPayload(sweep, true))
      .then(data => { if (data?.final_contextual_score != null) setLiveContextScore(data) })
    // Shadow candidate scored side-by-side with the baseline — comparison
    // only, never drives the demo. Hidden unless the candidate is available.
    scoreShadow(attackTxToApiPayload(sweep, true))
      .then(data => { if (data?.candidate_available) setLiveShadowScore(data) })
  }, [stage])

  const run = useCallback(() => {
    if (stage !== STAGES.IDLE) return
    setStage(STAGES.ATTACK)

    ATTACK_SEQUENCE.forEach((tx, i) => {
      const isSweep = i === ATTACK_SEQUENCE.length - 1
      schedule(() => {
        setBankATxs(prev => [
          ...prev.slice(-49),
          {
            id: `TX#ATK_0${i + 1}`,
            from: tx.from,
            to: tx.to,
            amount: tx.amount,
            status: isSweep ? 'FLAGGED' : 'CLEAR',
            ts: Date.now(),
          },
        ])
        // Feed Bank A's node-local feature store as each synthetic
        // transaction lands (fire-and-forget; offline → null, demo intact).
        ingestFeatureTransaction({
          transaction_id: `TX-DEMO-${Date.now()}-${demoTxSeq++}`,
          ...attackTxToApiPayload(tx, isSweep),
        })
      }, i * TIMINGS.ATTACK_TX_GAP_MS)
    })

    schedule(() => setStage(STAGES.DETECTED), TIMINGS.DETECT_AT_MS)
    schedule(() => setStage(STAGES.BROADCASTING), TIMINGS.BROADCAST_AT_MS)
    schedule(() => {
      setStage(STAGES.BLOCKED)
      setBlockedTx(ACCOMPLICE_TX)
    }, TIMINGS.BLOCK_AT_MS)
  }, [stage, schedule])

  const reset = useCallback(() => {
    timeoutIds.current.forEach(clearTimeout)
    timeoutIds.current = []
    setStage(STAGES.IDLE)
    setBankATxs([])
    setBankBTxs([])
    setBlockedTx(null)
    setLiveScore(null)
    setLivePattern(null)
    setLiveContextScore(null)
    setLiveShadowScore(null)
  }, [])

  return {
    stage, bankATxs, bankBTxs, blockedTx,
    liveScore, livePattern, liveContextScore, liveShadowScore, run, reset,
  }
}
