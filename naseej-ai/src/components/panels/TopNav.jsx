import { Shield, Activity, Users, Network } from 'lucide-react'
import { BRAND, NETWORK_STATUS, NETWORK_STATUS_INTEL } from '../../config/copy'

const VIEWS = [
  { id: 'demo', label: 'DEMO', icon: Activity },
  { id: 'network', label: 'NETWORK INTELLIGENCE', icon: Network },
  { id: 'investigator', label: 'INVESTIGATOR', icon: Users },
]

export default function TopNav({ view, onViewChange, openCaseCount = 0 }) {
  return (
    <div
      className="flex items-center justify-between px-6 py-3 shrink-0"
      style={{
        background: 'rgba(13,21,37,0.92)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(16px)',
      }}
    >
      <div className="flex items-center gap-3">
        <Shield size={16} style={{ color: '#4fc3f7' }} />
        <span className="font-bold tracking-[3px] text-sm" style={{ color: '#4fc3f7' }}>
          {BRAND.nameEn}
        </span>
        <span className="text-[12px] tracking-wide" style={{ color: '#7c4dff', fontFamily: 'serif' }}>
          {BRAND.nameAr}
        </span>
        <span className="hidden lg:inline text-[9px] tracking-widest" style={{ color: '#4a5a7a' }}>
          {BRAND.tagline}
        </span>
      </div>

      {/* View switch */}
      <div className="flex items-center gap-1">
        {VIEWS.map(v => {
          const active = v.id === view
          const Icon = v.icon
          return (
            <button
              key={v.id}
              onClick={() => onViewChange(v.id)}
              className="relative flex items-center gap-1.5 font-mono text-[9px] font-bold tracking-[1.5px] px-3 py-1.5 rounded"
              style={{
                color: active ? '#000' : '#5a6a8a',
                background: active ? '#4fc3f7' : 'rgba(13,21,37,0.7)',
                border: active ? 'none' : '1px solid #1a2744',
                cursor: 'pointer',
              }}
            >
              <Icon size={10} />
              {v.label}
              {v.id === 'investigator' && openCaseCount > 0 && (
                <span
                  className="font-mono text-[8px] font-bold px-1 rounded-full"
                  style={{
                    background: active ? '#000' : '#ff4d6b',
                    color: active ? '#4fc3f7' : '#fff',
                    minWidth: 14,
                    textAlign: 'center',
                  }}
                >
                  {openCaseCount}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-4">
        <span className="text-[9px] tracking-widest" style={{ color: '#3a4a6a' }}>
          {BRAND.status}
        </span>
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ background: '#00e676', boxShadow: '0 0 6px #00e676' }}
          />
          <span className="text-[9px] tracking-widest" style={{ color: '#00e676' }}>
            {view === 'network' ? NETWORK_STATUS_INTEL : NETWORK_STATUS}
          </span>
        </div>
      </div>
    </div>
  )
}
