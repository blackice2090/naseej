import { Wifi, WifiOff } from 'lucide-react'

// Truthful data-source badge. `connected` reflects whether the backend
// responded to the shared enrichment calls.
//  - Backend reachable → prominent green "API LIVE".
//  - Backend unavailable → prominent amber "SYNTHETIC MODE", with a smaller
//    secondary "API OFFLINE" technical status. Never a false live state.
export default function DashboardStatusBadge({ connected }) {
  if (connected) {
    return (
      <span
        className="inline-flex items-center gap-1.5 font-mono text-[9px] font-bold tracking-widest px-2 py-1 rounded"
        style={{ color: '#00e676', border: '1px solid #00e67644', background: '#00e6760d' }}
        title="Backend reachable · governance endpoints responded"
        aria-label="Data source: API LIVE"
      >
        <Wifi size={11} aria-hidden="true" />
        API LIVE
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className="inline-flex items-center gap-1.5 font-mono text-[9px] font-bold tracking-widest px-2 py-1 rounded"
        style={{ color: '#fbbf24', border: '1px solid #fbbf2444', background: '#fbbf240d' }}
        aria-label="Data source: SYNTHETIC MODE"
      >
        <WifiOff size={11} aria-hidden="true" />
        SYNTHETIC MODE
      </span>
      <span
        className="font-mono text-[8px] tracking-widest"
        style={{ color: '#5a6a8a' }}
        title="Backend not reachable — deterministic fallback data in use"
      >
        API OFFLINE
      </span>
    </span>
  )
}
