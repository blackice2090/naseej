import { useState, useEffect } from 'react'
import { AlertTriangle, Lock, Shield, FileText, ArrowUpRight, ArrowDownRight, Cpu } from 'lucide-react'
import SectionLabel from '../ui/SectionLabel'
import { fetchCaseExplanation } from '../../lib/api'
import {
  STATUS_META, TIER_COLORS, DECISIONS, TRANSITIONS,
  TYPOLOGY_EXPLANATIONS, ACTION_META, HITL_NOTICE,
  canDecide, canAddNote, DECISION_MIN_ROLE,
} from '../../config/investigator'

const panelStyle = {
  background: 'rgba(10,15,30,0.65)',
  border: '1px solid rgba(255,255,255,0.06)',
  backdropFilter: 'blur(8px)',
}

function fmt(iso) {
  return iso ? iso.replace('T', ' ').slice(0, 16) + ' UTC' : '—'
}

// ── Why flagged? ───────────────────────────────────────────────────────────

const LEVEL_COLOR = { high: '#ff4d6b', medium: '#fbbf24', low: '#4fc3f7' }

// Backend-derived risk factors (SHAP or deterministic fallback). Bucketed
// values only — never raw figures.
function FactorList({ factors }) {
  if (!factors?.length) return null
  return (
    <div className="flex flex-col gap-1 mt-1.5">
      {factors.slice(0, 4).map((f, i) => {
        const up = f.direction === 'increases_risk'
        const Arrow = up ? ArrowUpRight : ArrowDownRight
        const color = LEVEL_COLOR[f.contribution_level] || '#5a6a8a'
        return (
          <div key={i} className="flex items-center gap-2">
            <Arrow size={11} style={{ color: up ? '#ff6b8a' : '#4fc3f7', flexShrink: 0 }} />
            <span className="text-[9px]" style={{ color: '#c9d8f5', minWidth: 0 }}>
              {f.human_label}
            </span>
            <span className="font-mono text-[8px] px-1 rounded shrink-0"
              style={{ color: '#7a8aa8', background: '#0d1525', border: '1px solid #1a2744' }}>
              {f.value_bucket}
            </span>
            <span className="font-mono text-[7px] tracking-widest shrink-0" style={{ color }}>
              {f.contribution_level.toUpperCase()}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function WhyFlagged({ caseItem, explanation }) {
  const typ = explanation?.typology_factors?.[0]
  const method = explanation?.explanation_method
  const methodLabel = method === 'shap' ? 'SHAP'
    : method === 'fallback' ? 'FALLBACK ATTRIBUTION'
    : method === 'rule' ? 'RULE-DERIVED' : null

  return (
    <div className="rounded p-3" style={panelStyle}>
      <div className="flex items-center justify-between mb-1">
        <SectionLabel>WHY FLAGGED?</SectionLabel>
        {methodLabel && (
          <span className="flex items-center gap-1 font-mono text-[7px] tracking-widest px-1.5 py-0.5 rounded"
            style={{ color: '#7c4dff', border: '1px solid #7c4dff33', background: '#7c4dff0d' }}>
            <Cpu size={8} /> {methodLabel}
          </span>
        )}
      </div>

      {/* Typology — backend explanation when live, static copy otherwise */}
      <div className="text-[10px] leading-relaxed mb-1" style={{ color: '#aab' }}>
        {typ?.what_detected || TYPOLOGY_EXPLANATIONS[caseItem.typology]
          || 'Pattern matched a registered network typology.'}
      </div>
      {typ?.why_it_matters && (
        <div className="text-[9px] leading-relaxed mb-1.5" style={{ color: '#8a9bbf' }}>
          {typ.why_it_matters}
        </div>
      )}
      <div className="text-[10px] leading-relaxed italic" style={{ color: '#7a8aa8' }}>
        “{caseItem.evidence_summary}”
      </div>

      {/* Top risk factors */}
      {explanation?.top_factors?.length > 0 && (
        <div className="mt-2">
          <span className="text-[8px] tracking-widest" style={{ color: '#5a6a8a' }}>TOP RISK FACTORS</span>
          <FactorList factors={explanation.top_factors} />
        </div>
      )}

      {/* Contextual velocity/counterparty factors */}
      {explanation?.contextual_factors?.length > 0 && (
        <div className="mt-2">
          <span className="text-[8px] tracking-widest" style={{ color: '#5a6a8a' }}>CONTEXT SIGNALS</span>
          <div className="flex flex-col gap-0.5 mt-1">
            {explanation.contextual_factors.slice(0, 4).map((c, i) => (
              <div key={i} className="text-[9px] leading-snug" style={{ color: '#8a9bbf' }}>› {c}</div>
            ))}
          </div>
        </div>
      )}

      {/* Risk / confidence bars */}
      <div className="flex gap-5 mt-2.5">
        {[['RISK SCORE', caseItem.risk_score, TIER_COLORS[caseItem.risk_tier]],
          ['CONFIDENCE', caseItem.confidence, '#4fc3f7']].map(([label, val, color]) => (
          <div key={label} className="flex items-center gap-2">
            <span className="text-[8px] tracking-widest" style={{ color: '#5a6a8a' }}>{label}</span>
            <div className="rounded-full overflow-hidden" style={{ width: 70, height: 4, background: '#0d1525' }}>
              <div style={{ width: `${val * 100}%`, height: '100%', background: color, borderRadius: 99 }} />
            </div>
            <span className="font-mono font-bold text-[10px]" style={{ color }}>
              {(val * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>

      {/* Threshold rationale + limitations (honest small print) */}
      {explanation && (
        <div className="mt-2 pt-2 flex flex-col gap-1" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          {explanation.threshold_rationale?.policy && (
            <div className="text-[8px] leading-snug" style={{ color: '#6a7a9a' }}>
              <span style={{ color: '#5a6a8a' }}>THRESHOLD · </span>{explanation.threshold_rationale.policy}
            </div>
          )}
          {explanation.model_limitations?.[0] && (
            <div className="text-[8px] leading-snug italic" style={{ color: '#5a6a8a' }}>
              {explanation.model_limitations[0]}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Recommended action + analyst decision ──────────────────────────────────

function DecisionPanel({ caseItem, onDecide, identity, usingMock }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const action = ACTION_META[caseItem.recommended_action]
  const allowed = TRANSITIONS[caseItem.status] || []
  const closed = caseItem.status.startsWith('closed')

  // Actions the status machine allows but this node/role may not take —
  // mirrored from the backend (which enforces it regardless of the UI).
  const isOwner = !!identity
    && identity.node_id === (caseItem.owner_node_id || caseItem.source_node_id)
  const roleBlocked = DECISIONS.filter(
    d => allowed.includes(d.to) && !canDecide(identity, caseItem, d.id),
  )

  const handle = async (decisionId) => {
    setError(null)
    if (reason.trim().length < 3) {
      setError('A decision reason is required — it becomes part of the case record.')
      return
    }
    setBusy(true)
    const result = await onDecide(caseItem, decisionId, reason.trim())
    setBusy(false)
    if (!result.ok) setError(result.reasons.join(' · '))
    else setReason('')
  }

  return (
    <div className="rounded p-3" style={panelStyle}>
      <SectionLabel>RECOMMENDED ACTION</SectionLabel>
      <div className="flex items-center gap-2 mb-1">
        <Shield size={12} style={{ color: '#fbbf24' }} />
        <span className="font-mono font-bold text-[12px] tracking-wider" style={{ color: '#fbbf24' }}>
          {action?.label || caseItem.recommended_action.toUpperCase()}
        </span>
      </div>
      <div className="text-[9px] leading-relaxed mb-1" style={{ color: '#7a8aa8' }}>
        {action?.explanation}
      </div>
      <div className="flex items-start gap-1.5 mb-3">
        <Lock size={9} style={{ color: '#00e676', marginTop: 1, flexShrink: 0 }} />
        <span className="text-[8px] leading-snug" style={{ color: '#00e676' }}>{HITL_NOTICE}</span>
      </div>

      <SectionLabel>ANALYST DECISION</SectionLabel>
      {closed ? (
        <div className="flex flex-col gap-1">
          <div className="text-[9px] tracking-widest" style={{ color: '#5a6a8a' }}>
            CASE CLOSED — STATUS IS TERMINAL. HISTORY BELOW IS THE RECORD.
          </div>
          {!usingMock && (
            <div className="text-[8px] tracking-wider" style={{ color: '#00e676' }}>
              ✓ OUTCOME CAPTURED FOR CALIBRATION DATASET · SHADOW ONLY — NOT PRODUCTION CALIBRATION
            </div>
          )}
        </div>
      ) : (
        <>
          <input
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="Decision rationale (required, recorded in history)…"
            className="w-full rounded px-2 py-1.5 text-[10px] mb-2 outline-none"
            style={{ background: '#0d1525', border: '1px solid rgba(255,255,255,0.08)', color: '#c9d8f5' }}
          />
          <div className="flex flex-wrap gap-1.5">
            {DECISIONS.map(d => {
              const transitionOk = allowed.includes(d.to)
              const roleOk = canDecide(identity, caseItem, d.id)
              const enabled = transitionOk && roleOk && !busy
              const color = STATUS_META[d.to].color
              return (
                <button
                  key={d.id}
                  onClick={() => enabled && handle(d.id)}
                  disabled={!enabled}
                  title={transitionOk && !roleOk
                    ? `Requires ${DECISION_MIN_ROLE[d.id]?.replace('_', ' ')} role or case ownership`
                    : undefined}
                  className="font-mono text-[8px] font-bold tracking-wider px-2.5 py-1.5 rounded"
                  style={{
                    color: enabled ? color : '#2a3a5a',
                    border: `1px solid ${enabled ? color + '66' : '#1a2744'}`,
                    background: enabled ? color + '11' : 'transparent',
                    cursor: enabled ? 'pointer' : 'not-allowed',
                  }}
                >
                  {d.label}
                </button>
              )
            })}
          </div>
          {!isOwner && (
            <div className="text-[8px] tracking-wider mt-1.5" style={{ color: '#5a6a8a' }}>
              READ-ONLY — THIS CASE IS OWNED BY ANOTHER NODE. DECISIONS BELONG TO THE OWNING BANK.
            </div>
          )}
          {isOwner && roleBlocked.length > 0 && (
            <div className="text-[8px] tracking-wider mt-1.5" style={{ color: '#5a6a8a' }}>
              {roleBlocked.map(d =>
                `${d.label} requires ${(DECISION_MIN_ROLE[d.id] || 'a senior').replace('_', ' ').toUpperCase()}`
              ).join(' · ')}
              {identity ? ` — your role: ${identity.role.replace('_', ' ').toUpperCase()}` : ''}
            </div>
          )}
        </>
      )}
      {error && (
        <div className="flex items-start gap-1.5 mt-2">
          <AlertTriangle size={10} style={{ color: '#ff4d6b', marginTop: 1, flexShrink: 0 }} />
          <span className="text-[9px]" style={{ color: '#ff4d6b' }}>{error}</span>
        </div>
      )}
    </div>
  )
}

// ── Notes ──────────────────────────────────────────────────────────────────

function NotesPanel({ caseItem, onAddNote, identity }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState(null)
  const noteAllowed = canAddNote(identity, caseItem)

  const submit = async () => {
    setError(null)
    if (note.trim().length < 3) return
    const result = await onAddNote(caseItem, note.trim())
    if (!result.ok) setError(result.reasons.join(' · '))
    else setNote('')
  }

  return (
    <div className="rounded p-3" style={panelStyle}>
      <SectionLabel>CASE NOTES — ZERO-PII ENFORCED</SectionLabel>
      <div className="flex flex-col gap-1.5 mb-2 max-h-24 overflow-y-auto">
        {caseItem.analyst_notes.map((n, i) => (
          <div key={i} className="text-[9px] leading-relaxed" style={{ color: '#aab' }}>
            <span className="font-mono" style={{ color: '#5a6a8a' }}>
              {fmt(n.timestamp)} · {n.analyst_role} @ {n.node_id} —{' '}
            </span>
            {n.note}
          </div>
        ))}
        {caseItem.analyst_notes.length === 0 && (
          <span className="text-[9px]" style={{ color: '#3a4a6a' }}>No notes yet.</span>
        )}
      </div>
      {noteAllowed ? (
        <div className="flex gap-1.5">
          <input
            value={note}
            onChange={e => setNote(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="Add a note — names, IBANs, phones, or account ids will be rejected…"
            className="flex-1 rounded px-2 py-1.5 text-[10px] outline-none"
            style={{ background: '#0d1525', border: '1px solid rgba(255,255,255,0.08)', color: '#c9d8f5' }}
          />
          <button
            onClick={submit}
            className="font-mono text-[9px] font-bold tracking-wider px-3 rounded"
            style={{ color: '#4fc3f7', border: '1px solid #4fc3f766', background: '#4fc3f711', cursor: 'pointer' }}
          >
            ADD
          </button>
        </div>
      ) : (
        <div className="text-[8px] tracking-wider" style={{ color: '#5a6a8a' }}>
          NOTES ARE RESTRICTED TO THE OWNING NODE'S ANALYSTS.
        </div>
      )}
      {error && (
        <div className="flex items-start gap-1.5 mt-1.5">
          <AlertTriangle size={10} style={{ color: '#ff4d6b', marginTop: 1, flexShrink: 0 }} />
          <span className="text-[9px]" style={{ color: '#ff4d6b' }}>{error}</span>
        </div>
      )}
    </div>
  )
}

// ── History + audit refs ───────────────────────────────────────────────────

function HistoryPanel({ caseItem }) {
  return (
    <div className="rounded p-3" style={panelStyle}>
      <SectionLabel>DECISION HISTORY — APPEND-ONLY</SectionLabel>
      <div className="flex flex-col gap-1.5 max-h-28 overflow-y-auto">
        {caseItem.decision_history.map((h, i) => (
          <div key={i} className="text-[9px] leading-relaxed" style={{ color: '#aab' }}>
            <span className="font-mono" style={{ color: '#5a6a8a' }}>{fmt(h.timestamp)}</span>
            {' · '}
            <span className="font-mono font-bold" style={{ color: STATUS_META[h.new_status]?.color }}>
              {h.decision.replace(/_/g, ' ').toUpperCase()}
            </span>
            <span style={{ color: '#5a6a8a' }}>
              {' '}({h.previous_status} → {h.new_status}) · {h.analyst_role} @ {h.node_id}
            </span>
            <div style={{ color: '#7a8aa8' }}>“{h.reason}”</div>
          </div>
        ))}
        {caseItem.decision_history.length === 0 && (
          <span className="text-[9px]" style={{ color: '#3a4a6a' }}>
            No decisions yet — case awaits first analyst action.
          </span>
        )}
      </div>
      {caseItem.audit_refs.length > 0 && (
        <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="flex items-center gap-1.5 mb-1">
            <FileText size={9} style={{ color: '#5a6a8a' }} />
            <span className="text-[8px] tracking-widest" style={{ color: '#5a6a8a' }}>
              AUDIT TRAIL REFS (HASH-CHAINED LOG)
            </span>
          </div>
          <div className="flex flex-wrap gap-1">
            {caseItem.audit_refs.map((r, i) => (
              <span key={i} className="font-mono text-[8px] px-1.5 py-0.5 rounded"
                style={{ color: '#4a5a7a', background: '#0d1525', border: '1px solid #1a2744' }}>
                {r.slice(0, 12)}…
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Detail container ───────────────────────────────────────────────────────

export default function CaseDetail({ caseItem, onDecide, onAddNote, identity, usingMock }) {
  // Backend explanation for the selected case (live API only). Offline → null,
  // so WhyFlagged falls back to the static typology copy. Cleared on switch.
  const [explanation, setExplanation] = useState(null)
  useEffect(() => {
    setExplanation(null)
    if (usingMock || !caseItem?.case_id) return
    let active = true
    fetchCaseExplanation(caseItem.case_id).then(d => {
      if (active && d && d.pii_safe) setExplanation(d)
    })
    return () => { active = false }
  }, [caseItem?.case_id, usingMock])

  if (!caseItem) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-[10px] tracking-[3px]" style={{ color: '#3a4a6a' }}>
          SELECT A CASE FROM THE RISK QUEUE
        </span>
      </div>
    )
  }

  const status = STATUS_META[caseItem.status]
  const tierColor = TIER_COLORS[caseItem.risk_tier]

  return (
    <div className="flex-1 flex flex-col gap-2.5 overflow-y-auto pr-1">
      {/* Header */}
      <div className="rounded p-3 flex items-center justify-between" style={panelStyle}>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2.5">
            <span className="font-mono font-bold text-[14px] tracking-wider" style={{ color: tierColor }}>
              {caseItem.typology.replace(/_/g, ' ').toUpperCase()}
            </span>
            <span
              className="text-[9px] font-bold tracking-[1.5px] px-2 py-0.5 rounded"
              style={{ color: status.color, border: `1px solid ${status.color}66`, background: `${status.color}11` }}
            >
              {status.label}
            </span>
            {caseItem.false_positive_flag && (
              <span className="text-[8px] tracking-widest" style={{ color: '#8a9bbf' }}>FP-FLAGGED</span>
            )}
          </div>
          <div className="font-mono text-[9px]" style={{ color: '#5a6a8a' }}>
            CASE {caseItem.case_id.slice(0, 8)} · {caseItem.pattern_hash}
          </div>
        </div>
        <div className="flex flex-col items-end gap-0.5 text-[8px] tracking-wider" style={{ color: '#5a6a8a' }}>
          <span>SOURCE {caseItem.source_node_id}</span>
          <span>OPENED {fmt(caseItem.created_at)}</span>
          <span>{caseItem.assigned_to ? `ASSIGNED ${caseItem.assigned_to}` : 'UNASSIGNED'}</span>
        </div>
      </div>

      <WhyFlagged caseItem={caseItem} explanation={explanation} />
      <DecisionPanel caseItem={caseItem} onDecide={onDecide} identity={identity} usingMock={usingMock} />
      <NotesPanel caseItem={caseItem} onAddNote={onAddNote} identity={identity} />
      <HistoryPanel caseItem={caseItem} />
    </div>
  )
}
