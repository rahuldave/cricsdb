import type { FilterParams, TeamProfile, ScopeAverageProfile } from '../../types'

export type TeamDiscipline =
  | 'results' | 'batting' | 'bowling' | 'fielding' | 'partnerships'

/** Stat rows rendered by TeamSummaryRow / AvgSummaryRow per discipline.
 *  This MUST stay in sync with the `statsFor` arrays in those two
 *  files (kept identical so column rows align). Used by the parent
 *  grid + each section's subgrid to declare row spans correctly. */
export const STAT_ROWS_BY_DISCIPLINE: Record<TeamDiscipline, number> = {
  results:      5,  // Matches, W, L, Win %, Toss won %
  batting:      5,  // Run rate, Boundary %, Avg 1st-inn, Highest, 100s + 50s
  bowling:      6,  // Economy, SR, Dot %, Avg opp. total, Wickets, Wickets/inn
  fielding:     6,  // Catches, Catches/inn, Stumpings, Stumpings/inn, Run-outs, Run-outs/inn
  partnerships: 7,  // Highest, 50+, 50+/inn, 100+, 100+/inn, Avg, Best pair
}

/** Phase-band rows — only batting + bowling carry these (PP, Mid, Death). */
export const PHASE_BAND_ROWS = 3

/** By-wicket rows — only partnerships (1st .. 10th wkt). */
export const BY_WICKET_ROWS = 10

/** Total parent-grid row tracks per visible discipline:
 *  section-head + stat rows + phase bands (batting/bowling) + by-wicket
 *  (partnerships). The TeamCompareGrid sums these to compute the parent
 *  grid's `gridTemplateRows`. */
export const DISCIPLINE_TOTAL_ROWS: Record<TeamDiscipline, number> = {
  results:      1 + STAT_ROWS_BY_DISCIPLINE.results,                          // 6
  batting:      1 + STAT_ROWS_BY_DISCIPLINE.batting + PHASE_BAND_ROWS,        // 9
  bowling:      1 + STAT_ROWS_BY_DISCIPLINE.bowling + PHASE_BAND_ROWS,        // 10
  fielding:     1 + STAT_ROWS_BY_DISCIPLINE.fielding,                         // 7
  partnerships: 1 + STAT_ROWS_BY_DISCIPLINE.partnerships + BY_WICKET_ROWS,    // 18
}

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

/** Same gate but for the league-average column. Keys on `legal_balls`
 *  for batting/bowling — `innings_batted`/`innings_bowled` are NOT
 *  on `ScopeBattingSummary`/`ScopeBowlingSummary` (spec dropped them
 *  per per-innings semantic; the type enforces it). */
export function avgDisciplineHasData(
  discipline: TeamDiscipline, profile: ScopeAverageProfile,
): boolean {
  if (discipline === 'results')      return (profile.summary?.matches ?? 0) > 0
  if (discipline === 'batting')      return (profile.batting?.legal_balls ?? 0) > 0
  if (discipline === 'bowling')      return (profile.bowling?.legal_balls ?? 0) > 0
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return false
    return (f.catches + f.stumpings + f.run_outs) > 0
  }
  return (profile.partnerships?.total ?? 0) > 0
}

/** Two-line scope-computed label for the avg column header.
 *  - `line1` is the column's *anchor* (rendered in the same h2 slot as
 *    team-col team names): "League average", "<Tournament> average", or
 *    "Full-member average". When `teamTournaments` is a singleton AND
 *    no explicit tournament filter is set AND team_type is 'club', the
 *    primary team's sole tournament is auto-promoted into line1 (e.g.
 *    RCB's universe collapses to IPL → "Indian Premier League average").
 *  - `line2` is the italic scope subtitle (rendered in the chip-area
 *    sub-line): gender + tier qualifier (when not redundant with line1)
 *    + season range, joined by " · ". Empty when nothing narrows. */
export interface ScopeAvgLabel { line1: string; line2: string }

export function scopeAvgLabel(
  filters: FilterParams,
  teamTournaments?: string[],
): ScopeAvgLabel {
  // Auto-promote the primary team's tournament when its universe
  // collapses to a singleton — same gate as the backend's _league_aux
  // scope_to_team narrowing (club + no explicit tournament).
  const promoted = !filters.tournament
    && filters.team_type === 'club'
    && teamTournaments?.length === 1
      ? teamTournaments[0]!
      : null
  const anchorTournament = filters.tournament || promoted

  let line1: string
  if (filters.team_class === 'full_member') {
    line1 = 'Full-member average'
  } else if (anchorTournament) {
    line1 = `${anchorTournament} average`
  } else if (filters.team_type === 'international') {
    // "League" implies a closed system (10 IPL teams) — wrong for
    // internationals, which are a collection of bilateral tours + ICC
    // events with no fixed roster. "International" reads cleanly next
    // to entity team cols ("Australia / International average / India").
    line1 = 'International average'
  } else {
    line1 = 'League average'
  }

  // line2 — gender + tier qualifier (only when not redundant with the
  // anchor) + season range.
  const parts: string[] = []
  const genderWord = filters.gender === 'male' ? "Men's"
                   : filters.gender === 'female' ? "Women's"
                   : ''

  if (anchorTournament) {
    // Tournament names already imply tier; keep gender only.
    if (genderWord) parts.push(genderWord)
  } else if (filters.team_class === 'full_member') {
    // "Full-member" always implies intl T20I; keep gender + T20I tier.
    parts.push(genderWord ? `${genderWord} T20I` : 'T20Is')
  } else if (filters.team_type === 'international') {
    parts.push(genderWord ? `${genderWord} T20I` : 'T20Is')
  } else if (filters.team_type === 'club') {
    parts.push(genderWord ? `${genderWord} club` : 'Clubs')
  } else if (genderWord) {
    parts.push(genderWord)
  }

  if (filters.season_from && filters.season_to) {
    parts.push(filters.season_from === filters.season_to
      ? filters.season_from
      : `${filters.season_from}–${filters.season_to}`)
  } else if (filters.season_from) {
    parts.push(`${filters.season_from}+`)
  } else if (filters.season_to) {
    parts.push(`–${filters.season_to}`)
  }

  return { line1, line2: parts.join(' · ') }
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
