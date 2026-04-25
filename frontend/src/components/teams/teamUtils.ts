import type { FilterParams, TeamProfile, ScopeAverageProfile } from '../../types'

export type TeamDiscipline =
  | 'results' | 'batting' | 'bowling' | 'fielding' | 'partnerships'

/** Each discipline's "has meaningful data in scope" gate. Drives both
 *  per-column band visibility and the grid-wide anyHasData mask.
 *  Reads `.value` off the envelope. */
export function teamDisciplineHasData(
  discipline: TeamDiscipline, profile: TeamProfile,
): boolean {
  if (discipline === 'results')      return (profile.summary?.matches?.value ?? 0) > 0
  if (discipline === 'batting')      return (profile.batting?.innings_batted?.value ?? 0) > 0
  if (discipline === 'bowling')      return (profile.bowling?.innings_bowled?.value ?? 0) > 0
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return false
    return ((f.catches.value ?? 0) + (f.stumpings.value ?? 0) + (f.run_outs.value ?? 0)) > 0
  }
  return (profile.partnerships?.total?.value ?? 0) > 0
}

/** Same gate but for the league-average column. */
export function avgDisciplineHasData(
  discipline: TeamDiscipline, profile: ScopeAverageProfile,
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

/** Scope-computed label for the average column header. Constructs a
 *  short phrase from the active FilterBar fields — "IPL 2024 avg",
 *  "Men's T20I 2024 avg", or just "League avg" when nothing's set. */
export function scopeAvgLabel(filters: FilterParams): string {
  const parts: string[] = []
  if (filters.tournament) {
    parts.push(filters.tournament)
  } else if (filters.team_type === 'international') {
    if (filters.gender === 'male')   parts.push("Men's T20I")
    else if (filters.gender === 'female') parts.push("Women's T20I")
    else parts.push('Internationals')
  } else if (filters.team_type === 'club') {
    if (filters.gender === 'male')   parts.push("Men's club")
    else if (filters.gender === 'female') parts.push("Women's club")
    else parts.push('Club')
  }
  if (filters.season_from && filters.season_to) {
    parts.push(filters.season_from === filters.season_to
      ? filters.season_from
      : `${filters.season_from}-${filters.season_to}`)
  } else if (filters.season_from) {
    parts.push(`${filters.season_from}+`)
  } else if (filters.season_to) {
    parts.push(`-${filters.season_to}`)
  }
  if (parts.length === 0) return 'League avg'
  return `${parts.join(' ')} avg`
}

/** Filter-scoped match count for the column identity line. Uses
 *  summary.matches as the canonical match-level count (team_summary's
 *  COUNT(*) over the filtered match table). fielding.matches and
 *  bowling.matches are innings-derived and can diverge by a handful
 *  of abandoned / no-result matches where a team never fielded or
 *  bowled — correct for their own stats, misleading as a headline. */
export function teamMatchesInScope(profile: TeamProfile): number {
  return profile.summary?.matches?.value
    ?? profile.bowling?.matches?.value
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
