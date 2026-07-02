import { useState } from 'react'
import { motion, LayoutGroup } from 'framer-motion'
import { FALLBACK_METRICS } from '../../data/mockData'
import { ML_CARD } from '../../config/copy'
import CountUp from '../ui/CountUp'

// Operating modes are a triage-policy preview only — they do not change
// the model threshold in this prototype.
const OPERATING_MODES = ['CONSERVATIVE', 'BALANCED', 'AGGRESSIVE']

export default function MLValidationCard({ metrics }) {
  const [activeMode, setActiveMode] = useState('BALANCED')
  const m = metrics || FALLBACK_METRICS

  const metricRows = [
    { label: 'PR-AUC',    num: m.pr_auc,                fmt: v => v.toFixed(4) },
    { label: 'PRECISION', num: m.precision * 100,        fmt: v => v.toFixed(1) + '%' },
    { label: 'RECALL',    num: m.recall * 100,           fmt: v => v.toFixed(1) + '%' },
    { label: 'F1',        num: m.f1,                     fmt: v => v.toFixed(4) },
    { label: 'THRESHOLD', num: m.threshold,              fmt: v => v.toFixed(4) },
    { label: 'ALERTS',    num: m.n_alerts,               fmt: v => Math.round(v).toString() },
    { label: 'CONFIRMED', num: m.n_confirmed_laundering, fmt: v => Math.round(v).toString() },
  ]

  return (
    <div
      className="shrink-0 px-6 py-2 flex items-stretch gap-6"
      style={{
        background: 'rgba(10,13,24,0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        borderTop: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {/* Left: model identity */}
      <div className="flex flex-col justify-center gap-1 shrink-0" style={{ minWidth: 220 }}>
        <div className="flex items-center gap-2">
          <span
            className="text-[9px] font-bold tracking-[2px] px-1.5 py-0.5 rounded"
            style={{ background: '#7c4dff22', color: '#7c4dff', border: '1px solid #7c4dff44' }}
          >
            {ML_CARD.badge}
          </span>
          <span className="font-mono font-bold text-[12px] tracking-wider" style={{ color: '#e0e8ff' }}>
            {ML_CARD.model}
          </span>
        </div>
        <div className="text-[9px] leading-relaxed" style={{ color: '#4a5a7a', maxWidth: 220 }}>
          {ML_CARD.context}
        </div>
      </div>

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      {/* Centre: metrics strip with count-up animation */}
      <div className="flex items-center gap-1.5 flex-1 overflow-hidden">
        {metricRows.map((mr) => (
          <div
            key={mr.label}
            className="flex flex-col items-center justify-center px-3 rounded shrink-0"
            style={{
              background: 'rgba(13,21,37,0.7)',
              border: '1px solid rgba(255,255,255,0.06)',
              backdropFilter: 'blur(8px)',
              height: 44,
              minWidth: 66,
              opacity: mr.label === 'THRESHOLD' ? 0.65 : 1,
            }}
          >
            <span
              className="font-mono font-bold text-[13px] leading-none"
              style={{
                color: mr.label === 'CONFIRMED' ? '#00e676'
                     : mr.label === 'ALERTS'    ? '#4fc3f7'
                     : mr.label === 'THRESHOLD' ? '#6a7a9a'
                     : '#c9d8f5',
              }}
            >
              <CountUp to={mr.num} duration={1500} format={mr.fmt} />
            </span>
            <span className="text-[8px] tracking-widest mt-0.5" style={{ color: mr.label === 'THRESHOLD' ? '#3a4a6a' : '#4a5a7a' }}>
              {mr.label}
            </span>
          </div>
        ))}
      </div>

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      {/* Right: operating mode with Framer Motion layoutId glide */}
      <div className="flex flex-col justify-center gap-1 shrink-0">
        <div className="text-[8px] tracking-[2px]" style={{ color: '#4a5a7a' }}>OPERATING MODE</div>
        <LayoutGroup id="mode-group">
          <div className="flex gap-1">
            {OPERATING_MODES.map(mode => {
              const active = mode === activeMode
              return (
                <motion.button
                  key={mode}
                  onClick={() => setActiveMode(mode)}
                  className="relative font-mono text-[8px] tracking-wider px-2.5 py-1 rounded font-bold"
                  style={{
                    color: active ? '#000' : '#3a4a6a',
                    border: active ? 'none' : '1px solid #1a2744',
                    background: active ? 'transparent' : 'rgba(13,21,37,0.7)',
                    cursor: 'pointer',
                    zIndex: 0,
                  }}
                >
                  {active && (
                    <motion.div
                      layoutId="mode-pill"
                      className="absolute inset-0 rounded"
                      style={{ background: '#4fc3f7', zIndex: -1 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                    />
                  )}
                  <span style={{ position: 'relative', zIndex: 1 }}>{mode}</span>
                </motion.button>
              )
            })}
          </div>
        </LayoutGroup>
        <div className="text-[8px] leading-snug" style={{ color: '#3a4a6a', maxWidth: 180 }}>
          {ML_CARD.governance}
        </div>
      </div>
    </div>
  )
}
