import { motion } from 'framer-motion'

export default function TxRow({ tx }) {
  const isBlocked = tx.status === 'BLOCKED'
  const isFlagged = tx.status === 'FLAGGED'
  const dotColor = isBlocked ? '#ff4d6b' : isFlagged ? '#fbbf24' : '#00e676'

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25 }}
      className="flex items-center justify-between py-[3px] px-2 rounded text-[10px] font-mono shrink-0"
      style={{
        background: isBlocked ? '#ff4d6b0e' : 'transparent',
        borderLeft: isBlocked ? '2px solid #ff4d6b' : isFlagged ? '2px solid #fbbf24' : '2px solid transparent',
      }}
    >
      <span className="shrink-0 mr-1" style={{ color: '#4fc3f7' }}>{tx.id}</span>
      <span className="shrink-0 mx-1" style={{ color: '#2a3a55' }}>→</span>
      <span className="truncate flex-1" style={{ color: '#667' }}>{tx.to}</span>
      <span className="ml-3 shrink-0" style={{ color: '#aab' }}>{tx.amount?.toLocaleString()} SAR</span>
      <span className="ml-2 shrink-0 font-bold" style={{ color: dotColor }}>● {tx.status}</span>
    </motion.div>
  )
}
