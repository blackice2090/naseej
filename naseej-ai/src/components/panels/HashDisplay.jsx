import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { Lock } from 'lucide-react'
import { STAGES, THREAT_HASH, SCRAMBLE_CHARS, TIMINGS } from '../../config/constants'
import { HASH_PANEL } from '../../config/copy'

// Matrix-decode reveal of the zero-PII pattern hash. When the backend is
// live, the real NSJ_* hash from /api/analyze-pattern replaces the demo
// placeholder.
export default function HashDisplay({ stage, liveHash }) {
  const hash = liveHash || THREAT_HASH
  const [displayed, setDisplayed] = useState('')
  const [showLabel, setShowLabel] = useState(false)
  const [isScrambling, setIsScrambling] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => {
    if (stage === STAGES.DETECTED) {
      setDisplayed('')
      setShowLabel(false)
      setIsScrambling(true)

      const TICK_MS = 30
      const MS_PER_CHAR = Math.floor(500 / hash.length)
      let elapsed = 0

      // Phase 1: pure scramble
      timerRef.current = setInterval(() => {
        elapsed += TICK_MS
        const scrambled = Array.from({ length: hash.length }, () =>
          SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)]
        ).join('')
        setDisplayed(scrambled)

        if (elapsed >= TIMINGS.HASH_SCRAMBLE_MS) {
          clearInterval(timerRef.current)
          setIsScrambling(false)

          // Phase 2: left-to-right reveal with trailing scramble
          let i = 0
          timerRef.current = setInterval(() => {
            i += 1
            const revealed = hash.slice(0, i)
            const trail = Array.from({ length: hash.length - i }, () =>
              SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)]
            ).join('')
            setDisplayed(revealed + trail)
            if (i >= hash.length) {
              clearInterval(timerRef.current)
              setDisplayed(hash)
              setShowLabel(true)
            }
          }, MS_PER_CHAR)
        }
      }, TICK_MS)

    } else if (stage > STAGES.DETECTED) {
      // Stage advanced early (e.g. fast-forward): snap the full hash in.
      clearInterval(timerRef.current)
      setIsScrambling(false)
      setDisplayed(hash)
      setShowLabel(true)
    }
    return () => clearInterval(timerRef.current)
  }, [stage, hash])

  if (stage < STAGES.DETECTED) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded p-3"
      style={{
        background: 'rgba(10,15,30,0.7)',
        border: '1px solid #7c4dff44',
        backdropFilter: 'blur(8px)',
      }}
    >
      <div className="text-[9px] tracking-widest mb-1.5" style={{ color: '#5a6a8a' }}>
        {HASH_PANEL.label}
      </div>
      <div
        className="font-mono text-[13px] font-bold tracking-wider"
        style={{
          color: isScrambling ? '#7c4dff66' : '#7c4dff',
          transition: 'color 0.3s',
          letterSpacing: '0.12em',
        }}
      >
        {displayed || <span className="animate-pulse">█</span>}
        {displayed.length > 0 && displayed.length < hash.length && !isScrambling && (
          <span className="animate-pulse" style={{ color: '#7c4dff' }}>█</span>
        )}
      </div>
      {showLabel && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="flex items-center gap-1.5 mt-2"
        >
          <Lock size={10} style={{ color: '#00e676' }} />
          <span className="text-[9px] tracking-widest" style={{ color: '#00e676' }}>
            {HASH_PANEL.verified}
          </span>
        </motion.div>
      )}
    </motion.div>
  )
}
