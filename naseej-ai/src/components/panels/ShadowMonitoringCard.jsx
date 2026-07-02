import { Activity } from 'lucide-react'
import { SHADOW_MONITORING } from '../../config/copy'

// Thin read-only "Shadow Monitoring" row. Renders ONLY when the backend
// returns node-scoped aggregate observations (App passes `monitoring`);
// otherwise the parent renders nothing — safe empty state, demo intact.
// Aggregate + bucketed only; never raw transactions/identifiers/values.
const DRIFT_COLOR = { normal: '#00e676', watch: '#fbbf24', unavailable: '#5a6a8a' }

export default function ShadowMonitoringCard({ monitoring }) {
  if (!monitoring) return null
  const pct = (v) => (v != null ? `${(v * 100).toFixed(0)}%` : '—')
  const drift = monitoring.driftSignal || 'unavailable'

  const stats = [
    { label: 'AGREEMENT', value: pct(monitoring.agreementRate), color: '#4fc3f7' },
    { label: 'CAND ALERT', value: pct(monitoring.candidateAlertRate), color: '#b388ff' },
    { label: 'MISSING FEAT', value: pct(monitoring.missingFeatureRate), color: '#8a9bbf' },
  ]

  return (
    <div
      className="shrink-0 px-6 py-1.5 flex items-center gap-4"
      style={{
        background: 'rgba(8,10,18,0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-center gap-1.5 shrink-0" style={{ minWidth: 150 }}>
        <Activity size={10} style={{ color: '#4fc3f7' }} />
        <span className="text-[9px] font-bold tracking-[2px]" style={{ color: '#4fc3f7' }}>
          {SHADOW_MONITORING.title}
        </span>
      </div>

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      <div className="flex items-center gap-4 flex-1 overflow-hidden">
        {stats.map((s) => (
          <div key={s.label} className="flex items-center gap-1.5 shrink-0">
            <span className="text-[7px] tracking-widest" style={{ color: '#4a5a7a' }}>{s.label}</span>
            <span className="font-mono font-bold text-[10px]" style={{ color: s.color }}>{s.value}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-[7px] tracking-widest" style={{ color: '#4a5a7a' }}>DRIFT</span>
          <span
            className="font-mono text-[8px] font-bold tracking-wider px-1.5 py-0.5 rounded"
            style={{ color: DRIFT_COLOR[drift] || '#5a6a8a', border: `1px solid ${(DRIFT_COLOR[drift] || '#5a6a8a')}44` }}
          >
            {drift.toUpperCase()}
          </span>
        </div>

        {/* Calibration dataset (labels from analyst case outcomes) */}
        {monitoring.calibrationStatus && monitoring.calibrationStatus !== 'unavailable' && (
          <>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-[7px] tracking-widest" style={{ color: '#4a5a7a' }}>LABELS</span>
              <span className="font-mono font-bold text-[10px]" style={{ color: '#00e676' }}>
                {monitoring.labeledCount ?? 0}
              </span>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-[7px] tracking-widest" style={{ color: '#4a5a7a' }}>CALIBRATION</span>
              <span
                className="font-mono text-[8px] font-bold tracking-wider px-1.5 py-0.5 rounded"
                style={{
                  color: monitoring.thresholdMet ? '#fbbf24' : '#8a9bbf',
                  border: `1px solid ${monitoring.thresholdMet ? '#fbbf2444' : '#8a9bbf33'}`,
                }}
              >
                {monitoring.calibrationStatus.replace(/_/g, ' ').toUpperCase()}
              </span>
            </div>
          </>
        )}
      </div>

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      <div className="flex flex-col items-end shrink-0" style={{ maxWidth: 240 }}>
        <span className="text-[7px] tracking-wider" style={{ color: '#fbbf24', fontStyle: 'italic' }}>
          {SHADOW_MONITORING.label}
        </span>
        <span className="text-[7px] tracking-wider" style={{ color: '#3a4a6a', fontStyle: 'italic' }}>
          CALIBRATION DATASET — NOT PRODUCTION CALIBRATION
        </span>
      </div>
    </div>
  )
}
