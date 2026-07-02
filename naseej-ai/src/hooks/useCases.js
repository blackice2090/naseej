// Investigator case state.
//
// Online (backend reachable): all reads and writes go through the case API,
// so the backend's transition rules, role permissions, access partitioning,
// PII guard, and audit log are exercised for real. The acting role comes
// from the backend's AuthContext (resolved from the API key), never from
// anything this client sends. Offline: the queue falls back to mock cases
// and mutations are local-only "safe mock controls" that mirror the same
// transition + role rules — clearly labelled in the UI via `usingMock`.

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  fetchCases, fetchWhoami, registerPattern, createCaseFromPattern,
  postCaseDecision, addCaseNote, feedbackFromCase,
} from '../lib/api'
import { MOCK_CASES, buildLocalDemoCase } from '../data/mockCases'
import { buildDemoPattern } from '../data/demoPattern'
import {
  DECISIONS, TRANSITIONS, MOCK_IDENTITY, canDecide, canAddNote, mockPiiCheck,
} from '../config/investigator'

const nowIso = () => new Date().toISOString()

export function useCases() {
  const [cases, setCases] = useState([])
  const [identity, setIdentity] = useState(null)
  const [usingMock, setUsingMock] = useState(false)
  const loadedRef = useRef(false)

  const refresh = useCallback(async () => {
    const data = await fetchCases()
    if (data?.cases) {
      setCases(data.cases)
      setUsingMock(false)
      const who = await fetchWhoami()
      setIdentity(who || MOCK_IDENTITY)
    } else if (!loadedRef.current) {
      setCases(MOCK_CASES)
      setIdentity(MOCK_IDENTITY)
      setUsingMock(true)
    }
    loadedRef.current = true
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const replaceCase = useCallback((updated) => {
    setCases(prev => prev.map(c => (c.case_id === updated.case_id ? updated : c)))
  }, [])

  // ── analyst actions (API when live, local mock otherwise) ───────────────

  const decide = useCallback(async (caseItem, decisionId, reason) => {
    if (!usingMock) {
      const resp = await postCaseDecision(caseItem.case_id, { decision: decisionId, reason })
      if (resp?.ok) {
        replaceCase(resp.data)
        // Auto-capture analyst feedback when the decision closes the case —
        // builds the calibration dataset (shadow only). Fire-and-forget; a
        // failure never affects the decision. The backend enforces all gates.
        if (String(resp.data?.status || '').startsWith('closed')) {
          feedbackFromCase(resp.data.case_id)
        }
        return { ok: true, feedbackCaptured: String(resp.data?.status || '').startsWith('closed') }
      }
      if (resp?.status === 403) return { ok: false, reasons: ['not permitted for your node/role'] }
      if (resp) return { ok: false, reasons: resp.data?.detail?.reasons || [String(resp.data?.detail || 'rejected')] }
      return { ok: false, reasons: ['backend unreachable'] }
    }
    // Mock mode: apply the same role + transition rules locally.
    if (!canDecide(MOCK_IDENTITY, caseItem, decisionId)) {
      return { ok: false, reasons: ['not permitted for your node/role (mock mode)'] }
    }
    if (mockPiiCheck(reason)) return { ok: false, reasons: ['note rejected by PII screen (mock mode)'] }
    const target = DECISIONS.find(d => d.id === decisionId)?.to
    if (!target || !TRANSITIONS[caseItem.status]?.includes(target)) {
      return { ok: false, reasons: [`invalid transition ${caseItem.status} → ${target}`] }
    }
    replaceCase({
      ...caseItem,
      status: target,
      updated_at: nowIso(),
      assigned_to: caseItem.assigned_to || MOCK_IDENTITY.node_id,
      false_positive_flag: caseItem.false_positive_flag || target === 'closed_false_positive',
      decision_history: [...caseItem.decision_history, {
        timestamp: nowIso(),
        node_id: MOCK_IDENTITY.node_id,
        decision: decisionId,
        reason,
        previous_status: caseItem.status,
        new_status: target,
        analyst_role: MOCK_IDENTITY.role,
        audit_ref: null,
      }],
    })
    return { ok: true }
  }, [usingMock, replaceCase])

  const addNote = useCallback(async (caseItem, note) => {
    if (!usingMock) {
      const resp = await addCaseNote(caseItem.case_id, { note })
      if (resp?.ok) { replaceCase(resp.data); return { ok: true } }
      if (resp?.status === 403) return { ok: false, reasons: ['not permitted for your node/role'] }
      if (resp) return { ok: false, reasons: resp.data?.detail?.reasons || ['rejected'] }
      return { ok: false, reasons: ['backend unreachable'] }
    }
    if (!canAddNote(MOCK_IDENTITY, caseItem)) {
      return { ok: false, reasons: ['not permitted for your node/role (mock mode)'] }
    }
    if (mockPiiCheck(note)) return { ok: false, reasons: ['note rejected by PII screen (mock mode)'] }
    replaceCase({
      ...caseItem,
      updated_at: nowIso(),
      analyst_notes: [...caseItem.analyst_notes, {
        timestamp: nowIso(), node_id: MOCK_IDENTITY.node_id, analyst_role: MOCK_IDENTITY.role, note,
      }],
    })
    return { ok: true }
  }, [usingMock, replaceCase])

  // ── demo integration: BLOCKED stage → a reviewable case ─────────────────

  const ingestDemoDetection = useCallback(async (livePattern) => {
    if (livePattern?.pattern_hash) {
      const pattern = buildDemoPattern(livePattern)
      const reg = await registerPattern(pattern)
      if (reg?.ok) {
        const created = await createCaseFromPattern(pattern.pattern_id)
        if (created?.ok) { await refresh(); return }
      }
    }
    // Offline (or registration failed): surface a local mock case instead.
    setCases(prev => [buildLocalDemoCase(), ...prev])
    setUsingMock(prev => prev || !livePattern?.pattern_hash)
  }, [refresh])

  const openCount = cases.filter(c => !c.status.startsWith('closed')).length

  return { cases, identity, usingMock, openCount, refresh, decide, addNote, ingestDemoDetection }
}
