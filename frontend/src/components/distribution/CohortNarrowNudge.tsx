/**
 * Inline "narrow cohort" nudge for the Distribution panel chip row.
 *
 * Renders ONLY when there's a real scope-vs-window mismatch — i.e.
 * the player is looking at a dist_window slice (last 10 / last 60d /
 * last 6mo / last 1y) AND the scope's season range covers ≥2 seasons
 * (so there's a meaningful narrowing the user could do).
 *
 * Suggestions:
 *   - All-time scope (no season range): suggest "latest season" +
 *     "last 2 seasons" within the player's career-in-scope.
 *   - Multi-season scope (≥2 seasons in range): suggest the most
 *     recent two individual seasons within the range as one-click
 *     narrows.
 *   - Single-season scope: returns null (comparison already tight).
 *
 * Clicking sets `season_from` / `season_to` URL params via
 * `useSetUrlParams`. Does NOT clear `dist_window` — the user opted
 * into it and "last 10 within 2023" is still a meaningful sub-slice.
 *
 * Spec: discussion in session 2026-05-21 → mismatch nudges for the
 * deferred per-window-cohort visualisation issue.
 */

import { useFetch } from '../../hooks/useFetch'
import { useFilters } from '../../hooks/useFilters'
import { useSetUrlParams } from '../../hooks/useUrlState'
import { getSeasons } from '../../api'
import type { DistWindow } from './WindowBadge'


interface Props {
  /** Active dist_window. Nudge hidden when window === 'scope'. */
  window: DistWindow
  /** Player ID — used to fetch the player's career-in-scope seasons
   *  so we only suggest seasons they actually played in. */
  playerId: string
}


export default function CohortNarrowNudge({ window, playerId }: Props) {
  const filters = useFilters()
  const setUrlParams = useSetUrlParams()

  // No mismatch — window IS scope, so the comparison is already
  // apples-to-apples by default. Nothing to nudge.
  if (window === 'scope') return null

  const { season_from, season_to } = filters

  // Single-season scope → already as tight as it gets. Hide.
  if (season_from && season_to && season_from === season_to) return null

  // Fetch the player's seasons in scope. Excludes scope axes that
  // can't be honored by /api/v1/seasons but keeps the rough scope
  // intent. Same shape as ScopeStatusStrip's derived-season fetch.
  const seasonsFetch = useFetch(
    () => getSeasons({
      player: playerId,
      gender: filters.gender,
      team_type: filters.team_type,
      tournament: filters.tournament,
      filter_team: filters.filter_team,
      filter_opponent: filters.filter_opponent,
      filter_venue: filters.filter_venue,
      team_class: filters.team_class,
      series_type: filters.series_type,
    }),
    [
      playerId, filters.gender, filters.team_type, filters.tournament,
      filters.filter_team, filters.filter_opponent, filters.filter_venue,
      filters.team_class, filters.series_type,
    ],
  )
  const allSeasons = seasonsFetch.data?.seasons ?? []
  if (allSeasons.length === 0) return null

  // Build suggestion list per the three cases.
  const suggestions: { label: string; onClick: () => void }[] = []

  if (!season_from && !season_to) {
    // Case A: all-time scope — suggest "latest season only" and
    // "last 2 seasons".
    const latest = allSeasons[allSeasons.length - 1]
    suggestions.push({
      label: `${latest} only`,
      onClick: () => setUrlParams({ season_from: latest, season_to: latest }),
    })
    if (allSeasons.length >= 2) {
      const prev = allSeasons[allSeasons.length - 2]
      suggestions.push({
        label: `${prev}–${latest}`,
        onClick: () => setUrlParams({ season_from: prev, season_to: latest }),
      })
    }
  } else {
    // Case B: multi-season scope — suggest the most recent two
    // individual seasons WITHIN the current range.
    const inScope = allSeasons.filter(s =>
      (!season_from || s >= season_from) && (!season_to || s <= season_to)
    )
    const top = inScope.slice(-2).reverse()  // most recent first
    for (const s of top) {
      // Don't suggest the current range's only season (avoids a no-op).
      if (season_from === s && season_to === s) continue
      suggestions.push({
        label: `${s} only`,
        onClick: () => setUrlParams({ season_from: s, season_to: s }),
      })
    }
  }

  if (suggestions.length === 0) return null

  return (
    <span style={{
      fontFamily: 'var(--serif)',
      fontStyle: 'italic',
      fontSize: '0.7rem',
      color: 'var(--ink-faint)',
      marginLeft: 'auto',  // push to the right end of the flex chip row
      alignSelf: 'flex-end',
      paddingBottom: '0',
      whiteSpace: 'nowrap',
    }}>
      narrow cohort:{' '}
      {suggestions.map((s, i) => (
        <span key={s.label}>
          {i > 0 && ' · '}
          <button
            type="button"
            onClick={s.onClick}
            style={{
              background: 'transparent',
              border: 0,
              padding: 0,
              font: 'inherit',
              color: 'var(--accent)',
              textDecoration: 'underline',
              cursor: 'pointer',
            }}
          >{s.label}</button>
        </span>
      ))}
    </span>
  )
}
