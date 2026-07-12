import { AlertTriangle, GitMerge, Timer, ShieldCheck } from 'lucide-react'

// Four primary KPIs, all derived from the single dashboard model so they never
// disagree. Risk is never communicated by colour alone — each card carries an
// icon and a text label.
function KpiCard({ icon: Icon, value, label, note, accent }) {
  return (
    <div
      className="rounded-lg p-4 flex flex-col gap-1"
      style={{ background: 'rgba(10,15,30,0.6)', border: '1px solid rgba(255,255,255,0.06)' }}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] tracking-widest font-bold" style={{ color: '#8a9bbf' }}>{label}</span>
        <Icon size={15} style={{ color: accent }} aria-hidden="true" />
      </div>
      <div className="text-3xl font-bold font-mono leading-none mt-1" style={{ color: accent }}>{value}</div>
      <p className="text-[10px] leading-snug mt-1.5" style={{ color: '#7c8caf' }}>{note}</p>
    </div>
  )
}

export default function ExecutiveKpiGrid({ kpis }) {
  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
      <KpiCard
        icon={AlertTriangle} accent="#4fc3f7"
        value={kpis.suspiciousPatterns} label="SUSPICIOUS PATTERNS"
        note="Detected locally across participating nodes"
      />
      <KpiCard
        icon={GitMerge} accent="#7c4dff"
        value={kpis.crossBankMatches} label="CROSS-BANK MATCHES"
        note="Patterns matched at another bank"
      />
      <KpiCard
        icon={Timer} accent="#4fc3f7"
        value={`${kpis.medianDetection}s`} label="MEDIAN DETECTION TIME"
        note="From local detection to network match"
      />
      <KpiCard
        icon={ShieldCheck} accent="#00e676"
        value={`${kpis.zeroPii}%`} label="ZERO-PII SHARING"
        note="No customer identifiers crossed bank boundaries"
      />
    </div>
  )
}
