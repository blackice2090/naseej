import { Network } from 'lucide-react'
import Panel from './Panel'
import { NETWORK_INTEL } from '../../config/copy'
import { BANKS } from '../../data/networkIntel'

// Fixed node positions on a 100x100 viewBox — four fictional bank nodes.
const POS = {
  'Bank A': { x: 22, y: 24 },
  'Bank B': { x: 78, y: 24 },
  'Bank C': { x: 22, y: 78 },
  'Bank D': { x: 78, y: 78 },
}

const VIOLET = '#7c4dff'
const RED = '#ff4d6b'

// Stable, hand-tuned label slot per directed connection. Each slot is a unique
// (x,y) badge centre near its own edge, spaced so no two badges — nor a badge
// and a node or arrowhead — overlap. Opposite directions on the same line get
// separate slots; diagonals stack in the centre column. Avoids dynamic
// collision detection while guaranteeing a clean layout for all 12 pairs.
const LABEL_SLOTS = {
  'Bank A->Bank B': { x: 40, y: 13 }, 'Bank B->Bank A': { x: 62, y: 13 }, // top horizontal
  'Bank C->Bank D': { x: 40, y: 88 }, 'Bank D->Bank C': { x: 62, y: 88 }, // bottom horizontal
  'Bank A->Bank C': { x: 31, y: 44 }, 'Bank C->Bank A': { x: 31, y: 58 }, // left vertical (right of line)
  'Bank B->Bank D': { x: 69, y: 44 }, 'Bank D->Bank B': { x: 69, y: 58 }, // right vertical (left of line)
  'Bank A->Bank D': { x: 50, y: 37 }, 'Bank C->Bank B': { x: 50, y: 47 }, // diagonals, centre column
  'Bank B->Bank C': { x: 50, y: 57 }, 'Bank D->Bank A': { x: 50, y: 67 },
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`

// Cross-bank intelligence map — the main visual. Shows only privacy-safe
// pattern-hash flows and confirmed matches between nodes. No accounts, names,
// IBANs, national IDs, phone numbers, or raw transactions appear here.
// Map shared-hash volume to a controlled, non-scaling stroke width. Higher
// volume reads as a heavier connection, but the range is clamped to ~2–4px so
// no path ever covers labels, arrowheads, nodes, or other connections.
const strokeForHashes = (hashes = 1) => {
  const clamped = Math.max(1, Math.min(hashes, 8))
  return 2 + ((clamped - 1) / 7) * 2 // 1 hash → 2px, 8+ hashes → 4px
}

export default function CrossBankNetworkMap({ edges }) {
  // Nodes that carry at least one active edge under the current filters.
  const connected = new Set()
  edges.forEach(e => { connected.add(e.from); connected.add(e.to) })

  return (
    <Panel title="CROSS-BANK INTELLIGENCE MAP" titleAr="خريطة الاستخبارات بين البنوك" icon={Network} className="flex-1">
      <div className="flex flex-col lg:flex-row gap-4 flex-1">
        <div className="relative flex-1" style={{ minHeight: 196, maxHeight: '48vh' }}>
          <svg viewBox="0 0 100 100" className="w-full h-full" style={{ overflow: 'visible' }} role="img"
            aria-label="Privacy-safe intelligence flows between four bank nodes">
            <defs>
              <marker id="niArrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill={VIOLET} />
              </marker>
              <marker id="niArrowRed" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill={RED} />
              </marker>
            </defs>

            {/* Dashed connection lines + arrowheads (unchanged geometry). */}
            {edges.map((e, i) => {
              const a = POS[e.from]; const b = POS[e.to]
              if (!a || !b) return null
              const color = e.critical ? RED : VIOLET
              const dx = b.x - a.x, dy = b.y - a.y
              const len = Math.hypot(dx, dy)
              const ux = dx / len, uy = dy / len
              // Stop lines at the node pill edge (pill half-width ~12, half-height ~5).
              const x1 = a.x + ux * 12, y1 = a.y + uy * 6
              const x2 = b.x - ux * 12, y2 = b.y - uy * 6
              const slot = LABEL_SLOTS[`${e.from}->${e.to}`] || { x: (x1 + x2) / 2, y: (y1 + y2) / 2 }
              const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
              return (
                <g key={`line-${i}`}>
                  {/* Restrained glow behind the critical path (position never animated). */}
                  {e.critical && (
                    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={RED}
                      strokeWidth={strokeForHashes(e.hashes) + 3} vectorEffect="non-scaling-stroke"
                      strokeLinecap="round" opacity="0.18" className="ni-critical-path"
                      style={{ pointerEvents: 'none' }} />
                  )}
                  {/* Faint leader tying the badge to its edge midpoint. */}
                  <line x1={slot.x} y1={slot.y} x2={mx} y2={my} stroke={color} strokeWidth="0.3" opacity="0.28" />
                  <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color}
                    strokeWidth={strokeForHashes(e.hashes)} vectorEffect="non-scaling-stroke"
                    strokeDasharray="6 4" strokeLinecap="round" opacity={e.critical ? 1 : 0.85}
                    className={e.critical ? 'ni-critical-path' : undefined}
                    markerEnd={`url(#${e.critical ? 'niArrowRed' : 'niArrow'})`} />
                </g>
              )
            })}

            {/* Two-line label badges, drawn after all lines so they sit on top. */}
            {edges.map((e, i) => {
              if (!POS[e.from] || !POS[e.to]) return null
              const color = e.critical ? RED : VIOLET
              const slot = LABEL_SLOTS[`${e.from}->${e.to}`] || { x: 50, y: 50 }
              const l1 = plural(e.hashes, 'Hash', 'Hashes')
              const l2 = plural(e.matches, 'Match', 'Matches')
              const w = Math.max(l1.length, l2.length) * 1.55 + 4.4
              const h = 9.4
              return (
                <g key={`label-${i}`}>
                  <rect x={slot.x - w / 2} y={slot.y - h / 2} width={w} height={h} rx="1.8"
                    fill="rgba(7,9,15,0.94)" stroke={`${color}88`} strokeWidth="0.35" />
                  <text x={slot.x} y={slot.y - 1.1} textAnchor="middle" fontSize="2.7" fill="#e6ecff"
                    fontWeight="bold" style={{ fontFamily: 'monospace' }}>{l1}</text>
                  <text x={slot.x} y={slot.y + 3.1} textAnchor="middle" fontSize="2.7"
                    fill={e.critical ? '#ffb3c1' : '#c3b6ff'} style={{ fontFamily: 'monospace' }}>{l2}</text>
                </g>
              )
            })}

            {/* Bank nodes — muted when they have no active edge under the filters. */}
            {BANKS.map(bank => {
              const p = POS[bank]
              const active = connected.has(bank)
              return (
                <g key={bank} opacity={active ? 1 : 0.4}>
                  <rect x={p.x - 12} y={p.y - 5} width="24" height="10" rx="2"
                    fill="rgba(13,21,37,0.96)" stroke="#4fc3f7" strokeWidth="0.6" />
                  <text x={p.x} y={p.y + 1.4} textAnchor="middle" fontSize="3.6" fill="#4fc3f7"
                    fontWeight="bold" style={{ fontFamily: 'monospace' }}>
                    {bank}
                  </text>
                  {!active && (
                    <text x={p.x} y={p.y + 8.4} textAnchor="middle" fontSize="2.3" fill="#7c8caf"
                      style={{ fontFamily: 'monospace' }}>No active matches</text>
                  )}
                </g>
              )
            })}
          </svg>
        </div>

        <div className="lg:w-52 flex flex-col gap-3 shrink-0">
          <div className="flex flex-col gap-1.5 text-[10px]">
            <LegendRow color="#4fc3f7" label="Bank node" symbol="ring" />
            <LegendRow color={VIOLET} label="Shared pattern hash / privacy-safe connection" />
            <LegendRow color={RED} label="Cross-bank match (critical)" />
            <div className="text-[9px] mt-0.5" style={{ color: '#7c8caf' }}>Each badge: pattern hashes shared · confirmed matches</div>
          </div>
          <p className="text-[10px] leading-relaxed pt-2" style={{ color: '#7a8aad', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            {NETWORK_INTEL.mapCaption}
          </p>
          <p className="text-[10px] leading-relaxed text-right" style={{ color: '#7c4dff', fontFamily: 'var(--font-arabic)' }} dir="rtl">
            {NETWORK_INTEL.mapCaptionAr}
          </p>
        </div>
      </div>
    </Panel>
  )
}

function LegendRow({ color, label, symbol }) {
  return (
    <div className="flex items-center gap-2">
      {symbol === 'ring'
        ? <span className="inline-block rounded-full shrink-0" style={{ width: 10, height: 10, border: `2px solid ${color}` }} />
        : <span className="inline-block rounded-full shrink-0" style={{ width: 10, height: 3, background: color }} />}
      <span style={{ color: '#a8b6d8' }}>{label}</span>
    </div>
  )
}
