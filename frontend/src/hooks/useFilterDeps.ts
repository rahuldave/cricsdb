import { useMemo } from 'react'
import { useFilters } from './useFilters'
import { FILTER_KEYS, type FilterKey } from '../components/scopeLinks'

/**
 * useFilterDeps — returns a stable array of FilterParams values in a
 * fixed order, suitable as a `useFetch` deps argument.
 *
 * Pages that want to refetch whenever any filter changes should use
 * this instead of hand-rolling `[filters.gender, filters.team_type, ...]`.
 * Iterates the single `FILTER_KEYS` registry so adding a new filter
 * auto-wires every page's deps (was the documented "filterDeps
 * landmine" — see internal_docs/design-decisions.md).
 *
 * Callers can append additional non-filter deps (e.g. active tab, a
 * row id) with `[...useFilterDeps(), tab]`.
 */
export function useFilterDeps(): (string | undefined)[] {
  const filters = useFilters()
  // `filters` is already memoized on URL string (see useFilters), so
  // reference identity changes only when values change. One more memo
  // here for the mapped array's stability.
  return useMemo(
    () => FILTER_KEYS.map(k => filters[k as FilterKey]),
    [filters],
  )
}
