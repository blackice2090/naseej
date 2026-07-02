import { FlaskConical, Award, AlertTriangle, CheckCircle, XCircle, SlidersHorizontal } from 'lucide-react'
import { MODEL_EVIDENCE } from '../../config/copy'
import { FALLBACK_MODEL_EVIDENCE } from '../../data/mockData'

// Small, read-only "Evaluation Evidence" strip beneath the ML baseline card.
// Reads the offline ML evaluation reports via /api/model/* (condensed in
// useBackendData → evidence); falls back to the synthetic-benchmark snapshot
// when the backend is offline. Never claims production readiness.
export default function ModelEvidenceCard({ evidence }) {
  const e = evidence || FALLBACK_MODEL_EVIDENCE
  const fmtModel = (m) => (m ? m.replace(/_/g, ' ').toUpperCase() : '—')
  const fmtTypology = (t) => (t ? t.replace(/_/g, ' ') : '—')

  const stats = [
    {
      icon: Award,
      label: 'BEST BY PR-AUC',
      value: fmtModel(e.bestModel),
      sub: e.prAuc != null ? `PR-AUC ${e.prAuc.toFixed(4)}` : null,
      color: '#00e676',
    },
    {
      icon: SlidersHorizontal,
      label: 'F1 · THRESHOLD',
      value: e.f1 != null ? e.f1.toFixed(4) : '—',
      sub: e.thresholdMode ? `${e.thresholdMode} mode` : null,
      color: '#4fc3f7',
    },
    {
      icon: AlertTriangle,
      label: 'WEAKEST TYPOLOGY',
      value: fmtTypology(e.weakestTypology),
      sub: 'lowest recall (heuristic)',
      color: '#fbbf24',
    },
  ]

  return (
    <div
      className="shrink-0 px-6 py-2 flex items-center gap-5"
      style={{
        background: 'rgba(8,11,20,0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      {/* Identity */}
      <div className="flex flex-col justify-center gap-0.5 shrink-0" style={{ minWidth: 210 }}>
        <div className="flex items-center gap-1.5">
          <FlaskConical size={11} style={{ color: '#7c4dff' }} />
          <span className="text-[9px] font-bold tracking-[2px]" style={{ color: '#7c4dff' }}>
            {MODEL_EVIDENCE.title}
          </span>
        </div>
        <div className="text-[8px] leading-snug" style={{ color: '#4a5a7a', maxWidth: 210 }}>
          {MODEL_EVIDENCE.subtitle}
        </div>
      </div>

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      {/* Evidence stats */}
      <div className="flex items-center gap-2 flex-1 overflow-hidden">
        {stats.map((s) => {
          const Icon = s.icon
          return (
            <div
              key={s.label}
              className="flex flex-col justify-center px-3 rounded shrink-0"
              style={{
                background: 'rgba(13,21,37,0.7)',
                border: '1px solid rgba(255,255,255,0.06)',
                height: 42,
                minWidth: 150,
              }}
            >
              <div className="flex items-center gap-1">
                <Icon size={9} style={{ color: s.color }} />
                <span className="text-[7px] tracking-widest" style={{ color: '#4a5a7a' }}>{s.label}</span>
              </div>
              <span className="font-mono font-bold text-[11px] leading-tight" style={{ color: s.color }}>
                {s.value}
              </span>
              {s.sub && (
                <span className="text-[7px] font-mono" style={{ color: '#5a6a8a' }}>{s.sub}</span>
              )}
            </div>
          )
        })}
      </div>

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      {/* LightGBM status + honesty note */}
      <div className="flex flex-col justify-center gap-1 shrink-0" style={{ maxWidth: 220 }}>
        <div className="flex items-center gap-1">
          {e.lightgbmEvaluated ? (
            <CheckCircle size={9} style={{ color: '#00e676' }} />
          ) : (
            <XCircle size={9} style={{ color: '#6a7a9a' }} />
          )}
          <span
            className="text-[8px] tracking-wider font-mono"
            style={{ color: e.lightgbmEvaluated ? '#00e676' : '#6a7a9a' }}
          >
            {e.lightgbmEvaluated ? MODEL_EVIDENCE.lightgbmYes : MODEL_EVIDENCE.lightgbmNo}
          </span>
        </div>
        <div className="text-[7px] leading-snug" style={{ color: '#3a4a6a', fontStyle: 'italic' }}>
          {MODEL_EVIDENCE.honesty}
        </div>
      </div>
    </div>
  )
}
