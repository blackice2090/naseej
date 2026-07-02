import { motion } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import { STAGES } from '../../config/constants'
import { ALERT_BANNER } from '../../config/copy'

export default function AlertBanner({ stage }) {
  if (stage < STAGES.DETECTED) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="flex items-start gap-3 rounded p-3"
      style={{ background: '#ff4d6b0f', border: '1px solid #ff4d6b55' }}
    >
      <AlertTriangle
        size={15}
        className="animate-pulse shrink-0"
        style={{ color: '#ff4d6b', marginTop: 1 }}
      />
      <div>
        <div className="font-bold text-[11px] tracking-wider" style={{ color: '#ff4d6b' }}>
          ⚠ {ALERT_BANNER.title}
        </div>
        <div className="text-[9px] mt-0.5 tracking-wide" style={{ color: '#ff4d6b99' }}>
          {ALERT_BANNER.subtitle}
        </div>
      </div>
    </motion.div>
  )
}
