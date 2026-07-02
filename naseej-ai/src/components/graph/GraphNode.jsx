import { motion } from 'framer-motion'
import { STAGES } from '../../config/constants'

// Account node in the mule-network map. The mule node gains radar ripple
// rings once graph analytics flags it (DETECTED onwards).
export default function GraphNode({ label, sublabel, color, isMule, stage }) {
  const isActive = isMule && stage >= STAGES.DETECTED
  const nodeColor = isActive ? '#ff4d6b' : color

  return (
    <div className="flex flex-col items-center">
      <div className="relative flex items-center justify-center" style={{ width: 44, height: 44 }}>
        {isActive && (
          <>
            {[0, 0.4, 0.8].map((delay, i) => (
              <motion.div
                key={i}
                className="absolute inset-0 rounded-full"
                style={{ border: `${i === 0 ? 2 : 1}px solid #ff4d6b` }}
                animate={{ scale: [1, 2.8 + i * 0.4], opacity: [0.8 - i * 0.2, 0] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut', delay }}
              />
            ))}
            <motion.div
              className="absolute inset-0 rounded-full"
              style={{ background: '#ff4d6b' }}
              animate={{ scale: [1, 1.5], opacity: [0.15, 0] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
            />
          </>
        )}

        <motion.div
          className="relative z-10 w-11 h-11 rounded-full flex items-center justify-center font-mono text-[10px] font-bold"
          animate={isActive ? {
            boxShadow: [
              '0 0 18px #ff4d6b99, 0 0 36px #ff4d6b44',
              '0 0 28px #ff4d6bcc, 0 0 56px #ff4d6b66',
              '0 0 18px #ff4d6b99, 0 0 36px #ff4d6b44',
            ],
          } : { boxShadow: `0 0 8px ${color}44` }}
          transition={{ duration: 1.4, repeat: isActive ? Infinity : 0 }}
          style={{
            background: '#0a0f1e',
            border: `2px solid ${nodeColor}`,
            color: nodeColor,
            transition: 'border-color 0.5s, color 0.5s',
          }}
        >
          {label}
        </motion.div>
      </div>
      <div className="text-[9px] tracking-widest mt-3" style={{ color: '#5a6a8a' }}>{sublabel}</div>
    </div>
  )
}
