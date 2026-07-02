import { motion, AnimatePresence } from 'framer-motion'

// Spring-slam FLAGGED stamp shown over Bank B when the match fires.
export default function BlockedStamp({ show }) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ scale: 3, opacity: 0, rotate: -12 }}
          animate={{ scale: 1, opacity: 1, rotate: -7 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ type: 'spring', stiffness: 700, damping: 18 }}
          className="absolute inset-0 flex items-center justify-center z-30 pointer-events-none"
        >
          <div
            className="font-mono font-black text-4xl tracking-[8px] border-4 rounded px-6 py-2"
            style={{
              color: '#ff4d6b',
              borderColor: '#ff4d6b',
              boxShadow: '0 0 40px #ff4d6b88, 0 0 80px #ff4d6b44, inset 0 0 30px #ff4d6b11',
              textShadow: '0 0 20px #ff4d6b, 0 0 40px #ff4d6b66',
              background: 'rgba(7,9,15,0.88)',
            }}
          >
            FLAGGED
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
