import { Lock } from 'lucide-react'
import Panel from './Panel'
import { NETWORK_INTEL } from '../../config/copy'

// Privacy & Governance strip. Prefers live backend governance flags when
// present, otherwise clearly-labelled deterministic synthetic evidence. No
// production/certified claims — these are design properties of the prototype.
export default function PrivacyGovernanceStrip({ governance }) {
  const items = [
    { label: 'Zero-PII Sharing', value: `${governance.zeroPii}%`, color: '#00e676' },
    { label: 'PII Payloads Blocked', value: governance.piiBlocked, color: '#00e676' },
    { label: 'Audited Actions', value: governance.auditedActions, color: '#4fc3f7' },
    { label: 'Human Review Coverage', value: `${governance.humanReview}%`, color: '#4fc3f7' },
    { label: 'Hash Integrity', value: governance.hashIntegrity, color: '#00e676' },
    { label: 'Sharing Scope', value: governance.sharingScope, color: '#7c4dff' },
  ]
  return (
    <Panel
      title="PRIVACY & GOVERNANCE" titleAr="الخصوصية والحوكمة" icon={Lock}
      right={
        <span className="flex items-center gap-2">
          <span className="font-mono text-[8px] font-bold tracking-widest px-1.5 py-0.5 rounded"
            style={{ color: '#fbbf24', border: '1px solid #fbbf2444', background: '#fbbf240d' }}>
            {NETWORK_INTEL.governanceEvidenceLabel}
          </span>
          <span className="text-[10px]" style={{ color: '#b39dff', fontFamily: 'var(--font-arabic)' }} dir="rtl">
            {NETWORK_INTEL.governanceEvidenceLabelAr}
          </span>
        </span>
      }
    >
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {items.map(it => (
          <div key={it.label} className="rounded p-2.5" style={{ background: 'rgba(13,21,37,0.5)', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div className="font-mono text-lg font-bold" style={{ color: it.color }}>{it.value}</div>
            <div className="text-[9px] tracking-wide mt-0.5" style={{ color: '#7a8aad' }}>{it.label}</div>
          </div>
        ))}
      </div>
      <p className="text-[10px] leading-relaxed mt-3" style={{ color: '#a8b6d8' }}>{NETWORK_INTEL.governanceStatement}</p>
      <p className="text-[10px] leading-relaxed mt-1" style={{ color: '#7c4dff', fontFamily: 'var(--font-arabic)' }} dir="rtl">
        {NETWORK_INTEL.governanceStatementAr}
      </p>
    </Panel>
  )
}
