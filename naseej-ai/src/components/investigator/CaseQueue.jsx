import { motion } from 'framer-motion'
import { STATUS_META, TIER_COLORS } from '../../config/investigator'

function age(iso) {
  const mins = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000))
  if (mins < 60) return `${mins}m`
  if (mins < 1440) return `${Math.floor(mins / 60)}h`
  return `${Math.floor(mins / 1440)}d`
}

function QueueCard({ caseItem, selected, onSelect }) {
  const tierColor = TIER_COLORS[caseItem.risk_tier] || '#5a6a8a'
  const status = STATUS_META[caseItem.status] || { label: caseItem.status, color: '#5a6a8a' }
  const closed = caseItem.status.startsWith('closed')

  return (
    <motion.button
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={() => onSelect(caseItem.case_id)}
      className="w-full text-left rounded p-3 flex flex-col gap-1.5"
      style={{
        background: selected ? 'rgba(79,195,247,0.08)' : 'rgba(10,15,30,0.65)',
        border: selected ? '1px solid #4fc3f766' : '1px solid rgba(255,255,255,0.06)',
        opacity: closed ? 0.55 : 1,
        cursor: 'pointer',
      }}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono font-bold text-[11px] tracking-wider" style={{ color: tierColor }}>
          {caseItem.typology.replace(/_/g, ' ').toUpperCase()}
        </span>
        <span className="text-[9px] tracking-widest" style={{ color: '#5a6a8a' }}>
          {age(caseItem.created_at)}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="text-[8px] font-bold tracking-[1.5px] px-1.5 py-0.5 rounded"
            style={{ color: status.color, border: `1px solid ${status.color}55`, background: `${status.color}11` }}
          >
            {status.label}
          </span>
          <span className="text-[8px] tracking-widest" style={{ color: tierColor }}>
            {caseItem.risk_tier.toUpperCase()}
          </span>
        </div>
        <span className="font-mono font-bold text-[12px]" style={{ color: tierColor }}>
          {(caseItem.risk_score * 100).toFixed(0)}%
        </span>
      </div>
      <div className="font-mono text-[8px] truncate" style={{ color: '#3a4a6a' }}>
        {caseItem.pattern_hash}
      </div>
    </motion.button>
  )
}

export default function CaseQueue({ cases, selectedId, onSelect }) {
  // Open work first, highest risk first; closed cases sink to the bottom.
  const sorted = [...cases].sort((a, b) => {
    const aClosed = a.status.startsWith('closed') ? 1 : 0
    const bClosed = b.status.startsWith('closed') ? 1 : 0
    if (aClosed !== bClosed) return aClosed - bClosed
    return b.risk_score - a.risk_score
  })

  return (
    <div className="flex flex-col gap-2 overflow-y-auto pr-1" style={{ minWidth: 270, maxWidth: 270 }}>
      {sorted.map(c => (
        <QueueCard key={c.case_id} caseItem={c} selected={c.case_id === selectedId} onSelect={onSelect} />
      ))}
      {sorted.length === 0 && (
        <div className="text-[10px] tracking-widest p-4 text-center" style={{ color: '#3a4a6a' }}>
          NO CASES — RUN THE DEMO SIMULATION
        </div>
      )}
    </div>
  )
}
