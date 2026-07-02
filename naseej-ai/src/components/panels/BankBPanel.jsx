import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Network, Radio, CheckCircle } from 'lucide-react'
import { STAGES } from '../../config/constants'
import { BANK_B } from '../../config/copy'
import StatCard from '../ui/StatCard'
import TxRow from '../ui/TxRow'
import SectionLabel from '../ui/SectionLabel'
import BlockedStamp from '../ui/BlockedStamp'
import IntelFeed from './IntelFeed'

// Bank B: the receiving node. Never sees Bank A's customers — only the
// zero-PII pattern hash, which it matches against its own transactions.
export default function BankBPanel({ stage, txList, blockedTx }) {
  const displayTxs = blockedTx
    ? [blockedTx, ...[...txList].reverse()]
    : [...txList].reverse()

  const [shake, setShake] = useState(false)
  const [showStamp, setShowStamp] = useState(false)

  useEffect(() => {
    if (stage === STAGES.BLOCKED) {
      setShake(true)
      setShowStamp(true)
      const t1 = setTimeout(() => setShake(false), 500)
      const t2 = setTimeout(() => setShowStamp(false), 2600)
      return () => { clearTimeout(t1); clearTimeout(t2) }
    }
  }, [stage])

  const statusColor = stage >= STAGES.BLOCKED ? '#ff4d6b'
    : stage >= STAGES.BROADCASTING ? '#7c4dff' : '#00e676'
  const statusText = stage >= STAGES.BLOCKED ? BANK_B.statusByStage.blocked
    : stage >= STAGES.BROADCASTING ? BANK_B.statusByStage.ingesting
    : BANK_B.statusByStage.idle

  return (
    <motion.div
      animate={shake ? { x: [0, -9, 8, -6, 5, -3, 2, 0] } : { x: 0 }}
      transition={{ duration: 0.42, ease: 'easeInOut' }}
      className="flex flex-col gap-3 p-4 overflow-hidden relative"
      style={{
        background: 'rgba(12,8,28,0.5)',
        backdropFilter: 'blur(16px)',
      }}
    >
      {/* Ambient glow — deep violet/purple */}
      <div
        className="absolute pointer-events-none"
        style={{
          top: '-40%',
          right: '-30%',
          width: '90%',
          height: '90%',
          background: 'radial-gradient(ellipse, rgba(124,77,255,0.10) 0%, transparent 68%)',
          zIndex: 0,
        }}
      />

      <BlockedStamp show={showStamp} />

      <div className="relative z-10 flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Network size={14} style={{ color: '#7c4dff' }} />
            <span className="text-[13px] font-bold tracking-[2px]" style={{ color: '#7c4dff' }}>
              {BANK_B.title}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ background: statusColor, boxShadow: `0 0 6px ${statusColor}` }}
            />
            <span className="text-[10px] tracking-widest" style={{ color: statusColor }}>
              {statusText}
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 shrink-0">
          <StatCard value={txList.length} label="TX TODAY" accent="#7c4dff" />
          <StatCard
            value={stage >= STAGES.BLOCKED ? '1' : '0'}
            label="FLAGGED"
            accent={stage >= STAGES.BLOCKED ? '#ff4d6b' : '#00e676'}
          />
          <StatCard value="0" label="PII RECORDS SHARED" accent="#00e676" />
        </div>

        {/* Threat intelligence feed */}
        <div className="shrink-0">
          <SectionLabel>{BANK_B.logLabel}</SectionLabel>
          <IntelFeed stage={stage} />
        </div>

        {/* TX feed */}
        <div className="shrink-0">
          <SectionLabel>{BANK_B.feedLabel}</SectionLabel>
          <div
            className="rounded p-2 overflow-y-auto flex flex-col gap-[2px]"
            style={{
              background: 'rgba(10,15,30,0.65)',
              border: '1px solid rgba(255,255,255,0.05)',
              height: 108,
            }}
          >
            {displayTxs.map((tx, i) => (
              <TxRow key={tx.id || i} tx={tx} />
            ))}
          </div>
        </div>

        {/* Status footer */}
        <div className="shrink-0">
          <AnimatePresence mode="sync">
            {stage >= STAGES.BLOCKED ? (
              <motion.div
                key="blocked-footer"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
                className="flex items-start gap-3 rounded p-3"
                style={{ background: '#00e67610', border: '1px solid #00e67644' }}
              >
                <CheckCircle size={15} style={{ color: '#00e676', flexShrink: 0, marginTop: 1 }} />
                <div>
                  <div className="font-bold text-[12px] tracking-wider" style={{ color: '#00e676' }}>
                    {BANK_B.blockedTitle}
                  </div>
                  <div className="text-[10px] mt-0.5 tracking-wide" style={{ color: '#00e676aa' }}>
                    {BANK_B.blockedSubtitle}
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="listening"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center gap-2 rounded p-3"
                style={{ background: 'rgba(10,15,30,0.6)', border: '1px solid #7c4dff33' }}
              >
                <Radio size={13} style={{ color: '#7c4dff' }} />
                <span className="text-[10px] tracking-widest" style={{ color: '#7c4dff' }}>
                  {BANK_B.listeningFooter}
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  )
}
