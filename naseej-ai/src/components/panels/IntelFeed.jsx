import { motion, AnimatePresence } from 'framer-motion'
import { INTEL_FEED } from '../../config/copy'

// Bank B's view of the Naseej network, line by line per stage.
export default function IntelFeed({ stage }) {
  const lines = INTEL_FEED[stage] || []
  return (
    <div
      className="rounded p-2 font-mono text-[10px] flex flex-col gap-1 overflow-y-auto"
      style={{
        background: 'rgba(10,15,30,0.6)',
        border: '1px solid rgba(255,255,255,0.05)',
        backdropFilter: 'blur(8px)',
        height: 82,
      }}
    >
      <AnimatePresence mode="sync">
        {lines.map((line, i) => (
          <motion.div
            key={`${stage}-${i}`}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.07, duration: 0.25 }}
            className={line.pulse ? 'animate-pulse' : ''}
            style={{ color: line.color, fontWeight: line.bold ? 'bold' : 'normal' }}
          >
            {line.text}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
