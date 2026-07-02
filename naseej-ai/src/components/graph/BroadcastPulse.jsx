import { motion } from 'framer-motion'

// Particle flow rendered across the split screen while the zero-PII hash
// propagates from Bank A to Bank B.

const PARTICLE_CONFIGS = [
  { delay: 0,    top: '44%', size: 10 },
  { delay: 0.22, top: '50%', size: 7  },
  { delay: 0.44, top: '40%', size: 8  },
  { delay: 0.66, top: '55%', size: 6  },
]

function DataParticle({ delay, top, size }) {
  return (
    <motion.div
      className="absolute rounded-full pointer-events-none"
      style={{
        top,
        width: size,
        height: size,
        background: '#7c4dff',
        boxShadow: `0 0 ${size * 2}px #7c4dff, 0 0 ${size * 4}px #7c4dff66`,
        left: '25%',
        zIndex: 20,
      }}
      animate={{
        left: ['25%', '74%'],
        opacity: [0, 1, 1, 0.6, 0],
        scale: [0.4, 1.3, 1.1, 0.8, 0.4],
      }}
      transition={{
        duration: 1.1,
        delay,
        ease: [0.25, 0.46, 0.45, 0.94],
        repeat: Infinity,
        repeatDelay: 0.3,
      }}
    />
  )
}

export default function BroadcastPulse({ active }) {
  if (!active) return null
  return (
    <>
      <div
        className="absolute pointer-events-none"
        style={{
          top: '50%',
          left: '25%',
          right: '26%',
          height: 1,
          background: 'linear-gradient(90deg, transparent, #7c4dff55, #7c4dff99, #7c4dff55, transparent)',
          transform: 'translateY(-50%)',
          zIndex: 10,
        }}
      />
      {PARTICLE_CONFIGS.map((cfg, i) => (
        <DataParticle key={i} {...cfg} />
      ))}
    </>
  )
}
