import { motion } from 'framer-motion'
import { STAGES } from '../../config/constants'
import GraphNode from './GraphNode'

// SOURCE → MULE → DESTINATION topology. Edges draw in during ATTACK and
// turn red once the pattern is DETECTED.
export default function GraphView({ stage }) {
  const isAlerted = stage >= STAGES.DETECTED
  const isDrawing = stage >= STAGES.ATTACK
  const lineColor = isAlerted ? '#ff4d6b77' : '#1a2744'

  return (
    <div className="relative flex items-center justify-between px-8 py-4" style={{ minHeight: 90 }}>
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ overflow: 'visible' }}>
        <defs>
          <marker id="arrowL" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill={lineColor} style={{ transition: 'fill 0.5s' }} />
          </marker>
          <marker id="arrowR" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill={lineColor} style={{ transition: 'fill 0.5s' }} />
          </marker>
        </defs>

        <motion.line
          x1="22%" y1="44%" x2="44%" y2="44%"
          stroke={lineColor}
          strokeWidth="1.5"
          strokeDasharray="5 3"
          markerEnd="url(#arrowL)"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: isDrawing ? 1 : 0, opacity: isDrawing ? 1 : 0 }}
          transition={{ duration: 0.7, ease: 'easeInOut' }}
          style={{ transition: 'stroke 0.5s' }}
        />

        <motion.line
          x1="57%" y1="44%" x2="79%" y2="44%"
          stroke={lineColor}
          strokeWidth="1.5"
          strokeDasharray="5 3"
          markerEnd="url(#arrowR)"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: isDrawing ? 1 : 0, opacity: isDrawing ? 1 : 0 }}
          transition={{ duration: 0.7, ease: 'easeInOut', delay: 0.4 }}
          style={{ transition: 'stroke 0.5s' }}
        />
      </svg>

      <GraphNode label="SRC"  sublabel="SOURCE"      color="#4fc3f7" isMule={false} stage={stage} />
      <GraphNode label="MULE" sublabel="MULE ACCT"   color="#7c4dff" isMule={true}  stage={stage} />
      <GraphNode
        label="INTL"
        sublabel="DESTINATION"
        color={isAlerted ? '#ff4d6b' : '#4fc3f7'}
        isMule={false}
        stage={stage}
      />
    </div>
  )
}
