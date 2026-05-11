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
 * Also tracks every AuxParam that changes the displayed data:
 *   - `filters.inning` (1st/2nd innings toggle)
 *   - `filters.toss_outcome` (Splits Mosaic toss filter)
 *   - `filters.result` (Splits Mosaic outcome filter)
 *
 * These are page-local AuxParams (not in FILTER_KEYS so they don't
 * ride into subscript link URLs), but every fetch they modify must
 * refetch when they flip — otherwise clicking a marginal in the
 * Splits Mosaic to flip toss_outcome leaves the StatCards and other
 * panels showing the pre-filter numbers (stale). Adding them here
 * keeps the "one source of truth for fetch deps" promise even though
 * FILTER_KEYS itself stays narrow. Spec:
 * internal_docs/spec-splits-mosaic.md §1.1.
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
    () => [
      ...FILTER_KEYS.map(k => filters[k as FilterKey]),
      filters.inning,
      filters.toss_outcome,
      filters.result,
    ],
    [filters],
  )
}
