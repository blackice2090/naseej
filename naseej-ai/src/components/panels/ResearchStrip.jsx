import { motion } from 'framer-motion'
import { BarChart2, Zap, Network, Lock, CheckCircle, Layers } from 'lucide-react'
import { STAGES } from '../../config/constants'
import { FALLBACK_CROSS_BANK, FALLBACK_CONTEXT_EXPLANATIONS } from '../../data/mockData'
import { CONTEXT_FEATURES } from '../../config/copy'
import { API_HOST_LABEL } from '../../lib/api'

// ── Cross-bank experiment summary ─────────────────────────────────────────

function CrossBankSection({ cb }) {
  const data = cb || FALLBACK_CROSS_BANK
  const max = Math.max(data.avg_recall_A_private, data.avg_recall_B_shared, data.avg_recall_C_naseej)
  const rows = [
    { label: 'PRIVATE', val: data.avg_recall_A_private, color: '#3a4a6a' },
    { label: 'SHARED',  val: data.avg_recall_B_shared,  color: '#4fc3f7' },
    { label: 'NASEEJ',  val: data.avg_recall_C_naseej,  color: '#7c4dff' },
  ]
  return (
    <div className="flex flex-col justify-center gap-1" style={{ minWidth: 210 }}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <BarChart2 size={10} style={{ color: '#7c4dff' }} />
        <span className="text-[9px] font-bold tracking-[2px]" style={{ color: '#7c4dff' }}>
          CROSS-BANK INTELLIGENCE
        </span>
      </div>
      {rows.map(r => (
        <div key={r.label} className="flex items-center gap-2">
          <span
            className="text-[9px] tracking-wider shrink-0 font-mono"
            style={{ color: r.label === 'NASEEJ' ? r.color : '#3a4a6a', width: 48, fontWeight: r.label === 'NASEEJ' ? 'bold' : 'normal' }}
          >
            {r.label}
          </span>
          <div className="flex-1 rounded-full overflow-hidden" style={{ height: 4, background: '#0d1525' }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(r.val / max) * 100}%` }}
              transition={{ duration: 1, ease: 'easeOut', delay: 0.1 }}
              style={{ height: '100%', background: r.color, borderRadius: 99 }}
            />
          </div>
          <span className="font-mono text-[10px] font-bold shrink-0" style={{ color: r.color, width: 36, textAlign: 'right' }}>
            {(r.val * 100).toFixed(1)}%
          </span>
        </div>
      ))}
      <div className="text-[9px] mt-0.5 font-mono" style={{ color: '#00e676' }}>
        ▲ +{(data.gain_recall_C_over_A * 100).toFixed(1)}pp recall vs private-only
      </div>
    </div>
  )
}

// ── Live single-transaction score (real XGBoost inference when API is up) ─

function LiveScoreSection({ score, stage }) {
  const active = stage >= STAGES.ATTACK && score != null
  const riskColor = score
    ? score.risk_score > 0.5 ? '#ff4d6b' : score.risk_score > 0.06 ? '#fbbf24' : '#4fc3f7'
    : '#4fc3f7'
  const predColor = score
    ? score.prediction === 'block' ? '#ff4d6b' : score.prediction === 'suspicious' ? '#fbbf24' : '#00e676'
    : '#5a6a8a'

  return (
    <div className="flex flex-col justify-center gap-1" style={{ minWidth: 200 }}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <Zap size={10} style={{ color: '#4fc3f7' }} />
        <span className="text-[9px] font-bold tracking-[2px]" style={{ color: '#4fc3f7' }}>
          SINGLE-TX SCORE
        </span>
      </div>
      {active ? (
        <>
          <div className="flex items-center gap-2">
            <span className="text-[9px] shrink-0" style={{ color: '#3a4a6a', width: 48 }}>RISK</span>
            <span className="font-mono font-bold text-[12px]" style={{ color: riskColor }}>
              {(score.risk_score * 100).toFixed(4)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] shrink-0" style={{ color: '#3a4a6a', width: 48 }}>VERDICT</span>
            <span className="font-mono font-bold text-[10px] tracking-wider" style={{ color: predColor }}>
              {score.prediction.toUpperCase()}
            </span>
          </div>
          <div className="text-[8px] mt-0.5" style={{ color: '#3a4a6a', fontStyle: 'italic' }}>
            No velocity history in single-TX mode
          </div>
          {score.source === 'model' && (
            <div className="flex items-center gap-1">
              <CheckCircle size={8} style={{ color: '#00e676' }} />
              <span className="text-[8px]" style={{ color: '#00e676' }}>
                XGBoost inference · Zero PII
              </span>
            </div>
          )}
        </>
      ) : (
        <span className="text-[9px]" style={{ color: '#3a4a6a' }}>
          Awaiting simulation…
        </span>
      )}
    </div>
  )
}

// ── Pattern-library decision on the full attack sequence ──────────────────

function PatternSection({ pattern, stage }) {
  const active = stage >= STAGES.DETECTED && pattern != null
  const top = pattern?.detected_patterns?.[0]
  const actionColor = pattern?.recommended_action === 'block' ? '#ff4d6b'
    : pattern?.recommended_action === 'review' ? '#fbbf24' : '#00e676'
  const tierColor = top?.risk_tier === 'critical' ? '#ff4d6b'
    : top?.risk_tier === 'high' ? '#fbbf24'
    : top?.risk_tier === 'medium' ? '#4fc3f7' : '#5a6a8a'

  return (
    <div
      className="flex flex-col justify-center gap-1"
      style={{
        minWidth: 220,
        padding: '4px 10px',
        borderRadius: 6,
        background: active ? 'rgba(124,77,255,0.05)' : 'transparent',
        border: active ? '1px solid rgba(124,77,255,0.15)' : '1px solid transparent',
      }}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <Network size={10} style={{ color: '#00e676' }} />
        <span className="text-[9px] font-bold tracking-[2px]" style={{ color: '#00e676' }}>
          PATTERN DECISION
        </span>
        {active && (
          <span className="text-[7px] tracking-widest ml-1" style={{ color: '#3a4a6a' }}>
            FULL SEQUENCE
          </span>
        )}
      </div>
      {active && top ? (
        <>
          <div className="flex items-center gap-2">
            <span className="text-[9px] shrink-0" style={{ color: '#3a4a6a', width: 48 }}>TYPE</span>
            <span className="font-mono font-bold text-[10px] tracking-wider" style={{ color: '#7c4dff' }}>
              {top.pattern_type?.replace(/_/g, ' ').toUpperCase() || '—'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] shrink-0" style={{ color: '#3a4a6a', width: 48 }}>RISK TIER</span>
            <span className="font-mono font-bold text-[10px]" style={{ color: tierColor }}>
              {top.risk_tier?.toUpperCase() || '—'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] shrink-0" style={{ color: '#3a4a6a', width: 48 }}>DECISION</span>
            <span className="font-mono font-bold text-[11px] tracking-wider" style={{ color: actionColor }}>
              {pattern.recommended_action?.toUpperCase() || '—'}
            </span>
          </div>
          {pattern.zero_pii && (
            <div className="flex items-center gap-1 mt-0.5">
              <Lock size={8} style={{ color: '#00e676' }} />
              <span className="text-[8px]" style={{ color: '#00e676' }}>Zero PII · PDPL-aligned</span>
            </div>
          )}
        </>
      ) : (
        <span className="text-[9px]" style={{ color: '#3a4a6a' }}>
          {stage >= STAGES.DETECTED ? 'Analyzing pattern…' : 'Awaiting detection…'}
        </span>
      )}
    </div>
  )
}

// ── Contextual velocity score (feature-store windows, rule layer) ─────────

function ContextSection({ contextScore, contextLive, stage }) {
  const detected = stage >= STAGES.DETECTED
  // Live explanations from /api/features/score-with-context, minus the
  // long honesty sentence (the strip shows the short label instead).
  const liveLines = contextScore?.explanation
    ?.filter(e => !e.startsWith('Adjustment is'))
    ?.slice(0, 4)
  const simulated = detected && !contextScore && !contextLive
  const lines = liveLines?.length ? liveLines
    : simulated ? FALLBACK_CONTEXT_EXPLANATIONS : null

  return (
    <div className="flex flex-col justify-center gap-0.5" style={{ minWidth: 230, maxWidth: 280 }}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <Layers size={10} style={{ color: '#fbbf24' }} />
        <span className="text-[9px] font-bold tracking-[2px]" style={{ color: '#fbbf24' }}>
          {CONTEXT_FEATURES.sectionTitle}
        </span>
        {simulated && (
          <span className="text-[7px] tracking-widest px-1 rounded"
            style={{ color: '#3a4a6a', border: '1px solid #1a2744' }}>
            {CONTEXT_FEATURES.simulatedTag}
          </span>
        )}
      </div>
      {detected && lines ? (
        <>
          {contextScore && (
            <div className="flex items-center gap-2">
              <span className="text-[9px] shrink-0" style={{ color: '#3a4a6a' }}>FINAL</span>
              <span className="font-mono font-bold text-[11px]" style={{ color: '#fbbf24' }}>
                {(contextScore.final_contextual_score * 100).toFixed(2)}%
              </span>
              <span className="text-[8px] font-mono" style={{ color: '#5a6a8a' }}>
                base {(contextScore.base_model_score * 100).toFixed(2)}%
                {' '}+ ctx {(contextScore.contextual_risk_adjustment * 100).toFixed(0)}pp
              </span>
            </div>
          )}
          {lines.map(line => (
            <div key={line} className="text-[8px] leading-snug" style={{ color: '#8a9bbf' }}>
              › {line}
            </div>
          ))}
          <div className="text-[7px] mt-0.5" style={{ color: '#3a4a6a', fontStyle: 'italic' }}>
            {CONTEXT_FEATURES.honesty}
          </div>
        </>
      ) : (
        <span className="text-[9px]" style={{ color: '#3a4a6a' }}>
          {detected ? 'Computing window features…' : 'Awaiting detection…'}
        </span>
      )}
    </div>
  )
}

// ── Strip container ────────────────────────────────────────────────────────

export default function ResearchStrip({
  cbData, scoreData, patternData, contextScore, contextLive, connected, stage,
}) {
  return (
    <div
      className="shrink-0 px-6 flex items-stretch gap-0 overflow-hidden"
      style={{
        background: 'rgba(7,9,15,0.92)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        minHeight: 70,
        paddingTop: 8,
        paddingBottom: 8,
      }}
    >
      <CrossBankSection cb={cbData} />

      <div className="w-px shrink-0 self-stretch mx-5" style={{ background: 'rgba(255,255,255,0.05)' }} />

      <LiveScoreSection score={scoreData} stage={stage} />

      <div className="w-px shrink-0 self-stretch mx-5" style={{ background: 'rgba(255,255,255,0.05)' }} />

      <PatternSection pattern={patternData} stage={stage} />

      <div className="w-px shrink-0 self-stretch mx-5" style={{ background: 'rgba(255,255,255,0.05)' }} />

      <ContextSection contextScore={contextScore} contextLive={contextLive} stage={stage} />

      <div className="flex-1" />

      {/* Backend connectivity indicators */}
      <div className="flex flex-col items-end justify-center gap-1 shrink-0">
        <div className="flex items-center gap-1.5">
          <div
            className={`w-1.5 h-1.5 rounded-full ${connected ? 'animate-pulse' : ''}`}
            style={{
              background: connected ? '#00e676' : '#3a4a6a',
              boxShadow: connected ? '0 0 4px #00e676' : 'none',
            }}
          />
          <span className="font-mono text-[9px] tracking-widest" style={{ color: connected ? '#00e676' : '#3a4a6a' }}>
            API {connected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
        <span className="font-mono text-[8px] tracking-widest" style={{ color: contextLive ? '#fbbf24' : '#3a4a6a' }}>
          {CONTEXT_FEATURES.label}: {contextLive ? CONTEXT_FEATURES.live : CONTEXT_FEATURES.offline}
        </span>
        <span className="text-[8px] tracking-wider" style={{ color: '#2a3a5a' }}>{API_HOST_LABEL}</span>
      </div>
    </div>
  )
}
