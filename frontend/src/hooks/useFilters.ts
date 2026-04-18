import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FILTER_KEYS, type FilterKey } from '../components/scopeLinks'
import type { FilterParams } from '../types'

/**
 * useFilters — read every FilterBar-tracked URL param into a FilterParams
 * object. Iterates the single `FILTER_KEYS` registry so adding a new
 * filter is ONE edit (in scopeLinks.ts); consumers here don't change.
 *
 * Lives in hooks/ (not colocated with FilterBar.tsx) so both FilterBar
 * itself and link-building helpers can depend on it without circular
 * imports.
 */
export function useFilters(): FilterParams {
  const [params] = useSearchParams()
  // Memoize by the actual URL-params string so consumers get a stable
  // reference when nothing changed — lets `Object.values(filters)` be
  // used directly as a useFetch dep without provoking spurious refetches.
  const qs = params.toString()
  return useMemo(() => {
    const out: Partial<FilterParams> = {}
    for (const k of FILTER_KEYS) {
      const v = params.get(k as FilterKey)
      if (v) out[k as FilterKey] = v
    }
    return out as FilterParams
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qs])
}
