// Network Intelligence dashboard state.
//
// Owns the filter selection and derives the whole (deterministic, synthetic)
// dashboard model from it via buildDashboard. The dashboard data itself is
// always synthetic and clearly labelled; `connected` (from the shared backend
// hook) only decides whether the status badge honestly reads API LIVE or
// DEMO FALLBACK — it never fabricates a fake success state.

import { useMemo, useState, useCallback } from 'react'
import { buildDashboard, DEFAULT_FILTERS } from '../data/networkIntel'

export function useNetworkIntel() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  const setFilter = useCallback((key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }, [])

  const dashboard = useMemo(() => buildDashboard(filters), [filters])

  return { filters, setFilter, dashboard }
}
