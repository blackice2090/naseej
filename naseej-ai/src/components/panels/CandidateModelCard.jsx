import { FlaskConical, Lock, GitCompare } from 'lucide-react'
import { CANDIDATE_MODEL } from '../../config/copy'

// Tiny read-only "Candidate Model" evidence row. Renders ONLY when the backend
// exposes a live candidate report (App passes `candidate`); otherwise the
// parent renders nothing — the demo never invents a candidate. The candidate
// is a shadow evaluation: it never replaces the deployed model.
//
// `shadow` (optional) is a live /api/model/candidate/score-shadow result from
// the demo run — candidate vs baseline, comparison-only. Hidden when absent.
export default function CandidateModelCard({ candidate, shadow }) {
  if (!candidate) return null
  const fmtModel = (m) => (m ? m.replace(/_/g, ' ').toUpperCase() : '—')
  const fmtPct = (v) => (v != null ? `${(v * 100).toFixed(3)}%` : '—')
  const showShadow = shadow && shadow.candidate_available && shadow.candidate_score != null

  const stats = [
    { label: 'CANDIDATE', value: fmtModel(candidate.selectedModel), color: '#b388ff' },
    { label: 'PR-AUC', value: candidate.prAuc != null ? candidate.prAuc.toFixed(4) : '—', color: '#00e676' },
    { label: 'F1', value: candidate.f1 != null ? candidate.f1.toFixed(4) : '—', color: '#4fc3f7' },
    { label: 'FEATURES', value: candidate.featureCount != null ? `${candidate.featureCount} approved` : '—', color: '#8a9bbf' },
  ]

  return (
    <div
      className="shrink-0 px-6 py-1.5 flex items-center gap-4"
      style={{
        background: 'rgba(10,8,20,0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-center gap-1.5 shrink-0" style={{ minWidth: 150 }}>
        <FlaskConical size={10} style={{ color: '#b388ff' }} />
        <span className="text-[9px] font-bold tracking-[2px]" style={{ color: '#b388ff' }}>
          {CANDIDATE_MODEL.title}
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
      </div>

      {/* Live shadow comparison (candidate vs baseline) — only when present */}
      {showShadow && (
        <>
          <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />
          <div className="flex items-center gap-3 shrink-0">
            <GitCompare size={10} style={{ color: '#fbbf24' }} />
            <div className="flex items-center gap-1.5">
              <span className="text-[7px] tracking-widest" style={{ color: '#4a5a7a' }}>CAND</span>
              <span className="font-mono font-bold text-[10px]" style={{ color: '#b388ff' }}>
                {fmtPct(shadow.candidate_score)}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[7px] tracking-widest" style={{ color: '#4a5a7a' }}>BASE</span>
              <span className="font-mono font-bold text-[10px]" style={{ color: '#4fc3f7' }}>
                {fmtPct(shadow.baseline_score)}
              </span>
            </div>
            <span
              className="font-mono text-[8px] font-bold tracking-wider px-1.5 py-0.5 rounded"
              style={{
                color: shadow.agreement_with_baseline === 'agree' ? '#00e676' : '#fbbf24',
                border: `1px solid ${shadow.agreement_with_baseline === 'agree' ? '#00e67644' : '#fbbf2444'}`,
              }}
            >
              {shadow.agreement_with_baseline === 'agree' ? 'AGREE' : 'DISAGREE'}
            </span>
            <span className="text-[7px] tracking-wider" style={{ color: '#fbbf24', fontStyle: 'italic' }}>
              SHADOW ONLY — DOES NOT DRIVE DECISIONS
            </span>
          </div>
        </>
      )}

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      {/* Shadow-only status — the load-bearing honesty label */}
      <div className="flex flex-col items-end justify-center gap-0.5 shrink-0" style={{ maxWidth: 230 }}>
        <div className="flex items-center gap-1">
          <Lock size={8} style={{ color: '#fbbf24' }} />
          <span className="text-[8px] font-bold tracking-wider font-mono" style={{ color: '#fbbf24' }}>
            {CANDIDATE_MODEL.status}
          </span>
        </div>
        <span className="text-[7px] leading-snug" style={{ color: '#3a4a6a', fontStyle: 'italic' }}>
          {CANDIDATE_MODEL.featureNote}
        </span>
      </div>
    </div>
  )
}
