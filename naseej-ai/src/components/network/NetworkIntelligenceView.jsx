import { FlaskConical } from 'lucide-react'
import { useNetworkIntel } from '../../hooks/useNetworkIntel'
import { NETWORK_INTEL } from '../../config/copy'
import DashboardFilters from './DashboardFilters'
import DashboardStatusBadge from './DashboardStatusBadge'
import ExecutiveKpiGrid from './ExecutiveKpiGrid'
import DecisionSummary from './DecisionSummary'
import CrossBankNetworkMap from './CrossBankNetworkMap'
import FraudPatternTrend from './FraudPatternTrend'
import TypologyRanking from './TypologyRanking'
import PriorityCasesTable from './PriorityCasesTable'
import PrivacyGovernanceStrip from './PrivacyGovernanceStrip'

// Network Intelligence page. Scrolls vertically inside the app shell (the demo
// page stays fixed) — page-specific overflow, no global body scroll changes.
export default function NetworkIntelligenceView({ connected, onOpenCase }) {
  const { filters, setFilter, dashboard } = useNetworkIntel()

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: 'rgba(8,12,24,0.4)' }}>
      <div className="max-w-[1600px] mx-auto px-6 py-5 flex flex-col gap-4">

        {/* Executive header */}
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-3">
              <h1 className="text-lg font-bold tracking-[3px]" style={{ color: '#4fc3f7' }}>{NETWORK_INTEL.titleEn}</h1>
              <span className="text-base leading-relaxed" style={{ color: '#7c4dff', fontFamily: 'var(--font-arabic)' }} dir="rtl">{NETWORK_INTEL.titleAr}</span>
            </div>
            <p className="text-[11px] mt-1 max-w-2xl leading-relaxed" style={{ color: '#a8b6d8' }}>{NETWORK_INTEL.subtitle}</p>
            <p className="text-[13px] mt-1 max-w-2xl leading-relaxed" style={{ color: '#c3b6ff', fontFamily: 'var(--font-arabic)' }} dir="rtl">{NETWORK_INTEL.subtitleAr}</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 font-mono text-[9px] font-bold tracking-widest px-2 py-1 rounded"
                style={{ color: '#fbbf24', border: '1px solid #fbbf2444', background: '#fbbf240d' }}>
                <FlaskConical size={11} aria-hidden="true" /> {NETWORK_INTEL.syntheticBadgeEn}
              </span>
              <DashboardStatusBadge connected={connected} />
            </div>
            <span className="text-[9px] tracking-widest" style={{ color: '#7c8caf' }}>
              RANGE: {dashboard.range.label.toUpperCase()}
            </span>
          </div>
        </header>

        {/* Story chips */}
        <div className="flex items-center gap-2 flex-wrap">
          {NETWORK_INTEL.storyChips.map((c, i) => (
            <span key={c} className="flex items-center gap-2">
              <span className="font-mono text-[9px] tracking-widest px-2 py-1 rounded"
                style={{ color: '#a8b6d8', background: 'rgba(13,21,37,0.7)', border: '1px solid #1a2744' }}>{c}</span>
              {i < NETWORK_INTEL.storyChips.length - 1 && <span style={{ color: '#6a7a9e' }}>→</span>}
            </span>
          ))}
        </div>

        {/* Filters */}
        <div className="rounded-lg px-4 py-3" style={{ background: 'rgba(10,15,30,0.5)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <DashboardFilters filters={filters} setFilter={setFilter} />
        </div>

        {/* KPI row */}
        <ExecutiveKpiGrid kpis={dashboard.kpis} />

        {/* Decision band — full width, above the map (no empty side area) */}
        <DecisionSummary riskStatus={dashboard.riskStatus} criticalCount={dashboard.criticalCount} topPattern={dashboard.topPattern} />

        {/* Cross-bank map (full width) */}
        <CrossBankNetworkMap edges={dashboard.edges} />

        {/* Trend + typologies */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 flex"><FraudPatternTrend trend={dashboard.trend} topPattern={dashboard.topPattern} range={dashboard.range} /></div>
          <div className="lg:col-span-1 flex"><TypologyRanking typologies={dashboard.typologies} /></div>
        </div>

        {/* Priority queue */}
        <PriorityCasesTable cases={dashboard.cases} onOpenCase={onOpenCase} />

        {/* Privacy & governance */}
        <PrivacyGovernanceStrip governance={dashboard.governance} />

        <p className="text-[9px] tracking-widest text-center pb-2" style={{ color: '#6a7a9e' }}>
          SYNTHETIC DEMO DATA · RESEARCH PROTOTYPE · NOT PRODUCTION VALIDATION · PDPL-BY-DESIGN · SAMA-ALIGNED PROTOTYPE
        </p>
      </div>
    </div>
  )
}
