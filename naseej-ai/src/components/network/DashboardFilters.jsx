import { TIME_RANGES, BANK_FILTERS, PATTERN_FILTERS } from '../../data/networkIntel'

// One row of filter groups. Selecting any option flows through useNetworkIntel
// → buildDashboard, so every section updates together from the same source.
function FilterGroup({ label, value, options, onChange }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] tracking-widest hidden xl:inline" style={{ color: '#7c8caf' }}>{label}</span>
      <div className="flex items-center gap-1 flex-wrap" role="group" aria-label={label}>
        {options.map(opt => {
          const active = opt.value === value
          return (
            <button
              key={opt.value}
              onClick={() => onChange(opt.value)}
              aria-pressed={active}
              className="font-mono text-[9px] font-bold tracking-wider px-2 py-1 rounded"
              style={{
                color: active ? '#000' : '#7a8aad',
                background: active ? '#4fc3f7' : 'rgba(13,21,37,0.7)',
                border: active ? 'none' : '1px solid #1a2744',
                cursor: 'pointer',
              }}
            >
              {opt.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default function DashboardFilters({ filters, setFilter }) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
      <FilterGroup
        label="TIME"
        value={filters.timeRange}
        options={TIME_RANGES.map(r => ({ value: r.id, label: r.label }))}
        onChange={v => setFilter('timeRange', v)}
      />
      <FilterGroup
        label="BANK"
        value={filters.bank}
        options={BANK_FILTERS.map(b => ({ value: b, label: b === 'All Banks' ? 'All' : b.replace('Bank ', '') }))}
        onChange={v => setFilter('bank', v)}
      />
      <FilterGroup
        label="PATTERN"
        value={filters.pattern}
        options={PATTERN_FILTERS.map(p => ({ value: p, label: p === 'All Patterns' ? 'All' : p }))}
        onChange={v => setFilter('pattern', v)}
      />
    </div>
  )
}
