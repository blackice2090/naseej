import { ListChecks, Check, Minus, ChevronRight } from 'lucide-react'
import Panel from './Panel'

const STATUS_COLOR = {
  Critical: '#ff4d6b',
  High: '#fbbf24',
  Medium: '#4fc3f7',
}

// Priority investigation queue. Clicking a row hands off to the existing
// Investigator flow (no duplicate case system is built here). Critical rows
// are marked with a left accent + badge, not a full bright-red background.
export default function PriorityCasesTable({ cases, onOpenCase }) {
  return (
    <Panel title="PRIORITY INVESTIGATION QUEUE" titleAr="قائمة الحالات ذات الأولوية" icon={ListChecks}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse" style={{ minWidth: 640 }}>
          <thead>
            <tr className="text-[9px] tracking-widest" style={{ color: '#5a6a8a' }}>
              <th className="text-left font-bold py-2 px-2">CASE ID</th>
              <th className="text-left font-bold py-2 px-2">BANK</th>
              <th className="text-left font-bold py-2 px-2">PATTERN</th>
              <th className="text-right font-bold py-2 px-2">RISK</th>
              <th className="text-center font-bold py-2 px-2">CROSS-BANK</th>
              <th className="text-left font-bold py-2 px-2">STATUS</th>
              <th className="text-left font-bold py-2 px-2">RECOMMENDED ACTION</th>
              <th className="py-2 px-2" aria-label="open" />
            </tr>
          </thead>
          <tbody>
            {cases.map(c => {
              const sc = STATUS_COLOR[c.status] || '#4fc3f7'
              return (
                <tr
                  key={c.id}
                  onClick={() => onOpenCase?.(c)}
                  tabIndex={0}
                  role="button"
                  aria-label={`Open case ${c.id} in Investigator`}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpenCase?.(c) } }}
                  className="text-[11px] cursor-pointer transition-colors"
                  style={{
                    borderTop: '1px solid rgba(255,255,255,0.05)',
                    borderLeft: `2px solid ${c.status === 'Critical' ? sc : 'transparent'}`,
                    background: c.status === 'Critical' ? 'rgba(255,77,107,0.05)' : 'transparent',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(79,195,247,0.06)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = c.status === 'Critical' ? 'rgba(255,77,107,0.05)' : 'transparent' }}
                >
                  <td className="py-2 px-2 font-mono font-bold" style={{ color: '#4fc3f7' }}>{c.id}</td>
                  <td className="py-2 px-2" style={{ color: '#a8b6d8' }}>{c.bank}</td>
                  <td className="py-2 px-2" style={{ color: '#c8d4f0' }}>{c.pattern}</td>
                  <td className="py-2 px-2 text-right font-mono font-bold" style={{ color: c.risk >= 0.9 ? '#ff4d6b' : c.risk >= 0.8 ? '#fbbf24' : '#a8b6d8' }}>
                    {c.risk.toFixed(2)}
                  </td>
                  <td className="py-2 px-2 text-center">
                    {c.crossBank
                      ? <span className="inline-flex items-center gap-1 font-mono text-[9px] font-bold" style={{ color: '#7c4dff' }}><Check size={11} aria-hidden="true" />Yes</span>
                      : <span className="inline-flex items-center gap-1 font-mono text-[9px]" style={{ color: '#5a6a8a' }}><Minus size={11} aria-hidden="true" />No</span>}
                  </td>
                  <td className="py-2 px-2">
                    <span className="font-mono text-[9px] font-bold tracking-wider px-1.5 py-0.5 rounded"
                      style={{ color: sc, border: `1px solid ${sc}55`, background: `${sc}12` }}>
                      {c.status}
                    </span>
                  </td>
                  <td className="py-2 px-2" style={{ color: '#a8b6d8' }}>{c.action}</td>
                  <td className="py-2 px-2 text-right"><ChevronRight size={13} style={{ color: '#4a5a7a' }} aria-hidden="true" /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[9px] tracking-widest mt-2 pt-2" style={{ color: '#5a6a8a', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        SELECT A CASE TO OPEN IT IN THE INVESTIGATOR WORKFLOW · HUMAN REVIEW REQUIRED · FLAGGED FOR REVIEW, NOT AUTO-BLOCKED
      </p>
    </Panel>
  )
}
