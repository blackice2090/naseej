import { BarChart3 } from 'lucide-react'
import Panel from './Panel'

const CAT_COLORS = {
  'Fan-in': '#4fc3f7',
  'Rapid Sweep': '#7c4dff',
  'Gather-Scatter': '#fbbf24',
  Cycle: '#00e676',
}

// Compact ranked horizontal bars with a one-line explanation per typology.
export default function TypologyRanking({ typologies }) {
  const max = Math.max(1, ...typologies.map(t => t.count))
  return (
    <Panel title="TOP DETECTED TYPOLOGIES" titleAr="أبرز الأنماط المكتشفة" icon={BarChart3} className="flex-1">
      <div className="flex flex-col gap-3">
        {typologies.map(t => (
          <div key={t.pattern}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-bold" style={{ color: '#c8d4f0' }}>{t.pattern}</span>
              <span className="font-mono text-[12px] font-bold" style={{ color: CAT_COLORS[t.pattern] }}>{t.count}</span>
            </div>
            <div className="rounded-full overflow-hidden" style={{ height: 6, background: 'rgba(255,255,255,0.05)' }}>
              <div className="h-full rounded-full" style={{ width: `${(t.count / max) * 100}%`, background: CAT_COLORS[t.pattern] }} />
            </div>
            <p className="text-[9.5px] leading-snug mt-1" style={{ color: '#7c8caf' }}>{t.explanation}</p>
          </div>
        ))}
      </div>
    </Panel>
  )
}
