import { useState, useEffect } from 'react'
import { Users } from 'lucide-react'
import CaseQueue from './CaseQueue'
import CaseDetail from './CaseDetail'
import { STATUS_META } from '../../config/investigator'

// Analyst workspace: risk queue on the left, case detail on the right.
// Receives case state from useCases (owned by App so the demo can ingest
// detections regardless of which view is showing).
export default function InvestigatorView({ cases, usingMock, onDecide, onAddNote, identity, focusCaseId }) {
  const [selectedId, setSelectedId] = useState(null)
  const selected = cases.find(c => c.case_id === selectedId) || null

  // Auto-select the newest case when none is selected yet.
  useEffect(() => {
    if (!selectedId && cases.length > 0) setSelectedId(cases[0].case_id)
  }, [cases, selectedId])

  // Hand-off from the Network Intelligence priority queue: select the exact
  // case that was clicked. `focusCaseId` carries a nonce so re-clicking the
  // same case re-focuses it.
  useEffect(() => {
    if (focusCaseId?.id) setSelectedId(focusCaseId.id)
  }, [focusCaseId])

  const counts = cases.reduce((acc, c) => {
    acc[c.status] = (acc[c.status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Workspace header */}
      <div
        className="shrink-0 px-6 py-2.5 flex items-center justify-between"
        style={{ background: 'rgba(7,9,15,0.92)', borderBottom: '1px solid rgba(255,255,255,0.04)' }}
      >
        <div className="flex items-center gap-3">
          <Users size={13} style={{ color: '#4fc3f7' }} />
          <span className="text-[11px] font-bold tracking-[2px]" style={{ color: '#4fc3f7' }}>
            INVESTIGATOR — RISK QUEUE
          </span>
          <div className="flex items-center gap-2 ml-2">
            {Object.entries(counts).map(([s, n]) => (
              <span key={s} className="text-[8px] tracking-wider font-mono"
                style={{ color: STATUS_META[s]?.color || '#5a6a8a' }}>
                {STATUS_META[s]?.label || s} {n}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {identity && (
            // Backend-resolved identity (node + role). UI mirroring only —
            // the backend enforces permissions regardless of this badge.
            <span
              className="font-mono text-[9px] font-bold tracking-widest px-2 py-0.5 rounded"
              style={{ color: '#4fc3f7', border: '1px solid #4fc3f744', background: '#4fc3f70d' }}
            >
              {identity.display_name.toUpperCase()} · {identity.role.replace('_', ' ').toUpperCase()}
            </span>
          )}
          <div className="flex items-center gap-2">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: usingMock ? '#fbbf24' : '#00e676' }}
            />
            <span className="font-mono text-[9px] tracking-widest"
              style={{ color: usingMock ? '#fbbf24' : '#00e676' }}>
              {usingMock ? 'MOCK DATA — BACKEND OFFLINE' : 'LIVE CASE API'}
            </span>
          </div>
        </div>
      </div>

      {/* Two-pane workspace */}
      <div className="flex-1 flex gap-3 p-4 overflow-hidden" style={{ background: 'rgba(8,12,24,0.4)' }}>
        <CaseQueue cases={cases} selectedId={selectedId} onSelect={setSelectedId} />
        <CaseDetail caseItem={selected} onDecide={onDecide} onAddNote={onAddNote}
          identity={identity} usingMock={usingMock} />
      </div>

      {/* Governance footer */}
      <div
        className="shrink-0 px-6 py-2 text-[9px] tracking-widest text-center"
        style={{ background: 'rgba(13,21,37,0.92)', borderTop: '1px solid rgba(255,255,255,0.06)', color: '#5a6a8a' }}
      >
        HUMAN-IN-THE-LOOP · RECOMMENDATIONS ONLY · EVERY DECISION ATTRIBUTED &amp; AUDIT-CHAINED · ZERO PII IN CASES
      </div>
    </div>
  )
}
