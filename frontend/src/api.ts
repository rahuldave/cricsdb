/**
 * The fetchers for the cricsdb API: one function per `/api/v1` endpoint, plus composers that call several at once.
 *
 * Each fetcher drops empty parameters, throws an `Error` with the server's `detail` when the request fails,
 * and shares one request between identical calls that are in flight at the same time.
 */
import type {
  FilterParams, Tournament, TeamInfo, PlayerSearchResult,
  TeamSummary, TeamResult, TeamSeasonRecord, TeamVsOpponent,
  BattingSummary, BattingInnings, BowlerMatchup, OverStats, PhaseStats,
  SeasonBattingStats, DismissalAnalysis, InterWicketStats,
  BowlingSummary, BowlingInnings, BatterMatchup, WicketAnalysis,
  HeadToHeadResponse,
  MatchListItem, Scorecard, InningsGridResponse,
  VenueInfo, VenuesLanding, VenueSummary,
} from './types'

// In-flight request dedup. React StrictMode dev replay fires every
// useFetch effect twice on mount — the second call has identical URL
// + params and would hit the server again. Collapsing identical
// in-flight GETs into one shared Promise halves dev-mode API time
// (HAR-measured 2026-05-22: 6 duplicate /summary calls on /players?
// player=X each ~1s totalling ~3s). In production StrictMode replay
// doesn't fire, so this is a no-op for end-user load time. The wider
// optimisation (slow /summary endpoints themselves) is queued —
// see memory project_player_summary_perf_followup.md.
const _inflight = new Map<string, Promise<unknown>>()

async function fetchApi<T>(path: string, params?: Record<string, string | number | undefined | null>): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value != null && value !== '') url.searchParams.set(key, String(value))
    }
  }
  const urlStr = url.toString()
  const existing = _inflight.get(urlStr)
  if (existing) return existing as Promise<T>
  const promise = (async () => {
    try {
      const res = await fetch(urlStr)
      if (!res.ok) {
        // FastAPI HTTPException puts the message under `detail`. Surface
        // it so the UI can show "Bowler not found: 14ba0d6a" instead of
        // just "API error: 404".
        let detail: string | null = null
        try {
          const body = await res.json()
          if (body && typeof body.detail === 'string') detail = body.detail
        } catch { /* ignore — body wasn't JSON */ }
        throw new Error(detail ?? `API error: ${res.status}`)
      }
      return (await res.json()) as T
    } finally {
      _inflight.delete(urlStr)
    }
  })()
  _inflight.set(urlStr, promise)
  return promise
}

type F = FilterParams

// Reference. `getTournaments` / `getSeasons` accept the full FilterParams
// shape plus a few extras: path `team`, rivalry `opponent`, page-local
// `series_type`. Backend drops its own self-referential axis —
// /tournaments ignores `tournament`, /seasons ignores `season_from`/
// `season_to` — so callers can pass the whole filter state without
// stripping fields per endpoint.
type ReferenceCtx = F & {
  team?: string
  opponent?: string
  series_type?: string
  /** Frontend URL convention: `?player=<id>`. /api/v1/seasons accepts
   *  this as `person_id`; the wrapper below renames before send so
   *  callers don't need to know the backend convention. Player-aware
   *  seasons fix the retired-player gap on first-3 / last-3 buttons —
   *  see internal_docs/design-decisions.md "FilterBar season-window
   *  quick-select buttons". */
  player?: string
}
/**
 * Fetch the tournaments that match the filters.
 * @param ctx the filters, and optionally a team, an opponent or a player
 * @returns the list of tournaments
 */
export const getTournaments = (ctx?: ReferenceCtx) =>
  fetchApi<{ tournaments: Tournament[] }>('/api/v1/tournaments', ctx as Record<string, string>)
/**
 * Fetch the seasons that match the filters; a `player` is sent as `person_id`.
 * @param ctx the filters, and optionally a team, an opponent or a player
 * @returns the list of seasons, oldest first
 */
export const getSeasons = (ctx?: ReferenceCtx) => {
  // Translate frontend `player` → backend `person_id`. Strip the
  // frontend-side key so it doesn't double-up in the query string.
  if (!ctx) return fetchApi<{ seasons: string[] }>('/api/v1/seasons')
  const { player, ...rest } = ctx
  const sendCtx = player ? { ...rest, person_id: player } : rest
  return fetchApi<{ seasons: string[] }>('/api/v1/seasons', sendCtx as Record<string, string>)
}
/**
 * Search team names at the filter scope.
 * @param filters the FilterBar filters, and `q` to match a part of the name
 * @returns the teams, each with its match count
 */
export const getTeams = (filters?: F & { q?: string }) =>
  fetchApi<{ teams: TeamInfo[] }>('/api/v1/teams', filters as Record<string, string>)
/**
 * Search players by name, optionally narrowed to people who played in the scope.
 * @param q the text to match, at least 2 characters
 * @param role `batter`, `bowler` or `fielder`; batters when absent
 * @param scope the FilterBar filters and `series_type`; when set, only people who played in scope matches
 * @param limit the most players to return
 * @returns the matching players
 */
export const searchPlayers = (
  q: string, role?: string,
  scope?: F & { series_type?: string },
  limit = 20,
) =>
  fetchApi<{ players: PlayerSearchResult[] }>('/api/v1/players', {
    q, role, limit,
    ...(scope as Record<string, string | undefined> | undefined),
  })

// Venues (Phase 2)
/**
 * Search venues at the filter scope, for the Venue typeahead.
 * @param filters the FilterBar filters, `q` to match venue or city, and `limit`
 * @returns the venues, by match count when there is no `q`
 */
export const getVenues = (filters?: F & { q?: string; limit?: number }) =>
  fetchApi<{ venues: VenueInfo[] }>('/api/v1/venues', filters as Record<string, string>)
/**
 * Fetch the venue directory for the `/venues` landing page.
 * @param filters the FilterBar filters
 * @returns the venues grouped by country, by match count
 */
export const getVenuesLanding = (filters?: F) =>
  fetchApi<VenuesLanding>('/api/v1/venues/landing', filters as Record<string, string>)
/**
 * Fetch the dossier of one venue.
 * @param venue the venue name
 * @param filters the FilterBar filters; any venue filter is replaced by `venue`
 * @returns the venue summary; `matches` is 0 when no match in scope
 */
export const getVenueSummary = (venue: string, filters?: F) =>
  fetchApi<VenueSummary>(
    `/api/v1/venues/${encodeURIComponent(venue)}/summary`,
    filters as Record<string, string>,
  )

// Teams
/**
 * Fetch the top-line record of a team.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the team summary
 */
export const getTeamSummary = (team: string, filters?: F) =>
  fetchApi<TeamSummary>(`/api/v1/teams/${encodeURIComponent(team)}/summary`, filters as Record<string, string>)
/**
 * Fetch a page of a team's match results.
 * @param team the team name
 * @param filters the FilterBar filters, and `limit` and `offset` for paging
 * @returns the results on this page and the total count
 */
export const getTeamResults = (team: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ results: TeamResult[]; total: number }>(`/api/v1/teams/${encodeURIComponent(team)}/results`, filters as Record<string, string>)
/**
 * Fetch a team's record against one opponent.
 * @param team the team name
 * @param opponent the opponent's name
 * @param filters the FilterBar filters
 * @returns the overall record, the record by season and the matches
 */
export const getTeamVs = (team: string, opponent: string, filters?: F) =>
  fetchApi<TeamVsOpponent>(`/api/v1/teams/${encodeURIComponent(team)}/vs/${encodeURIComponent(opponent)}`, filters as Record<string, string>)
/**
 * Fetch the teams that a team has played, with match counts.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the opponents and their match counts
 */
export const getTeamOpponents = (team: string, filters?: F) =>
  fetchApi<{ opponents: { name: string; matches: number }[] }>(`/api/v1/teams/${encodeURIComponent(team)}/opponents`, filters as Record<string, string>)
/**
 * Fetch a team's record against its main opponents, in total and by season.
 * @param team the team name
 * @param filters the FilterBar filters, and `top_n`, the number of opponents
 * @returns the rollup per opponent and the per-season cells
 */
export const getTeamOpponentsMatrix = (team: string, filters?: F & { top_n?: number }) =>
  fetchApi<import('./types').OpponentsMatrix>(`/api/v1/teams/${encodeURIComponent(team)}/opponents-matrix`, filters as Record<string, string>)
/**
 * Fetch a team's wins and losses by season.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one record per season
 */
export const getTeamByseason = (team: string, filters?: F) =>
  fetchApi<{ seasons: TeamSeasonRecord[] }>(`/api/v1/teams/${encodeURIComponent(team)}/by-season`, filters as Record<string, string>)
/**
 * Fetch the players of a team in each season.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the roster of each season, with turnover
 */
export const getTeamPlayersBySeason = (team: string, filters?: F) =>
  fetchApi<import('./types').TeamPlayersBySeason>(`/api/v1/teams/${encodeURIComponent(team)}/players-by-season`, filters as Record<string, string>)
/**
 * Fetch the team directory for the `/teams` landing page.
 * @param filters the FilterBar filters
 * @returns the international and club teams, in groups
 */
export const getTeamsLanding = (filters?: F) =>
  fetchApi<import('./types').TeamsLanding>(`/api/v1/teams/landing`, filters as Record<string, string>)
/**
 * Fetch the split of matches by toss, innings and result, for the Splits mosaic.
 * @param filters the FilterBar filters, and `team` for one team against the league
 * @returns the cells of the splits grid
 */
export const getTeamSplits = (filters?: F & { team?: string }) =>
  fetchApi<import('./types').TeamSplits>(`/api/v1/teams/splits`, filters as Record<string, string>)
/**
 * Fetch a team's record lists, such as highest totals and biggest wins.
 * @param team the team name
 * @param filters the FilterBar filters, and `limit`, the length of each list
 * @returns the record lists
 */
export const getTeamRecords = (team: string, filters?: F & { limit?: number }) =>
  fetchApi<import('./types').TournamentRecords>(`/api/v1/teams/${encodeURIComponent(team)}/records`, filters as Record<string, string>)

// Batting
/**
 * Fetch the top batters by average and by strike rate.
 * @param filters the FilterBar filters, `limit`, and the `min_balls` and `min_dismissals` thresholds
 * @returns the leader lists
 */
export const getBattingLeaders = (filters?: F & { limit?: number; min_balls?: number; min_dismissals?: number }) =>
  fetchApi<import('./types').BattingLeaders>(`/api/v1/batters/leaders`, filters as Record<string, string>)
/**
 * Fetch a player's batting summary.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the batting summary
 */
export const getBatterSummary = (id: string, filters?: F) =>
  fetchApi<BattingSummary>(`/api/v1/batters/${id}/summary`, filters as Record<string, string>)
/**
 * Fetch a player's batting record lists, such as highest scores and fastest fifties.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `limit`, the length of each list
 * @returns the record lists
 */
export const getBatterRecords = (id: string, filters?: F & { limit?: number }) =>
  fetchApi<import('./types').BatterRecords>(`/api/v1/batters/${id}/records`, filters as Record<string, string>)
/**
 * Fetch a page of a player's batting innings.
 * @param id the player's person id
 * @param filters the FilterBar filters, `limit` and `offset` for paging, and `sort`
 * @returns the innings on this page and the total count
 */
export const getBatterInnings = (id: string, filters?: F & { limit?: number; offset?: number; sort?: string }) =>
  fetchApi<{ innings: BattingInnings[]; total: number }>(`/api/v1/batters/${id}/by-innings`, filters as Record<string, string>)
/**
 * Fetch a player's batting record against each bowler.
 * @param id the player's person id
 * @param filters the FilterBar filters, `bowler_id` for one bowler, `min_balls` and `limit`
 * @returns the matchups
 */
export const getBatterVsBowlers = (id: string, filters?: F & { bowler_id?: string; min_balls?: number; limit?: number }) =>
  fetchApi<{ matchups: BowlerMatchup[] }>(`/api/v1/batters/${id}/vs-bowlers`, filters as Record<string, string>)
/**
 * Fetch a player's batting stats in each over.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per over
 */
export const getBatterByOver = (id: string, filters?: F) =>
  fetchApi<{ by_over: OverStats[] }>(`/api/v1/batters/${id}/by-over`, filters as Record<string, string>)
/**
 * Fetch a player's batting stats in the powerplay, middle and death overs.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getBatterByPhase = (id: string, filters?: F) =>
  fetchApi<{ by_phase: PhaseStats[] }>(`/api/v1/batters/${id}/by-phase`, filters as Record<string, string>)
/**
 * Fetch a player's batting stats by season.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getBatterBySeason = (id: string, filters?: F) =>
  fetchApi<{ by_season: SeasonBattingStats[] }>(`/api/v1/batters/${id}/by-season`, filters as Record<string, string>)
/**
 * Fetch how a player gets out as a batter.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the dismissal analysis
 */
export const getBatterDismissals = (id: string, filters?: F) =>
  fetchApi<DismissalAnalysis>(`/api/v1/batters/${id}/dismissals`, filters as Record<string, string>)
// Pooled-scope cohort dismissal distribution — backs the 3 normalized
// cohort charts on the Dismissals tab. No person_id: it's the league-
// wide pool at the FilterBar scope (same cohort the By Over / By Phase
// tabs compare against).
/**
 * Fetch how all batters in scope get out, for the cohort charts of the Dismissals tab.
 * @param filters the FilterBar filters
 * @returns the dismissal distribution of the scope
 */
export const getScopeDismissals = (filters?: F) =>
  fetchApi<import('./types').ScopeDismissals>('/api/v1/scope/averages/batting/dismissals', filters as Record<string, string>)
/**
 * Fetch the runs and rate of a player's innings between each fall of wicket.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per number of wickets down (0-10) at which the batter faced a ball
 */
export const getBatterInterWicket = (id: string, filters?: F) =>
  fetchApi<{ inter_wicket: InterWicketStats[] }>(`/api/v1/batters/${id}/inter-wicket`, filters as Record<string, string>)
/**
 * Fetch the per-innings distribution dossier of a player's batting.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the batting distribution
 */
export const getBatterDistribution = (id: string, filters?: F) =>
  fetchApi<import('./types').BatterDistribution>(`/api/v1/batters/${id}/distribution`, filters as Record<string, string>)

// Bowling
/**
 * Fetch the top bowlers.
 * @param filters the FilterBar filters, `limit`, and the `min_balls` and `min_wickets` thresholds
 * @returns the leader lists
 */
export const getBowlingLeaders = (filters?: F & { limit?: number; min_balls?: number; min_wickets?: number }) =>
  fetchApi<import('./types').BowlingLeaders>(`/api/v1/bowlers/leaders`, filters as Record<string, string>)
/**
 * Fetch a player's bowling summary.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the bowling summary
 */
export const getBowlerSummary = (id: string, filters?: F) =>
  fetchApi<BowlingSummary>(`/api/v1/bowlers/${id}/summary`, filters as Record<string, string>)
/**
 * Fetch a player's bowling record lists, such as best figures.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `limit`, the length of each list
 * @returns the record lists
 */
export const getBowlerRecords = (id: string, filters?: F & { limit?: number }) =>
  fetchApi<import('./types').BowlerRecords>(`/api/v1/bowlers/${id}/records`, filters as Record<string, string>)
/**
 * Fetch a page of a player's bowling innings.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `limit` and `offset` for paging
 * @returns the innings on this page and the total count
 */
export const getBowlerInnings = (id: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ innings: BowlingInnings[]; total: number }>(`/api/v1/bowlers/${id}/by-innings`, filters as Record<string, string>)
/**
 * Fetch a player's bowling record against each batter.
 * @param id the player's person id
 * @param filters the FilterBar filters, `batter_id` for one batter, `min_balls` and `limit`
 * @returns the matchups
 */
export const getBowlerVsBatters = (id: string, filters?: F & { batter_id?: string; min_balls?: number; limit?: number }) =>
  fetchApi<{ matchups: BatterMatchup[] }>(`/api/v1/bowlers/${id}/vs-batters`, filters as Record<string, string>)
/**
 * Fetch a player's bowling stats in each over.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per over
 */
export const getBowlerByOver = (id: string, filters?: F) =>
  fetchApi<{ by_over: OverStats[] }>(`/api/v1/bowlers/${id}/by-over`, filters as Record<string, string>)
/**
 * Fetch a player's bowling stats in the powerplay, middle and death overs.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getBowlerByPhase = (id: string, filters?: F) =>
  fetchApi<{ by_phase: PhaseStats[] }>(`/api/v1/bowlers/${id}/by-phase`, filters as Record<string, string>)
/**
 * Fetch a player's bowling stats by season.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per season
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const getBowlerBySeason = (id: string, filters?: F) =>
  fetchApi<{ by_season: any[] }>(`/api/v1/bowlers/${id}/by-season`, filters as Record<string, string>)
/**
 * Fetch how a player takes wickets: by kind, by phase and by batter.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the wicket analysis
 */
export const getBowlerWickets = (id: string, filters?: F) =>
  fetchApi<WicketAnalysis>(`/api/v1/bowlers/${id}/wickets`, filters as Record<string, string>)
/**
 * Fetch the batters that a player has dismissed as a bowler.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the victims
 */
export const getBowlerVictims = (id: string, filters?: F) =>
  fetchApi<{ victims: import('./types').BowlingVictim[] }>(`/api/v1/bowlers/${id}/victims`, filters as Record<string, string>)
/**
 * Fetch the per-innings distribution dossier of a player's bowling.
 * @param id the player's person id
 * @param filters the FilterBar filters, `min_balls`, and `as_of_date` (YYYY-MM-DD) to fix the form windows
 * @returns the bowling distribution
 */
export const getBowlerDistribution = (id: string, filters?: F & { min_balls?: number; as_of_date?: string }) =>
  fetchApi<import('./types').BowlerDistribution>(`/api/v1/bowlers/${id}/distribution`, filters as Record<string, string>)

// Fielding
/**
 * Fetch the top fielders.
 * @param filters the FilterBar filters, and `limit`
 * @returns the leader lists
 */
export const getFieldingLeaders = (filters?: F & { limit?: number }) =>
  fetchApi<import('./types').FieldingLeaders>(`/api/v1/fielders/leaders`, filters as Record<string, string>)
/**
 * Fetch a player's fielding summary.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the fielding summary
 */
export const getFielderSummary = (id: string, filters?: F) =>
  fetchApi<import('./types').FieldingSummary>(`/api/v1/fielders/${id}/summary`, filters as Record<string, string>)
/**
 * Fetch a player's fielding record lists.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `limit`, the length of each list
 * @returns the record lists
 */
export const getFielderRecords = (id: string, filters?: F & { limit?: number }) =>
  fetchApi<import('./types').FielderRecords>(`/api/v1/fielders/${id}/records`, filters as Record<string, string>)
/**
 * Fetch a player's fielding dismissals by season.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getFielderBySeason = (id: string, filters?: F) =>
  fetchApi<{ by_season: import('./types').FieldingSeason[] }>(`/api/v1/fielders/${id}/by-season`, filters as Record<string, string>)
/**
 * Fetch a player's fielding dismissals in the powerplay, middle and death overs.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getFielderByPhase = (id: string, filters?: F) =>
  fetchApi<{ by_phase: import('./types').FieldingPhase[] }>(`/api/v1/fielders/${id}/by-phase`, filters as Record<string, string>)
/**
 * Fetch a player's fielding dismissals in each over.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per over
 */
export const getFielderByOver = (id: string, filters?: F) =>
  fetchApi<{ by_over: import('./types').FieldingByOverEntry[] }>(`/api/v1/fielders/${id}/by-over`, filters as Record<string, string>)
/**
 * Fetch a player's fielding dismissals by kind: catches, stumpings, run-outs.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the total and the count of each kind
 */
export const getFielderDismissalTypes = (id: string, filters?: F) =>
  fetchApi<{ total: number; by_kind: Record<string, number> }>(`/api/v1/fielders/${id}/dismissal-types`, filters as Record<string, string>)
/**
 * Fetch the batters that a player has dismissed as a fielder.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `limit`
 * @returns the victims
 */
export const getFielderVictims = (id: string, filters?: F & { limit?: number }) =>
  fetchApi<{ victims: import('./types').FieldingVictim[] }>(`/api/v1/fielders/${id}/victims`, filters as Record<string, string>)
/**
 * Fetch a page of a player's fielding innings.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `limit` and `offset` for paging
 * @returns the innings on this page and the total count
 */
export const getFielderInnings = (id: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ innings: import('./types').FieldingInnings[]; total: number }>(`/api/v1/fielders/${id}/by-innings`, filters as Record<string, string>)
/**
 * Fetch the per-innings distribution dossier of a player's fielding.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `as_of_date` (YYYY-MM-DD) to fix the form windows
 * @returns the fielding distribution
 */
export const getFielderDistribution = (id: string, filters?: F & { as_of_date?: string }) =>
  fetchApi<import('./types').FielderDistribution>(`/api/v1/fielders/${id}/distribution`, filters as Record<string, string>)

// Composed player overview — four summary endpoints in parallel.
// `.catch(() => null)` per sub-fetch so a 404 on one discipline
// (specialist batter → no bowling row) doesn't blow up the whole
// profile. The /players page expects nulls where disciplines are
// missing; it hides those rows.
/**
 * Fetch a player's batting, bowling, fielding and keeping summaries at once.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the four summaries; each is null when its request fails
 */
export const getPlayerProfile = async (id: string, filters?: F) => {
  const [batting, bowling, fielding, keeping] = await Promise.all([
    getBatterSummary(id, filters).catch(() => null),
    getBowlerSummary(id, filters).catch(() => null),
    getFielderSummary(id, filters).catch(() => null),
    getFielderKeepingSummary(id, filters).catch(() => null),
  ])
  return { batting, bowling, fielding, keeping } as import('./types').PlayerProfile
}

// Teams the player has appeared for at the active scope, with per-team
// matches / runs / wickets / catches. Backs the "teams played for"
// strip at the top of the player profile.
/**
 * Fetch the teams a player has played for in scope, with matches, runs, wickets and catches.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per team
 */
export const getPlayerTeams = (id: string, filters?: F) =>
  fetchApi<{ teams: import('./types').PlayerTeamTotals[] }>(`/api/v1/players/${id}/teams`, filters as Record<string, string>)

// Teams the player has faced (with match counts) — the menu for the
// player-page "Versus" opponent filter. Narrows to the player's spell
// when filter_team is pinned; drops filter_opponent so the active
// selection doesn't collapse its own menu.
/**
 * Fetch the teams a player has faced, for the Versus filter.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the opponents and their match counts
 */
export const getPlayerOpponents = (id: string, filters?: F) =>
  fetchApi<{ opponents: import('./types').PlayerOpponentTotals[] }>(`/api/v1/players/${id}/opponents`, filters as Record<string, string>)

// Player-POV match-result counts (own-team won/lost/tied) for the
// player-page ResultFilter pills, plus toss-outcome counts (toss_won /
// toss_lost, no tied bucket) for the TossFilter pills. Aux-stripped
// breakdown at scope.
/**
 * Fetch the results and tosses of a player's teams, for the result and toss pills.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the counts of matches, wins, losses, ties, no results, tosses won and tosses lost
 */
export const getPlayerResultCounts = (id: string, filters?: F) =>
  fetchApi<{
    matches: number; wins: number; losses: number; ties: number; no_results: number
    toss_won: number; toss_lost: number
  }>(
    `/api/v1/players/${id}/result-counts`, filters as Record<string, string>)

// Keeping (Tier 2 fielding)
/**
 * Fetch a player's wicket-keeping summary.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns the keeping summary
 */
export const getFielderKeepingSummary = (id: string, filters?: F) =>
  fetchApi<import('./types').KeepingSummary>(`/api/v1/fielders/${id}/keeping/summary`, filters as Record<string, string>)
/**
 * Fetch a player's wicket-keeping stats by season.
 * @param id the player's person id
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getFielderKeepingBySeason = (id: string, filters?: F) =>
  fetchApi<{ by_season: import('./types').KeepingSeason[] }>(`/api/v1/fielders/${id}/keeping/by-season`, filters as Record<string, string>)
/**
 * Fetch a page of the innings a player kept wicket in.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `limit` and `offset` for paging
 * @returns the innings on this page and the total count
 */
export const getFielderKeepingInnings = (id: string, filters?: F & { limit?: number; offset?: number }) =>
  fetchApi<{ innings: import('./types').KeepingInnings[]; total: number }>(`/api/v1/fielders/${id}/keeping/by-innings`, filters as Record<string, string>)
/**
 * Fetch the innings where the keeper could be this player or another, with the other candidates.
 * @param id the player's person id
 * @param filters the FilterBar filters, and `limit`
 * @returns the innings and the total count
 */
export const getFielderKeepingAmbiguous = (id: string, filters?: F & { limit?: number }) =>
  fetchApi<{ innings: import('./types').KeepingAmbiguousInnings[]; total: number }>(`/api/v1/fielders/${id}/keeping/ambiguous`, filters as Record<string, string>)

// Matches
/**
 * Fetch a page of matches.
 * @param filters the FilterBar filters, `team`, `player_id`, and `limit` and `offset` for paging
 * @returns the matches on this page and the total count
 */
export const getMatches = (filters?: F & { team?: string; player_id?: string; limit?: number; offset?: number }) =>
  fetchApi<{ matches: MatchListItem[]; total: number }>('/api/v1/matches', filters as Record<string, string>)
/**
 * Fetch the scorecard of a match.
 * @param matchId the match id
 * @returns the scorecard
 */
export const getMatchScorecard = (matchId: number) =>
  fetchApi<Scorecard>(`/api/v1/matches/${matchId}/scorecard`)
/**
 * Fetch every ball of a match, for the innings grid chart.
 * @param matchId the match id
 * @returns the deliveries of each innings
 */
export const getInningsGrid = (matchId: number) =>
  fetchApi<InningsGridResponse>(`/api/v1/matches/${matchId}/innings-grid`)

// Head to Head
/**
 * Fetch the record of one batter against one bowler.
 * @param batterId the batter's person id
 * @param bowlerId the bowler's person id
 * @param filters the FilterBar filters, and `series_type`
 * @returns the head-to-head record
 */
export const getHeadToHead = (
  batterId: string, bowlerId: string,
  filters?: F & { series_type?: string },
) =>
  fetchApi<HeadToHeadResponse>(`/api/v1/head-to-head/${batterId}/${bowlerId}`, filters as Record<string, string>)

// Team stats — batting / bowling / fielding / partnerships
const te = encodeURIComponent

/**
 * Fetch a team's top-line batting stats.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the batting summary
 */
export const getTeamBattingSummary = (team: string, filters?: F) =>
  fetchApi<import('./types').TeamBattingSummary>(`/api/v1/teams/${te(team)}/batting/summary`, filters as Record<string, string>)
/**
 * Fetch a team's batting stats by season.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getTeamBattingBySeason = (team: string, filters?: F) =>
  fetchApi<{ seasons: import('./types').TeamBattingSeason[] }>(`/api/v1/teams/${te(team)}/batting/by-season`, filters as Record<string, string>)
/**
 * Fetch a team's batting stats in the powerplay, middle and death overs.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getTeamBattingByPhase = (team: string, filters?: F) =>
  fetchApi<{ phases: import('./types').TeamBattingPhase[] }>(`/api/v1/teams/${te(team)}/batting/by-phase`, filters as Record<string, string>)
/**
 * Fetch a team's batting stats when it bats first and second.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one row per innings
 */
export const getTeamBattingByInning = (team: string, filters?: F) =>
  fetchApi<{ innings: import('./types').TeamBattingInning[] }>(`/api/v1/teams/${te(team)}/batting/by-inning`, filters as Record<string, string>)
/**
 * Fetch a team's top batters.
 * @param team the team name
 * @param filters the FilterBar filters, and `limit`
 * @returns the top batters
 */
export const getTeamTopBatters = (team: string, filters?: F & { limit?: number }) =>
  fetchApi<{ top_batters: import('./types').TeamTopBatter[] }>(`/api/v1/teams/${te(team)}/batting/top-batters`, filters as Record<string, string>)
/**
 * Fetch a team's batting by phase and season, for the heatmap.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the phase by season matrix
 */
export const getTeamBattingPhaseSeasonHeatmap = (team: string, filters?: F) =>
  fetchApi<import('./types').BattingPhaseSeasonHeatmap>(`/api/v1/teams/${te(team)}/batting/phase-season-heatmap`, filters as Record<string, string>)
/**
 * Fetch the per-innings distribution dossier of a team's batting.
 * @param team the team name
 * @param filters the FilterBar filters, and `as_of_date` (YYYY-MM-DD) to fix the form windows
 * @returns the batting distribution
 */
export const getTeamBattingDistribution = (team: string, filters?: F & { as_of_date?: string }) =>
  fetchApi<import('./types').TeamBattingDistribution>(`/api/v1/teams/${te(team)}/batting/distribution`, filters as Record<string, string>)

/**
 * Fetch a team's top-line bowling stats.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the bowling summary
 */
export const getTeamBowlingSummary = (team: string, filters?: F) =>
  fetchApi<import('./types').TeamBowlingSummary>(`/api/v1/teams/${te(team)}/bowling/summary`, filters as Record<string, string>)
/**
 * Fetch a team's bowling stats by season.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getTeamBowlingBySeason = (team: string, filters?: F) =>
  fetchApi<{ seasons: import('./types').TeamBowlingSeason[] }>(`/api/v1/teams/${te(team)}/bowling/by-season`, filters as Record<string, string>)
/**
 * Fetch a team's bowling stats in the powerplay, middle and death overs.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getTeamBowlingByPhase = (team: string, filters?: F) =>
  fetchApi<{ phases: import('./types').TeamBowlingPhase[] }>(`/api/v1/teams/${te(team)}/bowling/by-phase`, filters as Record<string, string>)
/**
 * Fetch a team's bowling stats when it bowls first and second.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one row per innings
 */
export const getTeamBowlingByInning = (team: string, filters?: F) =>
  fetchApi<{ innings: import('./types').TeamBowlingInning[] }>(`/api/v1/teams/${te(team)}/bowling/by-inning`, filters as Record<string, string>)
/**
 * Fetch a team's top bowlers.
 * @param team the team name
 * @param filters the FilterBar filters, and `limit`
 * @returns the top bowlers
 */
export const getTeamTopBowlers = (team: string, filters?: F & { limit?: number }) =>
  fetchApi<{ top_bowlers: import('./types').TeamTopBowler[] }>(`/api/v1/teams/${te(team)}/bowling/top-bowlers`, filters as Record<string, string>)
/**
 * Fetch a team's bowling by phase and season, for the heatmap.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the phase by season matrix
 */
export const getTeamBowlingPhaseSeasonHeatmap = (team: string, filters?: F) =>
  fetchApi<import('./types').BowlingPhaseSeasonHeatmap>(`/api/v1/teams/${te(team)}/bowling/phase-season-heatmap`, filters as Record<string, string>)
/**
 * Fetch the per-innings distribution dossier of a team's bowling.
 * @param team the team name
 * @param filters the FilterBar filters, and `as_of_date` (YYYY-MM-DD) to fix the form windows
 * @returns the bowling distribution
 */
export const getTeamBowlingDistribution = (team: string, filters?: F & { as_of_date?: string }) =>
  fetchApi<import('./types').TeamBowlingDistribution>(`/api/v1/teams/${te(team)}/bowling/distribution`, filters as Record<string, string>)

/**
 * Fetch a team's top-line fielding stats.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the fielding summary
 */
export const getTeamFieldingSummary = (team: string, filters?: F) =>
  fetchApi<import('./types').TeamFieldingSummary>(`/api/v1/teams/${te(team)}/fielding/summary`, filters as Record<string, string>)
/**
 * Fetch a team's fielding stats by season.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getTeamFieldingBySeason = (team: string, filters?: F) =>
  fetchApi<{ seasons: import('./types').TeamFieldingSeason[] }>(`/api/v1/teams/${te(team)}/fielding/by-season`, filters as Record<string, string>)
/**
 * Fetch a team's fielding stats when it fields first and second.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns one row per innings
 */
export const getTeamFieldingByInning = (team: string, filters?: F) =>
  fetchApi<{ innings: import('./types').TeamFieldingInning[] }>(`/api/v1/teams/${te(team)}/fielding/by-inning`, filters as Record<string, string>)
/**
 * Fetch a team's top fielders.
 * @param team the team name
 * @param filters the FilterBar filters, and `limit`
 * @returns the top fielders
 */
export const getTeamTopFielders = (team: string, filters?: F & { limit?: number }) =>
  fetchApi<{ top_fielders: import('./types').TeamTopFielder[] }>(`/api/v1/teams/${te(team)}/fielding/top-fielders`, filters as Record<string, string>)
/**
 * Fetch the per-innings distribution dossier of a team's fielding.
 * @param team the team name
 * @param filters the FilterBar filters, and `as_of_date` (YYYY-MM-DD) to fix the form windows
 * @returns the fielding distribution
 */
export const getTeamFieldingDistribution = (team: string, filters?: F & { as_of_date?: string }) =>
  fetchApi<import('./types').TeamFieldingDistribution>(`/api/v1/teams/${te(team)}/fielding/distribution`, filters as Record<string, string>)

/**
 * Fetch a team's partnership stats for each wicket.
 * @param team the team name
 * @param filters the FilterBar filters, and `side`: `batting` for the team's partnerships, `bowling` for those against it
 * @returns the team, the side and one row per wicket
 */
export const getTeamPartnershipsByWicket = (team: string, filters?: F & { side?: 'batting' | 'bowling' }) =>
  fetchApi<{ team: string; side: 'batting' | 'bowling'; by_wicket: import('./types').PartnershipByWicket[] }>(
    `/api/v1/teams/${te(team)}/partnerships/by-wicket`, filters as Record<string, string>)
/**
 * Fetch a team's partnership stats in the first and second innings.
 * @param team the team name
 * @param filters the FilterBar filters, and `side`: `batting` or `bowling`
 * @returns the team, the side and one row per innings
 */
export const getTeamPartnershipsByInning = (team: string, filters?: F & { side?: 'batting' | 'bowling' }) =>
  fetchApi<{ team: string; side: 'batting' | 'bowling'; innings: import('./types').TeamPartnershipsInning[] }>(
    `/api/v1/teams/${te(team)}/partnerships/by-inning`, filters as Record<string, string>)
/**
 * Fetch the most prolific pairs at each wicket, by runs together.
 * @param team the team name
 * @param filters the FilterBar filters, `side`, `min_n` and `top_n`
 * @returns the best pairs
 */
export const getTeamPartnershipsBestPairs = (team: string, filters?: F & { side?: 'batting' | 'bowling'; min_n?: number; top_n?: number }) =>
  fetchApi<import('./types').PartnershipBestPairsResponse>(
    `/api/v1/teams/${te(team)}/partnerships/best-pairs`, filters as Record<string, string>)
/**
 * Fetch a team's average partnership by wicket and season, for the heatmap.
 * @param team the team name
 * @param filters the FilterBar filters, and `side`: `batting` or `bowling`
 * @returns the wicket by season matrix
 */
export const getTeamPartnershipsHeatmap = (team: string, filters?: F & { side?: 'batting' | 'bowling' }) =>
  fetchApi<import('./types').PartnershipHeatmap>(`/api/v1/teams/${te(team)}/partnerships/heatmap`, filters as Record<string, string>)
/**
 * Fetch a team's highest partnerships.
 * @param team the team name
 * @param filters the FilterBar filters, `side`, and `limit`
 * @returns the team, the side and the partnerships
 */
export const getTeamPartnershipsTop = (team: string, filters?: F & { side?: 'batting' | 'bowling'; limit?: number }) =>
  fetchApi<{ team: string; side: 'batting' | 'bowling'; partnerships: import('./types').PartnershipTopEntry[] }>(
    `/api/v1/teams/${te(team)}/partnerships/top`, filters as Record<string, string>)
/**
 * Fetch a team's partnership counts, highest stand and top pair.
 * @param team the team name
 * @param filters the FilterBar filters, and `side`: `batting` or `bowling`
 * @returns the partnership summary
 */
export const getTeamPartnershipsSummary = (team: string, filters?: F & { side?: 'batting' | 'bowling' }) =>
  fetchApi<import('./types').TeamPartnershipsSummary>(
    `/api/v1/teams/${te(team)}/partnerships/summary`, filters as Record<string, string>)

/**
 * Fetch a team's partnership stats by season.
 * @param team the team name
 * @param filters the FilterBar filters, and `side`: `batting` or `bowling`
 * @returns the team, the side and one row per season
 */
export const getTeamPartnershipsBySeason = (team: string, filters?: F & { side?: 'batting' | 'bowling' }) =>
  fetchApi<{ team: string; side: 'batting' | 'bowling'; by_season: import('./types').TeamPartnershipsSeason[] }>(
    `/api/v1/teams/${te(team)}/partnerships/by-season`, filters as Record<string, string>)

// Composed team overview — summary endpoints + deep-lens (by-phase /
// by-wicket / by-season) endpoints in parallel. Mirrors
// getPlayerProfile: `.catch(() => null)` per sub-fetch so a scope that
// yields zero results in one discipline (e.g. a defunct team with no
// recent partnerships) doesn't blow up the whole column. Consumed by
// TeamCompareGrid which hides rows where every column is null.
//
// 12 fetches per team-column. Two bundles' worth of data so the grid
// can render summary + phase bands + partnership-by-wicket + season
// trajectory without a second composer round-trip.
/**
 * Fetch the summaries, phases, wickets and seasons of a team at once, for the Compare grid.
 * @param team the team name
 * @param filters the FilterBar filters
 * @returns the twelve parts; each is null when its request fails
 */
export const getTeamProfile = async (team: string, filters?: F) => {
  const [
    summary, batting, bowling, fielding, partnerships,
    batting_by_phase, bowling_by_phase, partnerships_by_wicket,
    batting_by_season, bowling_by_season, fielding_by_season, partnerships_by_season,
  ] = await Promise.all([
    getTeamSummary(team, filters).catch(() => null),
    getTeamBattingSummary(team, filters).catch(() => null),
    getTeamBowlingSummary(team, filters).catch(() => null),
    getTeamFieldingSummary(team, filters).catch(() => null),
    getTeamPartnershipsSummary(team, filters).catch(() => null),
    getTeamBattingByPhase(team, filters).catch(() => null),
    getTeamBowlingByPhase(team, filters).catch(() => null),
    getTeamPartnershipsByWicket(team, filters).catch(() => null),
    getTeamBattingBySeason(team, filters).catch(() => null),
    getTeamBowlingBySeason(team, filters).catch(() => null),
    getTeamFieldingBySeason(team, filters).catch(() => null),
    getTeamPartnershipsBySeason(team, filters).catch(() => null),
  ])
  return {
    summary, batting, bowling, fielding, partnerships,
    batting_by_phase, bowling_by_phase, partnerships_by_wicket,
    batting_by_season, bowling_by_season, fielding_by_season, partnerships_by_season,
  } as import('./types').TeamProfile
}

// ─── Scope averages — pool-weighted league baselines ─────────────────
// The "average team" counterpart to getTeam* — same FilterBar scope,
// no team filter. Drives the average column on the Teams > Compare tab
// + phase-band / per-wicket / season-trajectory expansions.
// See internal_docs/spec-team-compare-average.md.

/**
 * Fetch the league's top-line record at the filter scope.
 * @param filters the FilterBar filters
 * @returns the scope summary
 */
export const getScopeSummary = (filters?: F) =>
  fetchApi<import('./types').ScopeSummary>('/api/v1/scope/averages/summary', filters as Record<string, string>)
/**
 * Fetch the league's batting stats at the filter scope.
 * @param filters the FilterBar filters
 * @returns the batting summary
 */
export const getScopeBattingSummary = (filters?: F) =>
  fetchApi<import('./types').ScopeBattingSummary>('/api/v1/scope/averages/batting/summary', filters as Record<string, string>)
/**
 * Fetch the league's batting stats in each phase.
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getScopeBattingByPhase = (filters?: F) =>
  fetchApi<{ by_phase: import('./types').ScopeBattingPhaseFlat[] }>('/api/v1/scope/averages/batting/by-phase', filters as Record<string, string>)
/**
 * Fetch the league's batting stats by season.
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getScopeBattingBySeason = (filters?: F) =>
  fetchApi<{ by_season: import('./types').ScopeBattingSeason[] }>('/api/v1/scope/averages/batting/by-season', filters as Record<string, string>)
/**
 * Fetch the league's bowling stats at the filter scope.
 * @param filters the FilterBar filters
 * @returns the bowling summary
 */
export const getScopeBowlingSummary = (filters?: F) =>
  fetchApi<import('./types').ScopeBowlingSummary>('/api/v1/scope/averages/bowling/summary', filters as Record<string, string>)
/**
 * Fetch the league's bowling stats in each phase.
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getScopeBowlingByPhase = (filters?: F) =>
  fetchApi<{ by_phase: import('./types').ScopeBowlingPhaseFlat[] }>('/api/v1/scope/averages/bowling/by-phase', filters as Record<string, string>)
/**
 * Fetch the league's bowling stats by season.
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getScopeBowlingBySeason = (filters?: F) =>
  fetchApi<{ by_season: import('./types').ScopeBowlingSeason[] }>('/api/v1/scope/averages/bowling/by-season', filters as Record<string, string>)
/**
 * Fetch the league's fielding stats at the filter scope.
 * @param filters the FilterBar filters
 * @returns the fielding summary
 */
export const getScopeFieldingSummary = (filters?: F) =>
  fetchApi<import('./types').ScopeFieldingSummary>('/api/v1/scope/averages/fielding/summary', filters as Record<string, string>)
/**
 * Fetch the league's fielding stats by season.
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getScopeFieldingBySeason = (filters?: F) =>
  fetchApi<{ by_season: import('./types').ScopeFieldingSeason[] }>('/api/v1/scope/averages/fielding/by-season', filters as Record<string, string>)
// ─── Player-cohort by-season + by-phase (spec-player-baseline-parity.md §3.2) ───
// person_id is required — the endpoint derives the cohort mix
// server-side from playerscopestats_{position,over,fielding_position}
// joined on (person_id, scope_key). Per-season and per-phase responses
// share a single FilterParams scope so the cohort baseline narrows
// with every FilterBar / aux click identical to chip ↔ chart symmetry.

const playerScope = <T>(path: string, personId: string, filters?: F) =>
  fetchApi<T>(path, { ...(filters as Record<string, string>), person_id: personId })

/**
 * Fetch the batting cohort of a player by season, the pool weighted by the player's batting positions.
 * @param personId the player's person id
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getScopePlayersBattingBySeason = (personId: string, filters?: F) =>
  playerScope<{ by_season: import('./types').ScopePlayerBattingSeason[] }>(
    '/api/v1/scope/averages/players/batting/by-season', personId, filters)
/**
 * Fetch the batting cohort of a player in each phase.
 * @param personId the player's person id
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getScopePlayersBattingByPhase = (personId: string, filters?: F) =>
  playerScope<{ by_phase: import('./types').ScopePlayerBattingPhase[] }>(
    '/api/v1/scope/averages/players/batting/by-phase', personId, filters)
// Tier 4 of spec-apples-to-apples-baselines.md — per-over batting
// cohort. Mirror of bowling's /by-over: takes person_id, derives ball
// mix server-side, returns a 20-element by_over array.
/**
 * Fetch the batting cohort of a player in each over, weighted by the player's ball mix.
 * @param personId the player's person id
 * @param filters the FilterBar filters
 * @returns 20 rows, one per over, and the cohort's ball mix
 */
export const getScopePlayersBattingByOver = (personId: string, filters?: F) =>
  playerScope<{
    by_over: {
      over: number; n_balls: number; n_players: number; n_innings: number;
      threshold: number; below_support: boolean;
      strike_rate: number | null; dot_pct: number | null;
      boundary_pct: number | null; balls_per_four: number | null;
      balls_per_boundary: number | null; runs_per_innings: number | null;
      dismissals: number;
    }[];
    cohort: { match_dimension: string; ball_mix: number[]; n_players: number; n_balls_total: number };
  }>('/api/v1/scope/averages/players/batting/by-over', personId, filters)
/**
 * Fetch the bowling cohort of a player by season.
 * @param personId the player's person id
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getScopePlayersBowlingBySeason = (personId: string, filters?: F) =>
  playerScope<{ by_season: import('./types').ScopePlayerBowlingSeason[] }>(
    '/api/v1/scope/averages/players/bowling/by-season', personId, filters)
// spec-rate-vs-volume-audit C3: cohort econ-by-over overlay on the
// /bowling By Over tab. Takes the player's over_mix (derived from
// summary.cohort.over_mix) so the cohort baseline is fold-weighted
// in the same way the /summary chip path is.
/**
 * Fetch the bowling cohort's economy, strike rate and dot percentage in each over, for a given over mix.
 * @param overMix the bowler's share of balls in each of overs 1 to 20, summing to 1
 * @param filters the FilterBar filters
 * @returns one row per over
 */
export const getScopePlayersBowlingSummary = (overMix: number[], filters?: F) =>
  fetchApi<{
    by_over: { over: number; economy: number | null; strike_rate: number | null; dot_pct: number | null }[]
  }>('/api/v1/scope/averages/players/bowling/summary', {
    ...(filters as Record<string, string>),
    over_mix: overMix.map(m => m.toFixed(6)).join(','),
  })
/**
 * Fetch the bowling cohort of a player in each phase.
 * @param personId the player's person id
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getScopePlayersBowlingByPhase = (personId: string, filters?: F) =>
  playerScope<{ by_phase: import('./types').ScopePlayerBowlingPhase[] }>(
    '/api/v1/scope/averages/players/bowling/by-phase', personId, filters)
/**
 * Fetch the fielding cohort of a player by season.
 * @param personId the player's person id
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getScopePlayersFieldingBySeason = (personId: string, filters?: F) =>
  playerScope<{ by_season: import('./types').ScopePlayerFieldingSeason[] }>(
    '/api/v1/scope/averages/players/fielding/by-season', personId, filters)
/**
 * Fetch the fielding cohort of a player in each phase.
 * @param personId the player's person id
 * @param filters the FilterBar filters
 * @returns one row per phase
 */
export const getScopePlayersFieldingByPhase = (personId: string, filters?: F) =>
  playerScope<{ by_phase: import('./types').ScopePlayerFieldingPhase[] }>(
    '/api/v1/scope/averages/players/fielding/by-phase', personId, filters)

/**
 * Fetch the league's partnership summary at the filter scope.
 * @param filters the FilterBar filters
 * @returns the partnership summary
 */
export const getScopePartnershipsSummary = (filters?: F) =>
  fetchApi<import('./types').ScopePartnershipsSummary>('/api/v1/scope/averages/partnerships/summary', filters as Record<string, string>)
/**
 * Fetch the league's partnership stats for each wicket.
 * @param filters the FilterBar filters
 * @returns one row per wicket
 */
export const getScopePartnershipsByWicket = (filters?: F) =>
  fetchApi<{ by_wicket: import('./types').ScopePartnershipByWicket[] }>('/api/v1/scope/averages/partnerships/by-wicket', filters as Record<string, string>)
/**
 * Fetch the league's partnership stats by season.
 * @param filters the FilterBar filters
 * @returns one row per season
 */
export const getScopePartnershipsBySeason = (filters?: F) =>
  fetchApi<{ by_season: import('./types').ScopePartnershipsSeason[] }>('/api/v1/scope/averages/partnerships/by-season', filters as Record<string, string>)

// Parallel composer mirroring getTeamProfile so the avg slot in
// TeamCompareGrid uses the same fetch shape as a team slot.
// 12 fetches — same shape as getTeamProfile so the grid can drive
// both with identical band logic.
/**
 * Fetch the league's twelve parts at once, in the shape of `getTeamProfile`, for the average column.
 * @param filters the FilterBar filters
 * @returns the twelve parts; each is null when its request fails
 */
export const getScopeAverageProfile = async (filters?: F) => {
  const [
    summary, batting, bowling, fielding, partnerships,
    batting_by_phase, bowling_by_phase, partnerships_by_wicket,
    batting_by_season, bowling_by_season, fielding_by_season, partnerships_by_season,
  ] = await Promise.all([
    getScopeSummary(filters).catch(() => null),
    getScopeBattingSummary(filters).catch(() => null),
    getScopeBowlingSummary(filters).catch(() => null),
    getScopeFieldingSummary(filters).catch(() => null),
    getScopePartnershipsSummary(filters).catch(() => null),
    getScopeBattingByPhase(filters).catch(() => null),
    getScopeBowlingByPhase(filters).catch(() => null),
    getScopePartnershipsByWicket(filters).catch(() => null),
    getScopeBattingBySeason(filters).catch(() => null),
    getScopeBowlingBySeason(filters).catch(() => null),
    getScopeFieldingBySeason(filters).catch(() => null),
    getScopePartnershipsBySeason(filters).catch(() => null),
  ])
  return {
    summary, batting, bowling, fielding, partnerships,
    batting_by_phase, bowling_by_phase, partnerships_by_wicket,
    batting_by_season, bowling_by_season, fielding_by_season, partnerships_by_season,
  } as import('./types').ScopeAverageProfile
}

// Tournaments / match-set dossier — `tournament` is optional; omit for
// cross-tournament rivalry views (filter_team + filter_opponent in filters).
type TF = F & { series_type?: string; filter_team?: string; filter_opponent?: string }
const tparams = (t: string | null | undefined, f?: TF) => {
  const out: Record<string, string> = { ...(f as Record<string, string>) }
  if (t) out.tournament = t
  return out
}

/**
 * Fetch the directory for the `/series` landing page: tournaments and rivalries.
 * @param filters the FilterBar filters
 * @returns the sections of the landing page
 */
export const getTournamentsLanding = (filters?: F) =>
  fetchApi<import('./types').TournamentsLanding>('/api/v1/series/landing', filters as Record<string, string>)
/**
 * Fetch the headline numbers of a tournament or any match set.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `series_type`, and `filter_team` and `filter_opponent` for a rivalry
 * @returns the summary
 */
export const getTournamentSummary = (tournament: string | null, filters?: TF) =>
  fetchApi<import('./types').TournamentSummary>('/api/v1/series/summary', tparams(tournament, filters))
/**
 * Fetch each edition of a tournament: champion, runner-up, top players and rates.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `series_type`, `filter_team` and `filter_opponent`
 * @returns the tournament and one row per season
 */
export const getTournamentBySeason = (tournament: string | null, filters?: TF) =>
  fetchApi<{ tournament: string; seasons: import('./types').TournamentSeason[] }>(
    '/api/v1/series/by-season', tparams(tournament, filters))
/**
 * Fetch the league-stage points table of one season of a tournament.
 * @param tournament the tournament
 * @param filters the filters; `season_from` must equal `season_to`
 * @returns the points tables
 */
export const getTournamentPointsTable = (tournament: string, filters?: TF) =>
  fetchApi<import('./types').TournamentPointsTableResponse>(
    '/api/v1/series/points-table', { ...(filters as Record<string, string>), tournament })
/**
 * Fetch the record lists of a tournament or match set.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `series_type`, `filter_team`, `filter_opponent` and `limit`
 * @returns the record lists
 */
export const getTournamentRecords = (tournament: string | null, filters?: TF & { limit?: number }) =>
  fetchApi<import('./types').TournamentRecords>(
    '/api/v1/series/records', tparams(tournament, filters))
/**
 * Fetch the rivalries not on the landing page, with at least 5 bilateral matches.
 * @param filters the FilterBar filters, and `gender`
 * @returns the rivalries and the match threshold
 */
export const getTournamentOtherRivalries = (filters?: F & { gender?: string }) =>
  fetchApi<{ rivalries: import('./types').RivalryEntry[]; threshold: number }>(
    '/api/v1/series/other-rivalries', filters as Record<string, string>)
/**
 * Fetch the older bilateral rivalry dossier of two teams.
 * @param team1 the first team
 * @param team2 the second team
 * @param filters the FilterBar filters
 * @returns the rivalry summary
 */
export const getRivalrySummary = (team1: string, team2: string, filters?: F) =>
  fetchApi<import('./types').RivalrySummary>(
    '/api/v1/rivalries/summary', { ...(filters as Record<string, string>), team1, team2 })

// Variant-aware leader endpoints for tournament dossiers (canonical → IN variants)
/**
 * Fetch the top batters of a tournament, over all its name variants.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `series_type`, `filter_team`, `filter_opponent` and `limit`
 * @returns the leader lists
 */
export const getTournamentBattersLeaders = (tournament: string | null, filters?: TF & { limit?: number }) =>
  fetchApi<import('./types').BattingLeaders>(
    '/api/v1/series/batters-leaders', tparams(tournament, filters))
/**
 * Fetch the batting stats of one player in a tournament or match set.
 * @param tournament the tournament; null for all tournaments in scope
 * @param personId the player's person id
 * @param filters the filters, `series_type`, `filter_team` and `filter_opponent`
 * @returns the player's row, or null when the player did not bat in scope
 */
export const getTournamentBatterScopeStats = (
  tournament: string | null, personId: string, filters?: TF,
) =>
  fetchApi<{ entry: import('./types').BattingLeaderEntry | null }>(
    '/api/v1/series/batter-scope-stats',
    { ...tparams(tournament, filters), person_id: personId },
  )
/**
 * Fetch the top bowlers of a tournament, over all its name variants.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `series_type`, `filter_team`, `filter_opponent` and `limit`
 * @returns the leader lists
 */
export const getTournamentBowlersLeaders = (tournament: string | null, filters?: TF & { limit?: number }) =>
  fetchApi<import('./types').BowlingLeaders>(
    '/api/v1/series/bowlers-leaders', tparams(tournament, filters))
/**
 * Fetch the bowling stats of one player in a tournament or match set.
 * @param tournament the tournament; null for all tournaments in scope
 * @param personId the player's person id
 * @param filters the filters, `series_type`, `filter_team` and `filter_opponent`
 * @returns the player's row, or null when the player did not bowl in scope
 */
export const getTournamentBowlerScopeStats = (
  tournament: string | null, personId: string, filters?: TF,
) =>
  fetchApi<{ entry: import('./types').BowlingLeaderEntry | null }>(
    '/api/v1/series/bowler-scope-stats',
    { ...tparams(tournament, filters), person_id: personId },
  )
/**
 * Fetch the top fielders of a tournament, over all its name variants.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `series_type`, `filter_team`, `filter_opponent` and `limit`
 * @returns the leader lists
 */
export const getTournamentFieldersLeaders = (tournament: string | null, filters?: TF & { limit?: number }) =>
  fetchApi<import('./types').FieldingLeaders>(
    '/api/v1/series/fielders-leaders', tparams(tournament, filters))
/**
 * Fetch the fielding stats of one player in a tournament or match set.
 * @param tournament the tournament; null for all tournaments in scope
 * @param personId the player's person id
 * @param filters the filters, `series_type`, `filter_team` and `filter_opponent`
 * @returns the player's row; zeros when the player played but took no credit, null when not in scope
 */
export const getTournamentFielderScopeStats = (
  tournament: string | null, personId: string, filters?: TF,
) =>
  fetchApi<{ entry: import('./types').FieldingLeaderEntry | null }>(
    '/api/v1/series/fielder-scope-stats',
    { ...tparams(tournament, filters), person_id: personId },
  )

/**
 * Fetch the partnership stats for each wicket in a tournament or match set, with the best stand.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `filter_team`, and `side`: `batting` for the team's partnerships, `bowling` for those against it
 * @returns one row per wicket
 */
export const getTournamentPartnershipsByWicket = (
  tournament: string | null, filters?: TF & { side?: 'batting' | 'bowling' },
) => fetchApi<import('./types').TournamentPartnershipsByWicket>(
  '/api/v1/series/partnerships/by-wicket', tparams(tournament, filters))
/**
 * Fetch the highest partnerships in a tournament or match set.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `filter_team`, `side` and `limit`
 * @returns the partnerships
 */
export const getTournamentPartnershipsTop = (
  tournament: string | null, filters?: TF & { side?: 'batting' | 'bowling'; limit?: number },
) => fetchApi<import('./types').TournamentPartnershipsTop>(
  '/api/v1/series/partnerships/top', tparams(tournament, filters))
/**
 * Fetch the highest partnerships for each wicket in a tournament or match set.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `filter_team`, `side` and `per_wicket`, the length of each list
 * @returns ten lists, one per wicket
 */
export const getTournamentPartnershipsTopByWicket = (
  tournament: string | null, filters?: TF & { side?: 'batting' | 'bowling'; per_wicket?: number },
) => fetchApi<import('./types').TournamentPartnershipsTopByWicket>(
  '/api/v1/series/partnerships/top-by-wicket', tparams(tournament, filters))
/**
 * Fetch the average partnership by season and wicket in a tournament or match set.
 * @param tournament the tournament; null for all tournaments in scope
 * @param filters the filters, `filter_team` and `side`
 * @returns the season by wicket matrix
 */
export const getTournamentPartnershipsHeatmap = (
  tournament: string | null, filters?: TF & { side?: 'batting' | 'bowling' },
) => fetchApi<import('./types').TournamentPartnershipsHeatmap>(
  '/api/v1/series/partnerships/heatmap', tparams(tournament, filters))

// ─── League (above-tournament scope dossier) ─────────────────────────

// /league/* endpoints removed 2026-05-14 — they were parallel copies
// of /series/* that just dropped the tournament param. /series/summary
// at broad scope now returns top_teams_international + top_teams_club
// + tournament-bearing champions_by_season + all-time leaders, sourced
// from precomputed bucket-baseline tables for sub-second response.
