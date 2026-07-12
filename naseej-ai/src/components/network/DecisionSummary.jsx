import { Brain, UserCheck } from 'lucide-react'
import { NETWORK_INTEL } from '../../config/copy'

const STATUS_COLOR = { ELEVATED: '#fbbf24', GUARDED: '#4fc3f7', STABLE: '#00e676' }

// Compact full-width decision band above the map. Communicates clearly: the AI
// recommends, a human analyst decides, and no automatic production blocking
// occurs. Laid out horizontally so it never leaves a large empty area.
export default function DecisionSummary({ riskStatus, criticalCount, topPattern }) {
  const color = STATUS_COLOR[riskStatus] || '#4fc3f7'
  return (
    <div
      className="rounded-lg p-4 flex flex-col lg:flex-row lg:items-stretch gap-4"
      style={{ background: 'rgba(10,15,30,0.6)', border: `1px solid ${color}55`, boxShadow: `inset 0 0 24px ${color}12` }}
    >
      {/* Status */}
      <div className="flex items-center gap-3 lg:pr-4 lg:border-r shrink-0" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <Brain size={18} style={{ color }} aria-hidden="true" />
        <div>
          <div className="text-[9px] tracking-widest" style={{ color: '#8a9bbf' }}>NETWORK RISK STATUS</div>
          <div className="font-mono text-lg font-bold tracking-widest leading-tight" style={{ color }}>{riskStatus}</div>
        </div>
      </div>

      {/* Reason */}
      <div className="flex-1 flex items-center">
        <p className="text-[12px] leading-relaxed" style={{ color: '#c8d4f0' }}>
          {criticalCount > 0
            ? `${criticalCount} critical case${criticalCount > 1 ? 's' : ''} in the current window. `
            : 'No critical cases in the current window. '}
          {topPattern?.count > 0
            ? `${topPattern.pattern} is the most active typology and drove the most cross-bank matches.`
            : 'Activity is within normal ranges for the selected filters.'}
        </p>
      </div>

      {/* Recommended action */}
      <div className="lg:w-[38%] shrink-0 rounded p-2.5 flex flex-col justify-center"
        style={{ background: 'rgba(124,77,255,0.06)', border: '1px solid rgba(124,77,255,0.2)' }}>
        <div className="flex items-center gap-2 mb-1">
          <UserCheck size={12} style={{ color: '#7c4dff' }} aria-hidden="true" />
          <span className="text-[9px] tracking-widest font-bold" style={{ color: '#7c4dff' }}>RECOMMENDED ACTION</span>
        </div>
        <p className="text-[11px] leading-relaxed" style={{ color: '#c0ccea' }}>
          Prioritize the critical cases for analyst review. <span style={{ color: '#e0e8ff' }}>AI recommends — a human analyst decides. No automatic production blocking.</span>
        </p>
        <p className="text-[12px] mt-1.5 leading-relaxed" style={{ color: '#b39dff', fontFamily: 'var(--font-arabic)' }} dir="rtl">
          {NETWORK_INTEL.decisionArabic}
        </p>
      </div>
    </div>
  )
}
