import type { FilterParams, TeamProfile } from '../../types'

export type TeamDiscipline =
  | 'results' | 'batting' | 'bowling' | 'fielding' | 'partnerships'

/** Each discipline's "has meaningful data in scope" gate. Drives both
 *  per-column band visibility and the grid-wide anyHasData mask. */
export function teamDisciplineHasData(
  discipline: TeamDiscipline, profile: TeamProfile,
): boolean {
  if (discipline === 'results')      return (profile.summary?.matches ?? 0) > 0
  if (discipline === 'batting')      return (profile.batting?.innings_batted ?? 0) > 0
  if (discipline === 'bowling')      return (profile.bowling?.innings_bowled ?? 0) > 0
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return false
    return (f.catches + f.stumpings + f.run_outs) > 0
  }
  return (profile.partnerships?.total ?? 0) > 0
}

/** Filter-scoped match count for the column identity line. Uses
 *  summary.matches as the canonical match-level count (team_summary's
 *  COUNT(*) over the filtered match table). fielding.matches and
 *  bowling.matches are innings-derived and can diverge by a handful
 *  of abandoned / no-result matches where a team never fielded or
 *  bowled — correct for their own stats, misleading as a headline. */
export function teamMatchesInScope(profile: TeamProfile): number {
  return profile.summary?.matches
    ?? profile.bowling?.matches
    ?? 0
}

/** Query-string carry for a Teams-page deep link — all active FilterBar
 *  params. Mirrors `players/roleUtils.carryFilters`. */
export function carryTeamFilters(filters: FilterParams): Record<string, string> {
  const out: Record<string, string> = {}
  if (filters.gender)          out.gender          = filters.gender
  if (filters.team_type)       out.team_type       = filters.team_type
  if (filters.tournament)      out.tournament      = filters.tournament
  if (filters.season_from)     out.season_from     = filters.season_from
  if (filters.season_to)       out.season_to       = filters.season_to
  if (filters.filter_venue)    out.filter_venue    = filters.filter_venue
  return out
}
