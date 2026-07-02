import { Activity } from 'lucide-react'
import { STAGES } from '../../config/constants'
import { BANK_A } from '../../config/copy'
import { FALLBACK_METRICS } from '../../data/mockData'
import StatCard from '../ui/StatCard'
import TxRow from '../ui/TxRow'
import SectionLabel from '../ui/SectionLabel'
import GraphView from '../graph/GraphView'
import AlertBanner from './AlertBanner'
import HashDisplay from './HashDisplay'

// Bank A: the detecting node. Sees raw local transactions, runs graph
// analytics, and produces the zero-PII pattern hash.
export default function BankAPanel({ stage, txList, metrics, liveHash }) {
  const m = metrics || FALLBACK_METRICS

  return (
    <div
      className="flex flex-col gap-3 p-4 overflow-hidden relative"
      style={{
        borderRight: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(8,14,28,0.5)',
        backdropFilter: 'blur(16px)',
      }}
    >
      {/* Ambient glow — deep blue/cyan */}
      <div
        className="absolute pointer-events-none"
        style={{
          top: '-40%',
          left: '-30%',
          width: '90%',
          height: '90%',
          background: 'radial-gradient(ellipse, rgba(79,195,247,0.08) 0%, transparent 68%)',
          zIndex: 0,
        }}
      />

      <div className="relative z-10 flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Activity size={14} style={{ color: '#4fc3f7' }} />
            <span className="text-[13px] font-bold tracking-[2px]" style={{ color: '#4fc3f7' }}>
              {BANK_A.title}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full animate-pulse"
              style={{ background: '#00e676', boxShadow: '0 0 6px #00e676' }} />
            <span className="text-[10px] tracking-widest" style={{ color: '#00e676' }}>
              {BANK_A.monitoring}
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 shrink-0">
          <StatCard value={txList.length} label="TX TODAY" accent="#4fc3f7" />
          <StatCard
            value={stage >= STAGES.DETECTED ? '1' : '0'}
            label="THREATS"
            accent={stage >= STAGES.DETECTED ? '#ff4d6b' : '#00e676'}
          />
          <StatCard value={m.pr_auc.toFixed(4)} label="PR-AUC" accent="#7c4dff" />
        </div>

        {/* Alert banner */}
        <div className="shrink-0">
          <AlertBanner stage={stage} />
        </div>

        {/* TX feed */}
        <div className="shrink-0">
          <SectionLabel>{BANK_A.feedLabel}</SectionLabel>
          <div
            className="rounded p-2 overflow-y-auto flex flex-col gap-[2px]"
            style={{
              background: 'rgba(10,15,30,0.65)',
              border: '1px solid rgba(255,255,255,0.05)',
              height: 108,
            }}
          >
            {[...txList].reverse().map((tx, i) => (
              <TxRow key={tx.id || i} tx={tx} />
            ))}
          </div>
        </div>

        {/* Graph */}
        <div className="shrink-0">
          <SectionLabel>{BANK_A.graphLabel}</SectionLabel>
          <div
            className="rounded"
            style={{
              background: 'rgba(10,15,30,0.65)',
              border: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            <GraphView stage={stage} />
          </div>
        </div>

        {/* Hash display */}
        <div className="shrink-0">
          <HashDisplay stage={stage} liveHash={liveHash} />
        </div>
      </div>
    </div>
  )
}
