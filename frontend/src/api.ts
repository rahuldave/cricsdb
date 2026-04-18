import type {
  FilterParams, Tournament, TeamInfo, PlayerSearchResult,
  TeamSummary, TeamResult, TeamSeasonRecord, TeamVsOpponent,
  BattingSummary, BattingInnings, BowlerMatchup, OverStats, PhaseStats,
  SeasonBattingStats, DismissalAnalysis, InterWicketStats,
  BowlingSummary, BowlingInnings, BatterMatchup, WicketAnalysis,
  HeadToHeadResponse,
  MatchListItem, Scorecard, InningsGridResponse,
  VenueInfo, VenuesLanding,
} from './types'

async function fetchApi<T>(path: string, params?: Record<string, string | number | undefined | null>): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value != null && value !== '') url.searchParams.set(key, String(value))
    }
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    // FastAPI HTTPException puts the message under `detail`. Surface it
    // so the UI can show "Bowler not found: 14ba0d6a" instead of just
    // "API error: 404".
    let detail: string | null = null
    try {
      const body = await res.json()
      if (body && typeof body.detail === 'string') detail = body.detail
    } catch { /* ignore — body wasn't JSON */ }
    throw new Error(detail ?? `API error: ${res.status}`)
  }
  return res.json()
}

type F = FilterParams

// Reference
export const getTournaments = (ctx?: { team?: string; opponent?: string; gender?: string; team_type?: string }) =>
  fetchApi<{ tournaments: Tournament[] }>('/api/v1/tournaments', ctx as Record<string, string>)
export const getSeasons = (ctx?: { team?: string; gender?: string; team_type?: string; tournament?: string }) =>
  fetchApi<{ seasons: string[] }>('/api/v1/seasons', ctx as Record<string, string>)
export const getTeams = (filters?: F & { q?: string }) =>
  fetchApi<{ teams: TeamInfo[] }>('/api/v1/teams', filters as Record<string, string>)
export const searchPlayers = (q: string, role?: string, limit = 20) =>
  fetchApi<{ players: PlayerSearchResult[] }>('/api/v1/players', { q, role, limit })

// Venues (Phase 2)
export const getVenues = (filters?: F & { q?: string; limit?: number }) =>
  fetchApi<{ venues: VenueInfo[] }>('/api/v1/venues', filters as Record<string, string>)
export const getVenuesLanding = (filters?: F) =>
  fetchApi<VenuesLanding>('/api/v1/venues/landing', filters as Record<string, string>)

// Teams
export const getTeamSummary = (team: string, filters?: F) =>
  fetchApi<TeamSummary>(`/api/v1/teams/${encodeURIComponent(team)}/summary`, filters as Record<string, string>)
export const getTeamResults = (team: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ results: TeamResult[]; total: number }>(`/api/v1/teams/${encodeURIComponent(team)}/results`, filters as Record<string, string>)
export const getTeamVs = (team: string, opponent: string, filters?: F) =>
  fetchApi<TeamVsOpponent>(`/api/v1/teams/${encodeURIComponent(team)}/vs/${encodeURIComponent(opponent)}`, filters as Record<string, string>)
export const getTeamOpponents = (team: string, filters?: F) =>
  fetchApi<{ opponents: { name: string; matches: number }[] }>(`/api/v1/teams/${encodeURIComponent(team)}/opponents`, filters as Record<string, string>)
export const getTeamOpponentsMatrix = (team: string, filters?: F & { top_n?: number }) =>
  fetchApi<import('./types').OpponentsMatrix>(`/api/v1/teams/${encodeURIComponent(team)}/opponents-matrix`, filters as Record<string, string>)
export const getTeamByseason = (team: string, filters?: F) =>
  fetchApi<{ seasons: TeamSeasonRecord[] }>(`/api/v1/teams/${encodeURIComponent(team)}/by-season`, filters as Record<string, string>)
export const getTeamPlayersBySeason = (team: string, filters?: F) =>
  fetchApi<import('./types').TeamPlayersBySeason>(`/api/v1/teams/${encodeURIComponent(team)}/players-by-season`, filters as Record<string, string>)
export const getTeamsLanding = (filters?: F) =>
  fetchApi<import('./types').TeamsLanding>(`/api/v1/teams/landing`, filters as Record<string, string>)

// Batting
export const getBattingLeaders = (filters?: F & { limit?: number; min_balls?: number; min_dismissals?: number }) =>
  fetchApi<import('./types').BattingLeaders>(`/api/v1/batters/leaders`, filters as Record<string, string>)
export const getBatterSummary = (id: string, filters?: F) =>
  fetchApi<BattingSummary>(`/api/v1/batters/${id}/summary`, filters as Record<string, string>)
export const getBatterInnings = (id: string, filters?: F & { limit?: number; offset?: number; sort?: string }) =>
  fetchApi<{ innings: BattingInnings[]; total: number }>(`/api/v1/batters/${id}/by-innings`, filters as Record<string, string>)
export const getBatterVsBowlers = (id: string, filters?: F & { bowler_id?: string; min_balls?: number }) =>
  fetchApi<{ matchups: BowlerMatchup[] }>(`/api/v1/batters/${id}/vs-bowlers`, filters as Record<string, string>)
export const getBatterByOver = (id: string, filters?: F) =>
  fetchApi<{ by_over: OverStats[] }>(`/api/v1/batters/${id}/by-over`, filters as Record<string, string>)
export const getBatterByPhase = (id: string, filters?: F) =>
  fetchApi<{ by_phase: PhaseStats[] }>(`/api/v1/batters/${id}/by-phase`, filters as Record<string, string>)
export const getBatterBySeason = (id: string, filters?: F) =>
  fetchApi<{ by_season: SeasonBattingStats[] }>(`/api/v1/batters/${id}/by-season`, filters as Record<string, string>)
export const getBatterDismissals = (id: string, filters?: F) =>
  fetchApi<DismissalAnalysis>(`/api/v1/batters/${id}/dismissals`, filters as Record<string, string>)
export const getBatterInterWicket = (id: string, filters?: F) =>
  fetchApi<{ inter_wicket: InterWicketStats[] }>(`/api/v1/batters/${id}/inter-wicket`, filters as Record<string, string>)

// Bowling
export const getBowlingLeaders = (filters?: F & { limit?: number; min_balls?: number; min_wickets?: number }) =>
  fetchApi<import('./types').BowlingLeaders>(`/api/v1/bowlers/leaders`, filters as Record<string, string>)
export const getBowlerSummary = (id: string, filters?: F) =>
  fetchApi<BowlingSummary>(`/api/v1/bowlers/${id}/summary`, filters as Record<string, string>)
export const getBowlerInnings = (id: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ innings: BowlingInnings[]; total: number }>(`/api/v1/bowlers/${id}/by-innings`, filters as Record<string, string>)
export const getBowlerVsBatters = (id: string, filters?: F & { batter_id?: string; min_balls?: number }) =>
  fetchApi<{ matchups: BatterMatchup[] }>(`/api/v1/bowlers/${id}/vs-batters`, filters as Record<string, string>)
export const getBowlerByOver = (id: string, filters?: F) =>
  fetchApi<{ by_over: OverStats[] }>(`/api/v1/bowlers/${id}/by-over`, filters as Record<string, string>)
export const getBowlerByPhase = (id: string, filters?: F) =>
  fetchApi<{ by_phase: PhaseStats[] }>(`/api/v1/bowlers/${id}/by-phase`, filters as Record<string, string>)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const getBowlerBySeason = (id: string, filters?: F) =>
  fetchApi<{ by_season: any[] }>(`/api/v1/bowlers/${id}/by-season`, filters as Record<string, string>)
export const getBowlerWickets = (id: string, filters?: F) =>
  fetchApi<WicketAnalysis>(`/api/v1/bowlers/${id}/wickets`, filters as Record<string, string>)

// Fielding
export const getFieldingLeaders = (filters?: F & { limit?: number }) =>
  fetchApi<import('./types').FieldingLeaders>(`/api/v1/fielders/leaders`, filters as Record<string, string>)
export const getFielderSummary = (id: string, filters?: F) =>
  fetchApi<import('./types').FieldingSummary>(`/api/v1/fielders/${id}/summary`, filters as Record<string, string>)
export const getFielderBySeason = (id: string, filters?: F) =>
  fetchApi<{ by_season: import('./types').FieldingSeason[] }>(`/api/v1/fielders/${id}/by-season`, filters as Record<string, string>)
export const getFielderByPhase = (id: string, filters?: F) =>
  fetchApi<{ by_phase: import('./types').FieldingPhase[] }>(`/api/v1/fielders/${id}/by-phase`, filters as Record<string, string>)
export const getFielderByOver = (id: string, filters?: F) =>
  fetchApi<{ by_over: { over_number: number; dismissals: number }[] }>(`/api/v1/fielders/${id}/by-over`, filters as Record<string, string>)
export const getFielderDismissalTypes = (id: string, filters?: F) =>
  fetchApi<{ total: number; by_kind: Record<string, number> }>(`/api/v1/fielders/${id}/dismissal-types`, filters as Record<string, string>)
export const getFielderVictims = (id: string, filters?: F & { limit?: number }) =>
  fetchApi<{ victims: import('./types').FieldingVictim[] }>(`/api/v1/fielders/${id}/victims`, filters as Record<string, string>)
export const getFielderInnings = (id: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ innings: import('./types').FieldingInnings[]; total: number }>(`/api/v1/fielders/${id}/by-innings`, filters as Record<string, string>)

// Composed player overview — four summary endpoints in parallel.
// `.catch(() => null)` per sub-fetch so a 404 on one discipline
// (specialist batter → no bowling row) doesn't blow up the whole
// profile. The /players page expects nulls where disciplines are
// missing; it hides those rows.
export const getPlayerProfile = async (id: string, filters?: F) => {
  const [batting, bowling, fielding, keeping] = await Promise.all([
    getBatterSummary(id, filters).catch(() => null),
    getBowlerSummary(id, filters).catch(() => null),
    getFielderSummary(id, filters).catch(() => null),
    getFielderKeepingSummary(id, filters).catch(() => null),
  ])
  return { batting, bowling, fielding, keeping } as import('./types').PlayerProfile
}

// Keeping (Tier 2 fielding)
export const getFielderKeepingSummary = (id: string, filters?: F) =>
  fetchApi<import('./types').KeepingSummary>(`/api/v1/fielders/${id}/keeping/summary`, filters as Record<string, string>)
export const getFielderKeepingBySeason = (id: string, filters?: F) =>
  fetchApi<{ by_season: import('./types').KeepingSeason[] }>(`/api/v1/fielders/${id}/keeping/by-season`, filters as Record<string, string>)
export const getFielderKeepingInnings = (id: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ innings: import('./types').KeepingInnings[]; total: number }>(`/api/v1/fielders/${id}/keeping/by-innings`, filters as Record<string, string>)
export const getFielderKeepingAmbiguous = (id: string, filters?: F & { limit?: number }) =>
  fetchApi<{ innings: import('./types').KeepingAmbiguousInnings[]; total: number }>(`/api/v1/fielders/${id}/keeping/ambiguous`, filters as Record<string, string>)

// Matches
export const getMatches = (filters?: F & { team?: string; player_id?: string; limit?: number; offset?: number }) =>
  fetchApi<{ matches: MatchListItem[]; total: number }>('/api/v1/matches', filters as Record<string, string>)
export const getMatchScorecard = (matchId: number) =>
  fetchApi<Scorecard>(`/api/v1/matches/${matchId}/scorecard`)
export const getInningsGrid = (matchId: number) =>
  fetchApi<InningsGridResponse>(`/api/v1/matches/${matchId}/innings-grid`)

// Head to Head
export const getHeadToHead = (
  batterId: string, bowlerId: string,
  filters?: F & { series_type?: string },
) =>
  fetchApi<HeadToHeadResponse>(`/api/v1/head-to-head/${batterId}/${bowlerId}`, filters as Record<string, string>)

// Team stats — batting / bowling / fielding / partnerships
const te = encodeURIComponent

export const getTeamBattingSummary = (team: string, filters?: F) =>
  fetchApi<import('./types').TeamBattingSummary>(`/api/v1/teams/${te(team)}/batting/summary`, filters as Record<string, string>)
export const getTeamBattingBySeason = (team: string, filters?: F) =>
  fetchApi<{ seasons: import('./types').TeamBattingSeason[] }>(`/api/v1/teams/${te(team)}/batting/by-season`, filters as Record<string, string>)
export const getTeamBattingByPhase = (team: string, filters?: F) =>
  fetchApi<{ phases: import('./types').TeamBattingPhase[] }>(`/api/v1/teams/${te(team)}/batting/by-phase`, filters as Record<string, string>)
export const getTeamTopBatters = (team: string, filters?: F & { limit?: number }) =>
  fetchApi<{ top_batters: import('./types').TeamTopBatter[] }>(`/api/v1/teams/${te(team)}/batting/top-batters`, filters as Record<string, string>)
export const getTeamBattingPhaseSeasonHeatmap = (team: string, filters?: F) =>
  fetchApi<import('./types').BattingPhaseSeasonHeatmap>(`/api/v1/teams/${te(team)}/batting/phase-season-heatmap`, filters as Record<string, string>)

export const getTeamBowlingSummary = (team: string, filters?: F) =>
  fetchApi<import('./types').TeamBowlingSummary>(`/api/v1/teams/${te(team)}/bowling/summary`, filters as Record<string, string>)
export const getTeamBowlingBySeason = (team: string, filters?: F) =>
  fetchApi<{ seasons: import('./types').TeamBowlingSeason[] }>(`/api/v1/teams/${te(team)}/bowling/by-season`, filters as Record<string, string>)
export const getTeamBowlingByPhase = (team: string, filters?: F) =>
  fetchApi<{ phases: import('./types').TeamBowlingPhase[] }>(`/api/v1/teams/${te(team)}/bowling/by-phase`, filters as Record<string, string>)
export const getTeamTopBowlers = (team: string, filters?: F & { limit?: number }) =>
  fetchApi<{ top_bowlers: import('./types').TeamTopBowler[] }>(`/api/v1/teams/${te(team)}/bowling/top-bowlers`, filters as Record<string, string>)
export const getTeamBowlingPhaseSeasonHeatmap = (team: string, filters?: F) =>
  fetchApi<import('./types').BowlingPhaseSeasonHeatmap>(`/api/v1/teams/${te(team)}/bowling/phase-season-heatmap`, filters as Record<string, string>)

export const getTeamFieldingSummary = (team: string, filters?: F) =>
  fetchApi<import('./types').TeamFieldingSummary>(`/api/v1/teams/${te(team)}/fielding/summary`, filters as Record<string, string>)
export const getTeamFieldingBySeason = (team: string, filters?: F) =>
  fetchApi<{ seasons: import('./types').TeamFieldingSeason[] }>(`/api/v1/teams/${te(team)}/fielding/by-season`, filters as Record<string, string>)
export const getTeamTopFielders = (team: string, filters?: F & { limit?: number }) =>
  fetchApi<{ top_fielders: import('./types').TeamTopFielder[] }>(`/api/v1/teams/${te(team)}/fielding/top-fielders`, filters as Record<string, string>)

export const getTeamPartnershipsByWicket = (team: string, filters?: F & { side?: 'batting' | 'bowling' }) =>
  fetchApi<{ team: string; side: 'batting' | 'bowling'; by_wicket: import('./types').PartnershipByWicket[] }>(
    `/api/v1/teams/${te(team)}/partnerships/by-wicket`, filters as Record<string, string>)
export const getTeamPartnershipsBestPairs = (team: string, filters?: F & { side?: 'batting' | 'bowling'; min_n?: number; top_n?: number }) =>
  fetchApi<import('./types').PartnershipBestPairsResponse>(
    `/api/v1/teams/${te(team)}/partnerships/best-pairs`, filters as Record<string, string>)
export const getTeamPartnershipsHeatmap = (team: string, filters?: F & { side?: 'batting' | 'bowling' }) =>
  fetchApi<import('./types').PartnershipHeatmap>(`/api/v1/teams/${te(team)}/partnerships/heatmap`, filters as Record<string, string>)
export const getTeamPartnershipsTop = (team: string, filters?: F & { side?: 'batting' | 'bowling'; limit?: number }) =>
  fetchApi<{ team: string; side: 'batting' | 'bowling'; partnerships: import('./types').PartnershipTopEntry[] }>(
    `/api/v1/teams/${te(team)}/partnerships/top`, filters as Record<string, string>)
export const getTeamPartnershipsSummary = (team: string, filters?: F & { side?: 'batting' | 'bowling' }) =>
  fetchApi<import('./types').TeamPartnershipsSummary>(
    `/api/v1/teams/${te(team)}/partnerships/summary`, filters as Record<string, string>)

// Composed team overview — five summary endpoints in parallel. Mirrors
// getPlayerProfile: `.catch(() => null)` per sub-fetch so a scope that
// yields zero results in one discipline (e.g. a defunct team with no
// recent partnerships) doesn't blow up the whole column. Consumed by
// TeamCompareGrid which hides rows where every column is null.
export const getTeamProfile = async (team: string, filters?: F) => {
  const [summary, batting, bowling, fielding, partnerships] = await Promise.all([
    getTeamSummary(team, filters).catch(() => null),
    getTeamBattingSummary(team, filters).catch(() => null),
    getTeamBowlingSummary(team, filters).catch(() => null),
    getTeamFieldingSummary(team, filters).catch(() => null),
    getTeamPartnershipsSummary(team, filters).catch(() => null),
  ])
  return { summary, batting, bowling, fielding, partnerships } as import('./types').TeamProfile
}

// Tournaments / match-set dossier — `tournament` is optional; omit for
// cross-tournament rivalry views (filter_team + filter_opponent in filters).
type TF = F & { series_type?: string; filter_team?: string; filter_opponent?: string }
const tparams = (t: string | null | undefined, f?: TF) => {
  const out: Record<string, string> = { ...(f as Record<string, string>) }
  if (t) out.tournament = t
  return out
}

export const getTournamentsLanding = (filters?: F) =>
  fetchApi<import('./types').TournamentsLanding>('/api/v1/series/landing', filters as Record<string, string>)
export const getTournamentSummary = (tournament: string | null, filters?: TF) =>
  fetchApi<import('./types').TournamentSummary>('/api/v1/series/summary', tparams(tournament, filters))
export const getTournamentBySeason = (tournament: string | null, filters?: TF) =>
  fetchApi<{ tournament: string; seasons: import('./types').TournamentSeason[] }>(
    '/api/v1/series/by-season', tparams(tournament, filters))
export const getTournamentPointsTable = (tournament: string, filters?: TF) =>
  fetchApi<import('./types').TournamentPointsTableResponse>(
    '/api/v1/series/points-table', { ...(filters as Record<string, string>), tournament })
export const getTournamentRecords = (tournament: string | null, filters?: TF & { limit?: number }) =>
  fetchApi<import('./types').TournamentRecords>(
    '/api/v1/series/records', tparams(tournament, filters))
export const getTournamentOtherRivalries = (filters?: F & { gender?: string }) =>
  fetchApi<{ rivalries: import('./types').RivalryEntry[]; threshold: number }>(
    '/api/v1/series/other-rivalries', filters as Record<string, string>)
export const getRivalrySummary = (team1: string, team2: string, filters?: F) =>
  fetchApi<import('./types').RivalrySummary>(
    '/api/v1/rivalries/summary', { ...(filters as Record<string, string>), team1, team2 })

// Variant-aware leader endpoints for tournament dossiers (canonical → IN variants)
export const getTournamentBattersLeaders = (tournament: string | null, filters?: TF & { limit?: number }) =>
  fetchApi<import('./types').BattingLeaders>(
    '/api/v1/series/batters-leaders', tparams(tournament, filters))
export const getTournamentBowlersLeaders = (tournament: string | null, filters?: TF & { limit?: number }) =>
  fetchApi<import('./types').BowlingLeaders>(
    '/api/v1/series/bowlers-leaders', tparams(tournament, filters))
export const getTournamentFieldersLeaders = (tournament: string | null, filters?: TF & { limit?: number }) =>
  fetchApi<import('./types').FieldingLeaders>(
    '/api/v1/series/fielders-leaders', tparams(tournament, filters))

export const getTournamentPartnershipsByWicket = (
  tournament: string | null, filters?: TF & { side?: 'batting' | 'bowling' },
) => fetchApi<import('./types').TournamentPartnershipsByWicket>(
  '/api/v1/series/partnerships/by-wicket', tparams(tournament, filters))
export const getTournamentPartnershipsTop = (
  tournament: string | null, filters?: TF & { side?: 'batting' | 'bowling'; limit?: number },
) => fetchApi<import('./types').TournamentPartnershipsTop>(
  '/api/v1/series/partnerships/top', tparams(tournament, filters))
export const getTournamentPartnershipsHeatmap = (
  tournament: string | null, filters?: TF & { side?: 'batting' | 'bowling' },
) => fetchApi<import('./types').TournamentPartnershipsHeatmap>(
  '/api/v1/series/partnerships/heatmap', tparams(tournament, filters))
