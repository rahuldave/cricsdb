import type {
  FilterParams, Tournament, TeamInfo, PlayerSearchResult,
  TeamSummary, TeamResult, TeamSeasonRecord, TeamVsOpponent,
  BattingSummary, BattingInnings, BowlerMatchup, OverStats, PhaseStats,
  SeasonBattingStats, DismissalAnalysis, InterWicketStats,
  BowlingSummary, BowlingInnings, BatterMatchup, WicketAnalysis,
  HeadToHeadResponse,
  MatchListItem, Scorecard, InningsGridResponse,
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
export const getTournaments = () =>
  fetchApi<{ tournaments: Tournament[] }>('/api/v1/tournaments')
export const getSeasons = () =>
  fetchApi<{ seasons: string[] }>('/api/v1/seasons')
export const getTeams = (filters?: F & { q?: string }) =>
  fetchApi<{ teams: TeamInfo[] }>('/api/v1/teams', filters as Record<string, string>)
export const searchPlayers = (q: string, role?: string, limit = 20) =>
  fetchApi<{ players: PlayerSearchResult[] }>('/api/v1/players', { q, role, limit })

// Teams
export const getTeamSummary = (team: string, filters?: F) =>
  fetchApi<TeamSummary>(`/api/v1/teams/${encodeURIComponent(team)}/summary`, filters as Record<string, string>)
export const getTeamResults = (team: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ results: TeamResult[]; total: number }>(`/api/v1/teams/${encodeURIComponent(team)}/results`, filters as Record<string, string>)
export const getTeamVs = (team: string, opponent: string, filters?: F) =>
  fetchApi<TeamVsOpponent>(`/api/v1/teams/${encodeURIComponent(team)}/vs/${encodeURIComponent(opponent)}`, filters as Record<string, string>)
export const getTeamOpponents = (team: string, filters?: F) =>
  fetchApi<{ opponents: { name: string; matches: number }[] }>(`/api/v1/teams/${encodeURIComponent(team)}/opponents`, filters as Record<string, string>)
export const getTeamByseason = (team: string, filters?: F) =>
  fetchApi<{ seasons: TeamSeasonRecord[] }>(`/api/v1/teams/${encodeURIComponent(team)}/by-season`, filters as Record<string, string>)

// Batting
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
export const getHeadToHead = (batterId: string, bowlerId: string, filters?: F) =>
  fetchApi<HeadToHeadResponse>(`/api/v1/head-to-head/${batterId}/${bowlerId}`, filters as Record<string, string>)
