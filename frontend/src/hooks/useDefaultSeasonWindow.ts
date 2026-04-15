import { useEffect, useRef } from 'react'
import { getSeasons } from '../api'
import { useSetUrlParams } from './useUrlState'
import type { FilterParams } from '../types'

/**
 * Landing pages for /batting, /bowling, /fielding default to the
 * last N seasons in scope when the user arrives without a season
 * filter. This hook detects that state and one-shot auto-applies
 * the default by writing `season_from` and `season_to` into the
 * URL (so the FilterBar visibly reflects it).
 *
 * Per-mount behaviour:
 * - Fires once when seasons load, if no season filter is already set.
 * - If the user later clears the seasons ("All seasons" reset),
 *   does NOT re-apply on the same mount — the ref remembers.
 * - Navigating to a different discipline's landing is a fresh
 *   mount → fresh ref → default applies there independently.
 *
 * Filter-scope aware: the seasons list is fetched for the current
 * gender/team_type/tournament scope, so "last 3 seasons" adapts
 * (e.g. last 3 IPL seasons rather than last 3 across everything
 * when `tournament=Indian Premier League` is set).
 */
export function useDefaultSeasonWindow(
  filters: FilterParams,
  enabled: boolean,
  n: number = 3,
) {
  const setUrlParams = useSetUrlParams()
  const appliedRef = useRef(false)

  useEffect(() => {
    if (!enabled || appliedRef.current) return

    // If the user already has a season filter set on arrival (or via
    // URL carry from another page), claim the one-shot slot without
    // mutating anything. Prevents us from overwriting their intent.
    if (filters.season_from || filters.season_to) {
      appliedRef.current = true
      return
    }

    let cancelled = false
    getSeasons({
      gender: filters.gender,
      team_type: filters.team_type,
      tournament: filters.tournament,
    })
      .then(d => {
        if (cancelled || appliedRef.current) return
        if (!d.seasons || d.seasons.length === 0) return
        // API returns seasons in chronological order ascending.
        // Last N entries are the N most recent.
        const latest = d.seasons.slice(-n)
        const from = latest[0]
        const to = latest[latest.length - 1]
        if (!from || !to) return
        setUrlParams({ season_from: from, season_to: to })
        appliedRef.current = true
      })
      .catch(() => {
        // Graceful fallback — user just sees all-time by default.
      })

    return () => { cancelled = true }
  }, [enabled, filters.season_from, filters.season_to,
      filters.gender, filters.team_type, filters.tournament])
}
