/**
 * PlayerResultFilter — player-page wrapper around the shared
 * ResultFilter pill row (Teams' standalone won/lost/tied widget).
 *
 * Standalone from the Splits Mosaic, mirroring the Teams widget. The
 * subject "team" is the player's OWN side per match (matchplayer.team),
 * so "Won" = matches the player's team won, across every team they've
 * turned out for. Writes the `result` aux param (sibling to the
 * `inning` toggle); the player /summary endpoints scope to it via
 * filters.player_result_clause.
 *
 * Counts come from /players/{id}/result-counts (aux-stripped) so the
 * pills stay stable as the user clicks them.
 *
 * Mounted on the main player page only for now — full roll-out to the
 * discipline pages is a later session.
 */

import { useFetch } from '../../hooks/useFetch'
import { useFilterDeps } from '../../hooks/useFilterDeps'
import { getPlayerResultCounts } from '../../api'
import ResultFilter from '../ResultFilter'
import type { FilterParams } from '../../types'

interface Props {
  playerId: string
  filters: FilterParams
}

export default function PlayerResultFilter({ playerId, filters }: Props) {
  const filterDeps = [playerId, ...useFilterDeps()]
  const fetchState = useFetch<{
    matches: number; wins: number; losses: number; ties: number; no_results: number
  } | null>(
    () => getPlayerResultCounts(playerId, filters),
    filterDeps,
  )
  const c = fetchState.data
  if (!c || c.matches === 0) return null
  return (
    <ResultFilter
      matches={c.matches}
      wins={c.wins}
      losses={c.losses}
      ties={c.ties}
      noResults={c.no_results}
    />
  )
}
