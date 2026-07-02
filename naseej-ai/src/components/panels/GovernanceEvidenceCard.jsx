import { ShieldCheck, Lock, Users, FileCheck, EyeOff, FlaskConical, XCircle } from 'lucide-react'
import { GOVERNANCE_EVIDENCE } from '../../config/copy'

// Compact "Governance Evidence" strip. Reads condensed flags from
// /api/demo/governance-evidence (App passes `governance`, which defaults to the
// prototype's design properties so the strip renders even offline). Read-only;
// changes no scoring behaviour. Honesty: PDPL-by-design / SAMA-aligned only.
export default function GovernanceEvidenceCard({ governance }) {
  const g = governance || {}
  const isActive = (v) => v === 'active' || v === true

  const flags = [
    { icon: Lock, label: 'ZERO PII', value: isActive(g.zeroPii) ? 'ACTIVE' : '—', ok: isActive(g.zeroPii) },
    { icon: Users, label: 'HUMAN-IN-THE-LOOP', value: isActive(g.humanInLoop) ? 'ACTIVE' : '—', ok: isActive(g.humanInLoop) },
    { icon: FileCheck, label: 'AUDIT TRAIL', value: isActive(g.auditTrail) ? 'ACTIVE' : '—', ok: isActive(g.auditTrail) },
    { icon: ShieldCheck, label: 'RBAC', value: isActive(g.rbac) ? 'ACTIVE' : '—', ok: isActive(g.rbac) },
    { icon: EyeOff, label: 'SHADOW MODEL', value: 'NOT DEPLOYED', neutral: true },
    { icon: FlaskConical, label: 'CALIBRATION', value: (g.calibration || 'not production calibrated').toUpperCase(), neutral: true },
    { icon: XCircle, label: 'PRODUCTION READY', value: 'NO', warn: true },
  ]

  return (
    <div
      className="shrink-0 px-6 py-1.5 flex items-center gap-4"
      style={{
        background: 'rgba(7,12,10,0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-center gap-1.5 shrink-0" style={{ minWidth: 150 }}>
        <ShieldCheck size={10} style={{ color: '#00e676' }} />
        <span className="text-[9px] font-bold tracking-[2px]" style={{ color: '#00e676' }}>
          {GOVERNANCE_EVIDENCE.title}
        </span>
      </div>

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      <div className="flex items-center gap-3 flex-1 overflow-hidden">
        {flags.map((f) => {
          const Icon = f.icon
          const color = f.warn ? '#ff4d6b' : f.neutral ? '#8a9bbf' : f.ok ? '#00e676' : '#5a6a8a'
          return (
            <div key={f.label} className="flex items-center gap-1 shrink-0">
              <Icon size={9} style={{ color }} />
              <span className="text-[7px] tracking-widest" style={{ color: '#4a5a7a' }}>{f.label}</span>
              <span className="font-mono text-[8px] font-bold tracking-wider" style={{ color }}>
                {f.value}
              </span>
            </div>
          )
        })}
      </div>

      <div className="w-px shrink-0 self-stretch" style={{ background: 'rgba(255,255,255,0.06)' }} />

      <span className="text-[7px] tracking-wider shrink-0" style={{ color: '#fbbf24', fontStyle: 'italic', maxWidth: 250 }}>
        {GOVERNANCE_EVIDENCE.warning}
      </span>
    </div>
  )
}
