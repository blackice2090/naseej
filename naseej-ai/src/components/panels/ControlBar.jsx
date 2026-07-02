import { motion } from 'framer-motion'
import { Zap } from 'lucide-react'
import { STAGES } from '../../config/constants'
import { STAGE_LABELS, COMPLIANCE_FOOTER } from '../../config/copy'

export default function ControlBar({ stage, onRun, onReset }) {
  const isIdle = stage === STAGES.IDLE

  return (
    <div
      className="flex items-center justify-between px-6 py-3 shrink-0"
      style={{
        background: 'rgba(13,21,37,0.92)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(16px)',
      }}
    >
      <div className="text-[10px] tracking-widest" style={{ color: '#5a6a8a' }}>
        STAGE: {STAGE_LABELS[stage]}
      </div>

      {isIdle ? (
        <motion.button
          onClick={onRun}
          whileHover={{ scale: 1.05, boxShadow: '0 0 20px #4fc3f755' }}
          whileTap={{ scale: 0.96 }}
          className="flex items-center gap-2 font-bold text-[10px] tracking-[2px] px-5 py-2 rounded"
          style={{ background: '#4fc3f7', color: '#000' }}
        >
          <Zap size={12} />
          RUN SIMULATION
        </motion.button>
      ) : (
        <motion.button
          onClick={onReset}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.96 }}
          className="flex items-center gap-2 font-bold text-[10px] tracking-[2px] px-5 py-2 rounded"
          style={{ background: '#1a2744', color: '#4fc3f7', border: '1px solid #4fc3f744' }}
        >
          ↺ RESET DEMO
        </motion.button>
      )}

      <div className="text-[10px] tracking-widest" style={{ color: '#5a6a8a' }}>
        {COMPLIANCE_FOOTER}
      </div>
    </div>
  )
}
