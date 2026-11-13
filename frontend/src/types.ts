/**
 * The shapes of the API's requests and responses, shared by `api.ts`, the pages and the components.
 * @packageDocumentation
 */

/** The filters that a page sends with its requests: the FilterBar fields, plus the page-local aux filters. */
export interface FilterParams {
  gender?: string // "male" or "female"; absent for both
  team_type?: string // "international" or "club"; absent for both
  tournament?: string // a canonical tournament name
  season_from?: string // the first season, as "2023" or "2023/24"
  season_to?: string // the last season, as "2023" or "2023/24"
  /** Player-page rivalry scope — match-level pair filter. Backend reads
   *  these as `filter_team` / `filter_opponent` query params. */
  filter_team?: string
  filter_opponent?: string // the other team of the rivalry pair, with `filter_team`
  /** Ambient venue filter — narrows every filter-consuming endpoint to
   *  a single canonical venue (e.g. "Wankhede Stadium, Mumbai"). Set
   *  via the FilterBar VenueSearch on any tab. */
  filter_venue?: string
  team?: string // a team to narrow to; not read from the URL by `useFilters`
  opponent?: string // an opponent to narrow to; not read from the URL by `useFilters`
  /** FilterBar field — the category of series: all (default),
   *  bilateral, icc or club; the legacy values bilateral_only and
   *  tournament_only are also accepted. In FILTER_KEYS, so it rides
   *  through scope-link URLs, and `useFilters` reads it from the URL.
   *  The backend reads it in FilterBarParams
   *  (api/filters.py::FilterBarParams). */
  series_type?: string
  /** Aux hint sent only by the Compare-tab avg slot's fetcher. Tells
   *  the backend's /scope/averages/* endpoints to narrow the universe
   *  to event_names where this team has appeared — so "RCB vs avg"
   *  means "RCB vs IPL avg", not "RCB vs all-club-cricket avg". Gated
   *  backend-side on (team is None AND no explicit tournament filter).
   *  Backed by ix_matchplayer_team for fast subquery. */
  scope_to_team?: string
  /** FilterBar narrowing — restricts the match pool to fixtures
   *  between two teams in a named class. Currently only
   *  `'full_member'` (= matches between two ICC full-member nations)
   *  is supported; expand as new classes are needed.
   *  Defensive backend gate: no-op when `team_type !== 'international'`
   *  (full-member status is an intl classification). FilterBar widget
   *  hides the pill on club / "All". Inherits down to compare slots
   *  via `useCompareSlots`; per-slot URL `compareN_team_class=...`
   *  overrides like every other overridable axis. */
  team_class?: string
  /** Chip-baseline alignment hint sent ONLY by the Compare-tab team
   *  slot's fetcher when a peer avg slot has team_class set. Tells
   *  the backend to apply that team_class to the league-side
   *  baseline computation INSIDE _league_aux only — team data is
   *  unaffected (Aus shows all 22 of its matches even when the
   *  league baseline is FM-only). Without this, chip's scope_avg
   *  numerically diverges from the avg col's displayed value. */
  chip_team_class?: string
  /** Page-local 1st/2nd-innings filter — string '0' (batting first)
   *  or '1' (batting second). NOT a FilterBar field (10-key ceiling
   *  stands); set by the page-level InningToggle on team/player
   *  Batting/Bowling/Fielding/Partnerships pages, OR per-slot via the
   *  Compare-tab SlotScopeEditor (compareN_inning URL param). Mirror
   *  of api/filters.py::AuxParams.inning. Spec:
   *  docs/internal/spec-inning-split.md. */
  inning?: string
  /** Match-outcome filter from path team's POV — 'won' / 'lost' /
   *  'tied' (last collapses true ties + no-results). AuxParam, set
   *  by the Splits Mosaic's marginals + cells + sub-rect clicks
   *  (`?result=won`). Only meaningful when subject team is bound.
   *  Mirror of api/filters.py::AuxParams.result. Spec:
   *  docs/internal/spec-splits-mosaic.md §1.1. */
  result?: string
  /** Toss-outcome filter from path team's POV — 'won' / 'lost'.
   *  AuxParam, set by the Splits Mosaic. Mirror of
   *  api/filters.py::AuxParams.toss_outcome. Spec:
   *  docs/internal/spec-splits-mosaic.md §1.1. */
  toss_outcome?: string
}

/** A tournament in the list from `/api/v1/tournaments`. */
export interface Tournament {
  event_name: string // the tournament's canonical name
  team_type: string // "international" or "club"
  gender: string // "male" or "female"
  matches: number // matches in scope
  seasons: string[] // the seasons it was played in
}

/** A team in the list from `/api/v1/teams`. */
export interface TeamInfo {
  name: string // the team's name
  matches: number // matches in scope
  team_type: string // "international" or "club"
  gender: string // "male" or "female"
}

/** A player in the search results from `/api/v1/players`. */
export interface PlayerSearchResult {
  id: string // the player's person id
  name: string // the display name
  unique_name: string // the name that tells apart players of the same name
  /** The count the results are ranked by: innings in the role (batting when no role); for fielders, matches in scope, or dismissals with no scope. */
  innings: number
}

/** Per-metric envelope on the 5 team-compare summary endpoints.
 *  See `api/metrics_metadata.py` for direction map. Spec-1 UI renders
 *  only `value`; the other fields are shipped for Spec-2 surfaces
 *  (player compare, leaderboard delta columns, H2H baseline).
 *  See `docs/internal/outlook-comparisons.md`. */
export interface MetricEnvelope {
  value: number | null // the metric's value; null when it cannot be computed
  scope_avg: number | null // the average of the same metric over the scope; null when there is none
  delta_pct: number | null // (value - scope_avg) / scope_avg × 100, to 1 decimal; null for a count, when a side is missing, or when `scope_avg` is 0
  direction: 'higher_better' | 'lower_better' | null // which way is better; null for a count
  sample_size: number | null // the sample behind the comparison, such as legal balls, matches or the cohort's innings; null when unknown
}

/** A team's record from `/api/v1/teams/{team}/summary`: results, toss, keepers and scope facts. */
export interface TeamSummary {
  team: string // the team's name
  matches: MetricEnvelope // matches played
  wins: MetricEnvelope // matches won
  losses: MetricEnvelope // matches lost
  ties: MetricEnvelope // matches tied
  no_results: MetricEnvelope // matches with no result
  win_pct: MetricEnvelope // wins as a percentage of matches
  toss_wins: MetricEnvelope // tosses won
  bat_first_wins: MetricEnvelope // wins when batting first
  field_first_wins: MetricEnvelope // wins when fielding first
  /** Present only when no gender filter is active AND the team has
   *  matches in BOTH genders within the current filter scope. */
  gender_breakdown: { male: number; female: number } | null
  /** Tier 2 — keepers used by this team (sorted by innings kept desc). */
  keepers: { person_id: string; name: string; innings_kept: number }[]
  /** Count of this team's fielding innings with no identified keeper. */
  keeper_ambiguous_innings: number
  /** Distinct canonical tournaments the team has matches in within
   *  the active filter scope. Drives the avg-col label promotion on
   *  the Compare tab — when a club team's universe collapses to a
   *  singleton (RCB → IPL), the avg col labels as the tournament. */
  tournaments_in_scope: string[]
  /** Most recent match date in scope (ISO YYYY-MM-DD). Drives the
   *  dormancy badge on the Teams page header via DormancyContext.
   *  Null when the team has no matches in scope. */
  last_match_date: string | null
  /** Number of distinct teams playing in the active scope. Used by
   *  SplitsMosaic to compute per-team league-avg comparison anchors. */
  unique_teams_in_scope?: number
}

/** Keeper info attached to each innings on the scorecard endpoint. */
export interface ScorecardKeeper {
  person_id: string | null // the keeper's person id; null when the keeper is ambiguous
  name: string | null // the keeper's name; null when ambiguous
  method: string | null // how the keeper was identified; null when ambiguous
  confidence: 'definitive' | 'high' | 'medium' | 'low' | null // how sure the identification is; null when ambiguous
  ambiguous_reason?: string // why no keeper was chosen; only when ambiguous
  candidate_ids?: string[] // the person ids that could have kept; only when ambiguous
  candidate_names?: string[] // the names of `candidate_ids`, in the same order
}

/** One match in a team's results from `/api/v1/teams/{team}/results`. */
export interface TeamResult {
  match_id: number // the match id
  date: string // the first day of the match, as YYYY-MM-DD
  opponent: string // the other team
  venue: string | null // the ground
  city: string | null // the city of the ground
  tournament: string | null // the tournament's name; null for a match outside one
  toss_winner: string | null // the team that won the toss
  toss_decision: string | null // what the toss winner chose, "bat" or "field"
  result: string // "won", "lost", "tied" or "no result", for this team
  margin: string | null // as "23 runs" or "5 wickets"; null for a tie or no result
  player_of_match: string[] | null // the players of the match
}

/** A team's results in one season, from `/api/v1/teams/{team}/by-season`. */
export interface TeamSeasonRecord {
  season: string // the season, as "2023" or "2023/24"
  matches: number // matches played
  wins: number // matches won
  losses: number // matches lost
  ties: number // matches tied
  no_results: number // matches with no result
  win_pct: number | null // wins as a percentage of matches
}

/** A player in a team's squad for one season. */
export interface TeamPlayer {
  person_id: string // the player's person id
  name: string // the display name
  bat_avg: number | null // runs per dismissal for the team that season; null with no dismissals
  bowl_sr: number | null // legal balls per wicket for the team that season; null with no wickets
}

/** How a season's squad differs from the season before. */
export interface TeamSeasonTurnover {
  prev_season: string // the season before, as "2023" or "2023/24"
  new_count: number // players in this season's squad and not the season before
  left_count: number // players in the season before and not this one
}

/** A team's squad in one season, with its turnover. */
export interface TeamPlayersSeasonBucket {
  season: string // the season, as "2023" or "2023/24"
  players: TeamPlayer[] // the squad, sorted by name
  turnover: TeamSeasonTurnover | null // the change from the season before; null for the first season
}

/** A team's squads by season, from `/api/v1/teams/{team}/players-by-season`. */
export interface TeamPlayersBySeason {
  seasons: TeamPlayersSeasonBucket[] // the seasons, latest first
}

/** A team on the Teams landing page. */
export interface TeamsLandingEntry {
  name: string // the team's name
  matches: number // matches in scope
  gender?: string | null // "male" or "female"
}

/** The teams of one tournament on the Teams landing page. */
export interface TeamsLandingTournamentGroup {
  tournament: string // the tournament's name
  matches: number // matches in scope
  teams: TeamsLandingEntry[] // the teams that played in it
}

/** The Teams landing page from `/api/v1/teams/landing`: international teams by gender, and club teams by kind of league. */
export interface TeamsLanding {
  international: { // national teams by gender; `regular` are ICC full members, `associate` the rest
    men: { regular: TeamsLandingEntry[]; associate: TeamsLandingEntry[] }
    women: { regular: TeamsLandingEntry[]; associate: TeamsLandingEntry[] }
  }
  club: { // club teams, grouped by tournament within each kind of league
    franchise_leagues: TeamsLandingTournamentGroup[]
    domestic_leagues: TeamsLandingTournamentGroup[]
    women_franchise: TeamsLandingTournamentGroup[]
    other: TeamsLandingTournamentGroup[]
  }
}

/** Splits Mosaic backing response. Spec: spec-splits-mosaic.md §1.3.
 *  Two modes: landing (subject null) and team-detail (subject.team set,
 *  cells + marginals carry per-axis deltas vs the league baseline). */
export interface SplitsCell {
  toss_outcome: 'won' | 'lost' // the toss, from the team's side
  inning: 0 | 1 // 0 when the team batted first, 1 when it batted second
  result: 'won' | 'lost' | 'tied' // the match result, from the team's side
  n: number // team-matches in this cell
  share: number | null // `n` as a fraction (0 to 1) of all team-matches; null when there are none
  wilson_lo: number | null // the lower end of the Wilson interval on `share`
  wilson_hi: number | null // the upper end of the Wilson interval on `share`
  /** Team-detail mode only — share of the same cell in the league
   *  (unpivoted across all team-views in scope). */
  league_share?: number | null
  /** share - league_share (absolute proportion delta). */
  delta?: number | null
  /** Relative %: (share - league_share) / league_share × 100. */
  delta_pct?: number | null
}

/** The total over one value of one Splits Mosaic axis, such as all cells where the toss was won. */
export interface SplitsMarginalEntry {
  n: number // team-matches with this value
  share: number | null // `n` as a fraction (0 to 1) of all team-matches
  wilson_lo: number | null // the lower end of the Wilson interval on `share`
  wilson_hi: number | null // the upper end of the Wilson interval on `share`
  league_share?: number | null // the league's share for the same value; team-detail mode only
  delta?: number | null // share - league_share; team-detail mode only
  delta_pct?: number | null // (share - league_share) / league_share × 100; team-detail mode only
}

/** The Splits Mosaic from `/api/v1/teams/splits`: matches by toss, inning and result, for a team or the whole league. */
export interface TeamSplits {
  subject: { team: string } | null // the team; null on the landing page, which shows the league
  scope_total_n: number // all team-matches in scope, the denominator of `share`
  /** Team-detail mode only. */
  league_total_n: number | null
  cells: SplitsCell[] // one cell per toss, inning and result
  marginals: { // the totals over each value of each axis
    toss_outcome: Record<'won' | 'lost', SplitsMarginalEntry>
    inning: Record<'0' | '1', SplitsMarginalEntry>
    result: Record<'won' | 'lost' | 'tied', SplitsMarginalEntry>
  }
}

/** A batter on a leaderboard. */
export interface BattingLeaderEntry {
  person_id: string // the batter's person id
  name: string // the display name
  runs: number // runs scored
  balls: number // balls faced
  dismissals: number // times out
  average: number | null // runs per dismissal; null with no dismissals
  strike_rate: number | null // runs per 100 balls
  /** Dominant team in scope. Only set on tournament/rivalry leaders
   *  (not on the landing /batters/leaders). Used by TournamentDossier's
   *  rivalry context links to flip filter_team/filter_opponent per row. */
  team?: string | null
}

/** The batting leaderboards from `/api/v1/batters/leaders` and the series pages. */
export interface BattingLeaders {
  by_runs: BattingLeaderEntry[] // the most runs
  by_average: BattingLeaderEntry[] // the best averages, among batters over the thresholds
  by_strike_rate: BattingLeaderEntry[] // the best strike rates, among batters over the thresholds
  thresholds: { min_balls: number; min_dismissals: number } // the minimum balls and dismissals for the rate boards
}

/** A bowler on a leaderboard. */
export interface BowlingLeaderEntry {
  person_id: string // the bowler's person id
  name: string // the display name
  balls: number // legal balls bowled
  runs_conceded: number // runs given away
  wickets: number // wickets taken
  strike_rate: number | null // balls per wicket; null with no wickets
  economy: number | null // runs per over
  team?: string | null // the dominant team in scope; only on tournament and rivalry leaders
}

/** The bowling leaderboards from `/api/v1/bowlers/leaders` and the series pages. */
export interface BowlingLeaders {
  by_wickets: BowlingLeaderEntry[] // the most wickets
  by_strike_rate: BowlingLeaderEntry[] // the best strike rates, among bowlers over the thresholds
  by_economy: BowlingLeaderEntry[] // the best economy rates, among bowlers over the thresholds
  thresholds: { min_balls: number; min_wickets: number } // the minimum balls and wickets for the rate boards
}

/** A fielder on a leaderboard. */
export interface FieldingLeaderEntry {
  person_id: string // the fielder's person id
  name: string // the display name
  total: number // dismissals credited, which the board ranks by
  catches: number // catches, including caught-and-bowled
  stumpings: number // stumpings
  run_outs?: number  // only present on by_dismissals
  c_and_b?: number // caught-and-bowled, a part of `catches`; only on by_dismissals
  team?: string | null // the dominant team in scope; only on tournament and rivalry leaders
}

/** The fielding leaderboards from `/api/v1/fielders/leaders` and the series pages. */
export interface FieldingLeaders {
  by_dismissals: FieldingLeaderEntry[] // the most dismissals as a fielder
  by_keeper_dismissals: FieldingLeaderEntry[] // the most dismissals as a keeper
  /** Present on /series/fielders-leaders only — top fielders by run-out
   *  count in scope. Absent on the batters-landing-style /fielders/leaders. */
  by_run_outs?: FieldingLeaderEntry[]
}

/** A team's head-to-head record against one opponent, from `/api/v1/teams/{team}/vs/{opponent}`. */
export interface TeamVsOpponent {
  team: string // the team
  opponent: string // the opponent
  overall: { matches: number; wins: number; losses: number; ties: number } // the record over all seasons in scope
  by_season: TeamSeasonRecord[] // the record in each season
  matches: TeamResult[] // the matches between them
}

/** A team's record against one opponent over the whole scope. */
export interface OpponentRollup {
  name: string // the opponent
  matches: number // matches played
  wins: number // matches won
  losses: number // matches lost
  ties: number // matches tied
  no_results: number // matches with no result
  win_pct: number | null // wins as a percentage of matches
}

/** A team's record against one opponent in one season. */
export interface OpponentMatrixCell {
  season: string // the season, as "2023" or "2023/24"
  opponent: string // the opponent
  matches: number // matches played
  wins: number // matches won
  losses: number // matches lost
  ties: number // matches tied
  win_pct: number | null // wins as a percentage of matches
}

/** A team's records against each opponent by season, from `/api/v1/teams/{team}/opponents-matrix`. */
export interface OpponentsMatrix {
  team: string // the team
  seasons: string[] // the seasons, the matrix's columns
  opponents: OpponentRollup[] // the opponents, the matrix's rows
  cells: OpponentMatrixCell[] // one cell per opponent and season they met in
}

/** An international team a player has played for, which gives the flag on a player page. */
export interface NationalityEntry {
  team: string // the national team
  gender: string // "male" or "female", to link to the right team page
  matches: number // matches the player played for it
}

/** A batter's record at one batting position, with the cohort's rates there. */
export interface BattingPositionDistributionEntry {
  bucket: number // the position bucket, 1 to 10; 1 is the two openers merged
  innings: number // innings batted in this bucket
  runs: number // runs scored
  legal_balls: number // legal balls faced
  dismissals: number // times out
  fours: number // fours hit
  sixes: number // sixes hit
  dots: number // dot balls faced
  // spec-mix-and-performance-charts.md §3.1 — per-bucket cohort
  // context for the By Position tab's Mix histogram +
  // Performance-vs-cohort chart. cohort_innings_share sums to 1.0
  // across the 10 entries. Null on buckets the cohort hasn't touched.
  cohort_innings_share: number | null // the cohort's share of innings in this bucket, 0 to 1
  cohort_strike_rate: number | null // the cohort's runs per 100 balls in this bucket
  cohort_average: number | null // the cohort's runs per dismissal in this bucket
}

/** How the batting cohort was built: the player's position mix, and the cohort's size. */
export interface BattingCohortMeta {
  match_dimension: 'position_mix' // what the cohort is weighted by
  position_mix: number[] // the player's share of innings in each of the 10 position buckets, summing to 1
  n_players: number // players in the cohort
  n_innings_total: number // innings in the cohort
}

/** A batter's career summary from `/api/v1/batters/{id}/summary`, each number with the cohort's average. */
export interface BattingSummary {
  person_id: string // the batter's person id
  name: string // the display name
  nationalities: NationalityEntry[] // the national teams played for, most matches first; empty for club-only players
  // Identity-bearing fields stay flat.
  highest_score: number // the highest score in one innings
  // Numeric fields are envelope-wrapped per Phase 4
  // (spec-player-compare-average.md). Counts have direction=null;
  // rate metrics (average, strike_rate, dot_pct, boundary_pct) carry
  // direction + delta_pct vs the position-mix-weighted cohort.
  matches: MetricEnvelope // matches batted in
  /** Squad appearances ("played") — headline matches count. `matches`
   *  above is matches BATTED; the tile shows played + "batted in N". */
  matches_played: MetricEnvelope
  innings: MetricEnvelope // innings batted
  runs: MetricEnvelope // runs scored
  balls_faced: MetricEnvelope // legal balls faced
  not_outs: MetricEnvelope // innings not out
  dismissals: MetricEnvelope // times out
  hundreds: MetricEnvelope // scores of 100 or more
  fifties: MetricEnvelope // scores of 50 to 99
  thirties: MetricEnvelope // scores of 30 to 49
  ducks: MetricEnvelope // dismissals for 0
  fours: MetricEnvelope // fours hit
  sixes: MetricEnvelope // sixes hit
  boundaries: MetricEnvelope // fours and sixes
  dots: MetricEnvelope // dot balls faced
  average: MetricEnvelope // runs per dismissal
  strike_rate: MetricEnvelope // runs per 100 balls
  dot_pct: MetricEnvelope // dot balls as a percentage of balls faced
  boundary_pct: MetricEnvelope // boundaries as a percentage of balls faced
  balls_per_four: MetricEnvelope // balls faced per four
  balls_per_six: MetricEnvelope // balls faced per six
  balls_per_boundary: MetricEnvelope // balls faced per boundary
  // Q6 per-innings rate envelopes (spec-player-baseline-parity.md
  // §3.3.1) — shipped session 1 in commit 55c890a. Each is a rate
  // metric: numerator (volume above) divided by innings_total.
  boundaries_per_innings: MetricEnvelope // boundaries per innings
  sixes_per_innings: MetricEnvelope // sixes per innings
  fours_per_innings: MetricEnvelope // fours per innings
  thirties_per_innings: MetricEnvelope // scores of 30 to 49, per innings
  fifties_per_innings: MetricEnvelope // scores of 50 to 99, per innings
  hundreds_per_innings: MetricEnvelope // scores of 100 or more, per innings
  ducks_per_innings: MetricEnvelope // ducks per innings
  // spec-rate-vs-volume-audit.md §2.1 Group A — sibling rate to the
  // Runs volume tile.
  runs_per_innings: MetricEnvelope // runs per innings
  // Per-bucket position distribution + cohort context (next-spec viz
  // consumes the by-bucket data; this spec uses just the cohort
  // baseline aggregated by the backend).
  position_distribution: BattingPositionDistributionEntry[] // the record at each of the 10 position buckets
  cohort: BattingCohortMeta | null // how the cohort was built; null when there is no cohort
  cohort_below_support: boolean // true when a bucket the player bats in has too few cohort innings, so the cohort rates are null
  cohort_cliff_buckets: number[] // the buckets that have too few cohort innings
}

/** One innings of a batter, from `/api/v1/batters/{id}/by-innings`. */
export interface BattingInnings {
  match_id: number // the match id
  date: string // the match date, as YYYY-MM-DD
  team: string // the batter's team
  opponent: string // the other team
  venue: string | null // the ground
  tournament: string | null // the tournament's name; null for a match outside one
  runs: number // runs scored
  balls: number // legal balls faced
  fours: number // fours hit
  sixes: number // sixes hit
  strike_rate: number | null // runs per 100 balls; null with no balls
  not_out: boolean // true when the batter was not out
  how_out: string | null // the kind of dismissal, such as "caught"; null when not out
  dismissed_by: string | null // the bowler of the dismissal ball; null when not out
}

/** A batter's record against one bowler, from `/api/v1/batters/{id}/vs-bowlers`. */
export interface BowlerMatchup {
  bowler_id: string // the bowler's person id
  bowler_name: string // the bowler's name
  balls: number // legal balls faced from the bowler
  runs: number // runs scored off the bowler
  dismissals: number // times out to the bowler
  average: number | null // runs per dismissal; null with no dismissals
  strike_rate: number | null // runs per 100 balls
  fours: number // fours hit
  sixes: number // sixes hit
  dots: number // dot balls
  dot_pct: number | null // dot balls as a percentage of balls
  balls_per_four: number | null // balls per four; null with no fours
  balls_per_six: number | null // balls per six; null with no sixes
  balls_per_boundary: number | null // balls per boundary; null with no boundaries
}

/** A player's record in one over of the innings, from the batter and bowler by-over endpoints. */
export interface OverStats {
  over_number: number // the over, 1 to 20
  balls: number // legal balls
  runs: number // runs
  fours: number // fours
  sixes: number // sixes
  dots: number // dot balls
  dismissals: number // wickets that fell
  strike_rate: number | null // runs per 100 balls
  dot_pct: number | null // dot balls as a percentage of balls
  boundary_pct: number | null // boundaries as a percentage of balls
  balls_per_four: number | null // balls per four; null with no fours
  balls_per_six: number | null // balls per six; null with no sixes
  balls_per_boundary: number | null // balls per boundary; null with no boundaries
}

/** A player's record in one phase of the innings, from the batter and bowler by-phase endpoints. */
export interface PhaseStats {
  phase: string // "powerplay", "middle" or "death"
  overs: string // the overs of the phase: "1-6", "7-15" or "16-20"
  balls: number // legal balls
  runs: number // runs
  fours: number // fours
  sixes: number // sixes
  dots: number // dot balls
  dismissals: number // wickets that fell
  strike_rate: number | null // runs per 100 balls
  dot_pct: number | null // dot balls as a percentage of balls
  boundary_pct: number | null // boundaries as a percentage of balls
}

/** A batter's record in one season, from `/api/v1/batters/{id}/by-season`. */
export interface SeasonBattingStats {
  season: string // the season, as "2023" or "2023/24"
  innings: number // innings batted
  runs: number // runs scored
  balls: number // legal balls faced
  average: number | null // runs per dismissal; null with no dismissals
  strike_rate: number | null // runs per 100 balls
  fours: number // fours hit
  sixes: number // sixes hit
  fifties: number // scores of 50 to 99
  hundreds: number // scores of 100 or more
  dismissals: number // times out
  balls_per_boundary: number | null // balls per boundary; null with no boundaries
  // spec-rate-vs-volume-audit §2.1 Group B — per-innings rate fields
  // emitted per /batters/{id}/by-season row.
  thirties?: number // scores of 30 to 49
  ducks?: number // dismissals for 0
  runs_per_innings?: number | null // runs per innings
  hundreds_per_innings?: number | null // hundreds per innings
  fifties_per_innings?: number | null // fifties per innings
  thirties_per_innings?: number | null // thirties per innings
  ducks_per_innings?: number | null // ducks per innings
  fours_per_innings?: number | null // fours per innings
  sixes_per_innings?: number | null // sixes per innings
  boundaries_per_innings?: number | null // boundaries per innings
}

/** How a batter gets out, from `/api/v1/batters/{id}/dismissals`. */
export interface DismissalAnalysis {
  total_dismissals: number // times out
  by_kind: Record<string, number> // dismissals by kind, such as "caught" or "bowled"
  by_phase: Record<string, number> // dismissals by phase: "powerplay", "middle", "death"
  by_over: { over_number: number; dismissals: number }[] // dismissals in each over
  top_bowlers: { // the bowlers who took the batter's wicket most often, with the kinds of dismissal
    bowler_id: string
    bowler_name: string
    dismissals: number
    kinds: Record<string, number>
  }[]
  // Innings + not-outs power the per-innings normalization on the
  // mode-of-dismissal cohort chart (not-out is its own modality).
  innings: number // innings batted
  not_outs: number // innings not out
}

/**
 * A player's career totals for one team, from `/api/v1/players/{id}/teams`.
 *
 * Per-team career volume for the "teams played for" strip at the top
 * of the player profile. Totals partition
 * the team-filtered discipline /summary pages exactly.
 */
export interface PlayerTeamTotals {
  team: string // the team
  matches: number // matches played for it
  runs: number // runs scored for it
  wickets: number // wickets taken for it
  catches: number // catches taken for it
}

/**
 * A team a player has played against, from `/api/v1/players/{id}/opponents`.
 *
 * Opponent menu for the player-page "Versus" filter. Teams the player has faced (with match
 * counts), narrowed to the player's spell when filter_team is pinned.
 */
export interface PlayerOpponentTotals {
  opponent: string // the opposing team
  matches: number // matches played against it
}

/**
 * How the batters of the scope get out, from `/api/v1/scope/averages/batting/dismissals`.
 *
 * Pooled-scope cohort dismissal distribution. Same shape as the player's, minus top_bowlers.
 */
export interface ScopeDismissals {
  total_dismissals: number // dismissals in scope
  by_kind: Record<string, number> // dismissals by kind, such as "caught" or "bowled"
  by_phase: Record<string, number> // dismissals by phase: "powerplay", "middle", "death"
  by_over: { over_number: number; dismissals: number }[] // dismissals in each over
  innings: number // innings batted in scope
  not_outs: number // innings not out
}

/**
 * A fielder's dismissals in one over, from `/api/v1/fielders/{id}/by-over`.
 *
 * Per-over fielding rollup — drives the By Over tab charts.
 * User-asked 2026-05-23: catches / run_outs / stumpings broken out
 * per over + cohort dismissals-per-match for a rate-vs-cohort chart.
 */
export interface FieldingByOverEntry {
  over_number: number // the over, 1 to 20
  dismissals: number // dismissals the fielder took part in
  catches: number // catches
  run_outs: number // run-outs
  stumpings: number // stumpings
  /** Cohort dismissals per match at this over, partitioned by the
   *  player's keeper-binary (matches_as_keeper > 0). */
  cohort_dismissals_per_match: number | null
}

/** A batter's record at one count of wickets down, from `/api/v1/batters/{id}/inter-wicket`. */
export interface InterWicketStats {
  wickets_down: number // wickets fallen before the ball, 0 to 10
  innings_count: number // innings with a legal ball faced at this count
  balls: number // legal balls faced
  runs: number // runs scored
  fours: number // fours hit
  sixes: number // sixes hit
  strike_rate: number | null // runs per 100 balls
  dismissals: number // times out at this count
  avg_balls_before_next_wicket: number | null // average balls before the next wicket; the backend does not send it now
  /** Cohort strike rate at this wickets_down — aggregated across
   *  every legal-ball delivery at the FilterParams scope (no
   *  batter_id filter). Drives the green reference line on the
   *  Strike-Rate-by-Wickets-Down chart. User-asked 2026-05-22. */
  cohort_strike_rate: number | null
}

// ─── Batter distribution dossier ────────────────────────────────────────
//
// Mirror of the /api/v1/batters/{id}/distribution response. Spec:
// docs/internal/spec-distribution-stats.md §8.8.

/** One innings of a batter in a distribution dossier, with its runs and balls by phase. */
export interface InningsObservation {
  innings_id: number // the innings id
  match_id: number // the match id
  date: string | null // the match date, as YYYY-MM-DD
  runs: number // runs scored
  balls: number // legal balls faced
  /** Per-innings strike rate computed server-side as runs*100/balls.
   *  Null when balls=0 (e.g. dismissed without facing a ball). Audit §4.5. */
  strike_rate: number | null
  dismissed: boolean // true when the batter was out
  fours: number // fours hit
  sixes: number // sixes hit
  dots: number // dot balls faced
  runs_pp: number // runs in the powerplay, overs 1 to 6
  balls_pp: number // balls faced in the powerplay
  runs_mid: number // runs in the middle overs, 7 to 15
  balls_mid: number // balls faced in the middle overs
  runs_death: number // runs at the death, overs 16 to 20
  balls_death: number // balls faced at the death
}

/** A batter's totals in one phase over all the innings of a dossier. */
export interface DistributionPhaseRollup {
  runs_total: number // runs in the phase
  balls_total: number // balls faced in the phase
  innings_active: number // innings with at least one ball faced in the phase
}

/** The distribution of a batter's innings over one window: runs, milestone chances and phases. */
export interface DistributionDossier {
  n_innings: number // innings in the window
  n_dismissals: number // innings out
  n_notouts: number // innings not out
  /** Max observation date in the scope (ISO YYYY-MM-DD). Null when scope is empty. Drives the dormancy badge. Only on the `lifetime` dossier — form-window dossiers may inherit it via the same shape but it's primarily meaningful on lifetime. */
  last_match_date?: string | null
  runs: { // the runs: totals, mean, median, spread, average, strike rate, and each innings
    total: number
    balls_total: number
    mean_per_innings: number | null
    median: number | null
    variance: number | null
    std: number | null
    average: number | null
    /** Career SR for the scope = total*100/balls_total. Server-computed
     *  (audit §4.1). Null when balls_total=0. */
    strike_rate: number | null
    observations: InningsObservation[]
  }
  milestones: { // the chances of 10 or fewer runs, of 25, 30, 50 or 100 plus, and of going on from 30 or 50
    p_failure_10: ProbRecord
    p_25_plus: ProbRecord
    p_30_plus: ProbRecord
    p_50_plus: ProbRecord
    p_100_plus: ProbRecord
    /** P(runs ≥ 50 | runs ≥ 30) — value=None when no innings reached 30. */
    p_50_given_30: ProbRecord
    /** P(runs ≥ 70 | runs ≥ 50) — value=None when no innings reached 50. */
    p_70_given_50: ProbRecord
  }
  phase: { // the totals in the powerplay, middle and death overs
    powerplay: DistributionPhaseRollup
    middle: DistributionPhaseRollup
    death: DistributionPhaseRollup
  }
}

/** A link to a related scope that the distribution panel suggests, such as the same player in one season. */
export interface SuggestedSplit {
  label: string // the link text
  params: Record<string, string> // the URL search params of the link
}

/** A batter's distribution dossier from `/api/v1/batters/{id}/distribution`: lifetime and recent form. */
export interface BatterDistribution {
  scope: Record<string, string> // the filters in effect, without the empty ones
  lifetime: DistributionDossier // all innings in scope
  form: { // the last 10 innings and the last 60 days, 6 months and year, with each window's mean and median minus lifetime
    last_10: DistributionDossier
    last_60d: DistributionDossier
    last_6mo: DistributionDossier
    last_1yr: DistributionDossier
    delta: {
      last_10_mean_minus_lifetime: number | null
      last_10_median_minus_lifetime: number | null
      last_60d_mean_minus_lifetime: number | null
      last_60d_median_minus_lifetime: number | null
      last_6mo_mean_minus_lifetime: number | null
      last_6mo_median_minus_lifetime: number | null
      last_1yr_mean_minus_lifetime: number | null
      last_1yr_median_minus_lifetime: number | null
    }
  }
  suggested_splits: SuggestedSplit[] // links to related scopes
}

// ─── Bowler distribution dossier ────────────────────────────────────────
//
// Mirror of /api/v1/bowlers/{id}/distribution. Spec:
// docs/internal/spec-distribution-stats.md §11.8.

/**
 * Wilson 95% CI binomial proportion record. Used by every probability
 * field across the distribution dossiers (bowler v1; batter retrofit
 * pending). `value`, `ci_low`, `ci_high` are null when denom == 0
 * (undefined ratio). Backend helper: api/wilson.py::prob_record.
 *
 * spec-prob-baselines.md §4.1 — `scope_avg` / `delta_pct` / `direction` /
 * `sample_size` are the chip-cohort extension. Optional because not
 * every prob endpoint has been wired through `enrich_prob_record`
 * (batting milestones landed in PT1.B; bowling / fielding ladders
 * follow in PT2-PT4). Null fields mean "below sample" — the caption
 * renders as "vs — (below sample)".
 */
export interface ProbRecord {
  value: number | null // num / denom, 0 to 1; null when denom is 0
  num: number // the count that meets the condition, such as innings of 50 plus
  denom: number // the count the chance is out of, such as all innings
  ci_low: number | null // the lower end of the Wilson 95% interval
  ci_high: number | null // the upper end of the Wilson 95% interval
  scope_avg?: number | null // the cohort's chance; null below sample
  delta_pct?: number | null // (value - scope_avg) / scope_avg × 100
  direction?: 'higher_better' | 'lower_better' | null // which way is better
  sample_size?: number | null // the cohort's sample size
}

/** One innings of a bowler in a distribution dossier, with its figures by phase. */
export interface BowlerInningsObservation {
  innings_id: number // the innings id
  match_id: number // the match id
  date: string | null // the match date, as YYYY-MM-DD
  balls: number // legal balls bowled
  runs_conceded: number // runs given away
  wickets: number // wickets taken
  dots: number // dot balls
  boundaries_conceded: number // fours and sixes hit off the bowler
  wides: number // wides bowled
  noballs: number // no-balls bowled
  runs_pp: number // runs conceded in the powerplay, overs 1 to 6
  balls_pp: number // balls bowled in the powerplay
  wickets_pp: number // wickets in the powerplay
  runs_mid: number // runs conceded in the middle overs, 7 to 15
  balls_mid: number // balls bowled in the middle overs
  wickets_mid: number // wickets in the middle overs
  runs_death: number // runs conceded at the death, overs 16 to 20
  balls_death: number // balls bowled at the death
  wickets_death: number // wickets at the death
}

/** The distribution of a bowler's wickets per innings, with the chances of each haul. */
export interface BowlerWicketsBlock {
  total: number // wickets taken
  mean_per_innings: number | null // wickets per innings
  median: number | null // the median wickets in an innings
  variance: number | null // the variance of wickets per innings
  std: number | null // the standard deviation of wickets per innings
  observations: BowlerInningsObservation[] // each innings
  milestones: { // the chances of 0 wickets, of 1 to 5 or more, and of going on from 2
    p_zero: ProbRecord
    p_geq_1: ProbRecord
    p_geq_2: ProbRecord
    p_geq_3: ProbRecord
    p_geq_4: ProbRecord
    p_geq_5: ProbRecord
    /** P(w ≥ 3 | w ≥ 2) — denom = count(≥2) for all conditionals (≥2-anchored ladder, spec §11.4.1). */
    p_3_given_2: ProbRecord
    p_4_given_2: ProbRecord
    p_5_given_2: ProbRecord
  }
}

/** The distribution of the runs a bowler concedes per innings. */
export interface BowlerRunsConcededBlock {
  total: number // runs conceded
  mean_per_innings: number | null // runs conceded per innings
  median: number | null // the median runs conceded in an innings
  variance: number | null // the variance of runs per innings
  std: number | null // the standard deviation of runs per innings
  milestones: { // the chances of 15 or fewer, 25 or fewer, 40 or more and 50 or more runs
    p_leq_15: ProbRecord
    p_leq_25: ProbRecord
    p_geq_40: ProbRecord
    p_geq_50: ProbRecord
  }
}

/** The distribution of a bowler's economy rate per innings. */
export interface BowlerEconomyBlock {
  /** Pool / balls-weighted economy — the conventional career number. */
  pool: number | null
  /** Unweighted mean of per-innings economies — different from pool when innings vary in balls. */
  mean_per_innings: number | null
  median_per_innings: number | null // the median economy of an innings
  variance: number | null // the variance of per-innings economy
  std: number | null // the standard deviation of per-innings economy
  /** Per-innings RPO list, derived at dossier-build time from observations. */
  per_innings: number[]
  milestones: { // the chances of an economy of 6 or less, 7 or less, 9 or more and 10 or more
    p_econ_leq_6: ProbRecord
    p_econ_leq_7: ProbRecord
    p_econ_geq_9: ProbRecord
    p_econ_geq_10: ProbRecord
  }
}

/** A bowler's totals in one phase over all the innings of a dossier. */
export interface BowlerPhaseRollup {
  runs_total: number // runs conceded in the phase
  balls_total: number // legal balls bowled in the phase
  wickets_total: number // wickets taken in the phase
  innings_active: number // innings with at least one ball bowled in the phase
}

/** The distribution of a bowler's innings over one window: wickets, runs, economy and phases. */
export interface BowlerDossier {
  n_innings: number // innings bowled in the window
  /** Max observation date in the scope (ISO YYYY-MM-DD). Drives the dormancy badge on the lifetime block. */
  last_match_date?: string | null
  /** Pool SR = total_balls / total_wickets when wickets > 0, else null. */
  pool_strike_rate: number | null
  /** Pool average = total_runs_conceded / total_wickets when wickets > 0, else null. */
  pool_average: number | null
  wickets: BowlerWicketsBlock // wickets per innings
  runs_conceded: BowlerRunsConcededBlock // runs conceded per innings
  economy: BowlerEconomyBlock // economy per innings
  phase: { // the totals in the powerplay, middle and death overs
    powerplay: BowlerPhaseRollup
    middle: BowlerPhaseRollup
    death: BowlerPhaseRollup
  }
}

/** A bowler's distribution dossier from `/api/v1/bowlers/{id}/distribution`: lifetime and recent form. */
export interface BowlerDistribution {
  scope: Record<string, string> // the filters in effect, without the empty ones
  thresholds: { min_balls: number } // the fewest balls an innings needs to count
  lifetime: BowlerDossier // all innings in scope
  form: { // the last 10 innings and the last 60 days, 6 months and year, with each window's wickets mean and economy minus lifetime
    last_10: BowlerDossier
    last_60d: BowlerDossier
    last_6mo: BowlerDossier
    last_1yr: BowlerDossier
    delta: {
      last_10_wickets_mean_minus_lifetime: number | null
      last_10_economy_pool_minus_lifetime: number | null
      last_60d_wickets_mean_minus_lifetime: number | null
      last_60d_economy_pool_minus_lifetime: number | null
      last_6mo_wickets_mean_minus_lifetime: number | null
      last_6mo_economy_pool_minus_lifetime: number | null
      last_1yr_wickets_mean_minus_lifetime: number | null
      last_1yr_economy_pool_minus_lifetime: number | null
    }
  }
  suggested_splits: SuggestedSplit[] // links to related scopes
}

// ─── Fielder distribution dossier ───────────────────────────────────────
//
// Mirror of /api/v1/fielders/{id}/distribution. Spec:
// docs/internal/spec-distribution-stats.md §13.

/** One match of a fielder in a distribution dossier. */
export interface FielderObservation {
  match_id: number // the match id
  date: string | null // the match date, as YYYY-MM-DD
  catches: number // catches taken
  run_outs: number // run-outs made
  stumpings: number // stumpings made
  is_keeper: 0 | 1 // 1 when the player kept wicket in the match
}

/** The distribution of one kind of fielding dismissal per match. */
export interface FielderCountBlock {
  total: number // dismissals of this kind
  mean_per_match: number | null // dismissals per match
  median: number | null // the median dismissals in a match
  variance: number | null // the variance of dismissals per match
  std: number | null // the standard deviation of dismissals per match
  milestones: { // the chances of 0, 1, and 2 or more in a match
    p_zero: ProbRecord
    p_one: ProbRecord
    p_geq_2: ProbRecord
  }
}

/** The distribution of a fielder's matches over one window: catches, run-outs and stumpings. */
export interface FielderDossier {
  n_matches: number // matches in the window
  /** Max observation date in the scope (ISO YYYY-MM-DD). Drives the dormancy badge on the lifetime block. */
  last_match_date?: string | null
  /** Sum of keeperassignment rows for this player in scope. Drives the conditional stumpings tab — only present when > 0. */
  innings_kept: number
  /** Substitute catches in scope — surfaced for reconciliation against /summary. Excluded from `catches.total`. */
  substitute_catches: number
  observations: FielderObservation[] // each match
  catches: FielderCountBlock // catches per match
  run_outs: FielderCountBlock // run-outs per match
  /** Null when innings_kept === 0 (non-keeper). */
  stumpings: FielderCountBlock | null
}

/** A fielder's distribution dossier from `/api/v1/fielders/{id}/distribution`: lifetime and recent form. */
export interface FielderDistribution {
  scope: Record<string, string> // the filters in effect, without the empty ones
  lifetime: FielderDossier // all matches in scope
  form: { // the last 10 matches and the last 60 days, 6 months and year, with each window's deltas from lifetime
    last_10: FielderDossier
    last_60d: FielderDossier
    last_6mo: FielderDossier
    last_1yr: FielderDossier
    /** 12 entries: 4 windows × 3 metrics. Stumpings deltas are null for non-keepers. */
    delta: Record<string, number | null>
  }
  suggested_splits: SuggestedSplit[] // links to related scopes
}

// ─── Team batting distribution dossier ──────────────────────────────────
//
// Mirror of /api/v1/teams/{team}/batting/distribution. Spec:
// docs/internal/spec-distribution-stats.md §16.2.

/** One batting innings of a team in a distribution dossier, with its figures at 10 overs and by phase. */
export interface TeamBattingInningsObservation {
  innings_id: number // the innings id
  match_id: number // the match id
  innings_number: number // the innings of the match
  date: string | null // the match date, as YYYY-MM-DD
  runs: number // the total
  balls: number // legal balls faced
  wickets: number // wickets lost
  /** Team total runs at end of over 10 (start-of-mid). */
  runs_at_10: number
  /** Wickets fallen by end of over 10. */
  wickets_at_10: number
  /** 1 when the innings reached over 10, else 0 — denominator gate for over-aware probabilities. */
  reached_10_overs: 0 | 1
  runs_pp: number // runs in the powerplay, overs 1 to 6
  balls_pp: number // balls in the powerplay
  wickets_pp: number // wickets lost in the powerplay
  runs_mid: number // runs in the middle overs, 7 to 15
  balls_mid: number // balls in the middle overs
  wickets_mid: number // wickets lost in the middle overs
  runs_death: number // runs at the death, overs 16 to 20
  balls_death: number // balls at the death
  wickets_death: number // wickets lost at the death
}

/** The distribution of a team's innings totals, with the chances of reaching each total. */
export interface TeamBattingRunsBlock {
  total: number // runs over all innings
  mean_per_innings: number | null // the mean innings total
  median: number | null // the median innings total
  variance: number | null // the variance of innings totals
  std: number | null // the standard deviation of innings totals
  /** Median of `final_runs / runs_at_10` over innings with reached_10_overs=1 AND runs_at_10 > 0 — paired with `p_double_at_10`. */
  escalation_ratio_median: number | null
  observations: TeamBattingInningsObservation[] // each innings
  milestones: { // the chances of under 100, of 100, 150, 200 or 230 plus, of going on to the next mark, and of doubling the 10-over score
    p_lt_100: ProbRecord
    p_geq_100: ProbRecord
    p_geq_150: ProbRecord
    p_geq_200: ProbRecord
    p_geq_230: ProbRecord
    /** P(runs ≥ 150 | runs ≥ 100) — chain-ladder; denom = count(≥100). */
    p_150_given_100: ProbRecord
    p_200_given_150: ProbRecord
    p_230_given_200: ProbRecord
    /** Over-aware: P(final ≥ 2 × runs_at_10 | reached_10_overs=1, runs_at_10>0). */
    p_double_at_10: ProbRecord
  }
}

/** The distribution of a team's run rate per innings. */
export interface TeamBattingRunRateBlock {
  /** Pool RR — total_runs / total_balls × 6 (balls-weighted, conventional career RR). */
  pool: number | null
  mean_per_innings: number | null // the unweighted mean of per-innings run rates
  median_per_innings: number | null // the median run rate of an innings
  variance: number | null // the variance of per-innings run rates
  std: number | null // the standard deviation of per-innings run rates
  /** Per-innings RR list aligned with runs.observations. */
  per_innings: number[]
  milestones: { // the chances of a run rate of 7 or less, 8 or less, 9 or more and 10 or more
    p_rr_leq_7: ProbRecord
    p_rr_leq_8: ProbRecord
    p_rr_geq_9: ProbRecord
    p_rr_geq_10: ProbRecord
  }
}

/** A team's batting totals in one phase over all the innings of a dossier. */
export interface TeamBattingPhaseRollup {
  runs_total: number // runs in the phase
  balls_total: number // legal balls in the phase
  wickets_total: number // wickets lost in the phase
  innings_active: number // innings with at least one ball in the phase
}

/** The distribution of a team's batting innings over one window: totals, run rate and phases. */
export interface TeamBattingDossier {
  n_innings: number // innings in the window
  /** Max observation date in the scope (ISO YYYY-MM-DD). Drives the dormancy badge on the lifetime block. */
  last_match_date?: string | null
  runs: TeamBattingRunsBlock // innings totals
  run_rate: TeamBattingRunRateBlock // run rates
  phase: { // the totals in the powerplay, middle and death overs
    powerplay: TeamBattingPhaseRollup
    middle: TeamBattingPhaseRollup
    death: TeamBattingPhaseRollup
  }
}

/** A team's batting distribution dossier from `/api/v1/teams/{team}/batting/distribution`: lifetime and recent form. */
export interface TeamBattingDistribution {
  team: string // the team
  scope: Record<string, string> // the filters in effect, without the empty ones
  lifetime: TeamBattingDossier // all innings in scope
  form: { // the last 10 innings and the last 60 days, 6 months and year, with each window's deltas from lifetime
    last_10: TeamBattingDossier
    last_60d: TeamBattingDossier
    last_6mo: TeamBattingDossier
    last_1yr: TeamBattingDossier
    /** 8 entries: 4 windows × 2 metrics (runs.mean, run_rate.pool). */
    delta: {
      last_10_runs_mean_minus_lifetime: number | null
      last_10_run_rate_pool_minus_lifetime: number | null
      last_60d_runs_mean_minus_lifetime: number | null
      last_60d_run_rate_pool_minus_lifetime: number | null
      last_6mo_runs_mean_minus_lifetime: number | null
      last_6mo_run_rate_pool_minus_lifetime: number | null
      last_1yr_runs_mean_minus_lifetime: number | null
      last_1yr_run_rate_pool_minus_lifetime: number | null
    }
  }
  suggested_splits: SuggestedSplit[] // links to related scopes
}

// ─── Team bowling distribution dossier ──────────────────────────────────
//
// Mirror of /api/v1/teams/{team}/bowling/distribution. Spec:
// docs/internal/spec-distribution-stats.md §16.3 (backend) + §17.4 (frontend).

/** One bowling innings of a team in a distribution dossier, with the opposition's figures at 10 overs and by phase. */
export interface TeamBowlingInningsObservation {
  innings_id: number // the innings id
  match_id: number // the match id
  innings_number: number // the innings of the match
  date: string | null // the match date, as YYYY-MM-DD
  /** Runs conceded — opposition's total against this team's bowlers. */
  runs_conceded: number
  /** Legal balls bowled in the innings (wides + no-balls excluded). */
  balls: number
  /** Wickets credited to the team (includes run-outs; 4-kind exclusion list — diverges from team-bowling/summary which is bowler-credited). */
  wickets: number
  /** Opposition runs at end of over 10. */
  runs_at_10: number
  /** Opposition wickets fallen by end of over 10. */
  wickets_at_10: number
  /** 1 when the innings reached over 10, else 0 — denominator gate for over-aware probabilities. */
  reached_10_overs: 0 | 1
  runs_pp: number // runs conceded in the powerplay, overs 1 to 6
  balls_pp: number // balls bowled in the powerplay
  wickets_pp: number // wickets taken in the powerplay
  runs_mid: number // runs conceded in the middle overs, 7 to 15
  balls_mid: number // balls bowled in the middle overs
  wickets_mid: number // wickets taken in the middle overs
  runs_death: number // runs conceded at the death, overs 16 to 20
  balls_death: number // balls bowled at the death
  wickets_death: number // wickets taken at the death
}

/** The distribution of the wickets a team takes per innings, with the chances of each count. */
export interface TeamBowlingWicketsBlock {
  total: number // wickets over all innings
  mean_per_innings: number | null // wickets per innings
  median: number | null // the median wickets in an innings
  variance: number | null // the variance of wickets per innings
  std: number | null // the standard deviation of wickets per innings
  observations: TeamBowlingInningsObservation[] // each innings
  milestones: { // the chances of 3 or fewer, 5 or 7 plus, and all 10 wickets, of going on from 5, and the 10-over chances
    p_leq_3: ProbRecord
    p_geq_5: ProbRecord
    p_geq_7: ProbRecord
    p_eq_10: ProbRecord
    /** P(wkts ≥ 7 | wkts ≥ 5) — denom = count(≥5). */
    p_7_given_5: ProbRecord
    p_10_given_5: ProbRecord
    /** Over-aware: P(opp wickets_at_10 ≥ 3 | reached_10_overs=1) — early breakthrough. */
    p_geq_3_at_10: ProbRecord
    /** Over-aware: P(final wickets = 10 | wickets_at_10 ≥ 3) — finishing rate. */
    p_eq_10_given_3_at_10: ProbRecord
  }
}

/** The distribution of the totals a team concedes, with the chances of each total. */
export interface TeamBowlingRunsConcededBlock {
  total: number // runs conceded over all innings
  mean_per_innings: number | null // the mean total conceded
  median: number | null // the median total conceded
  variance: number | null // the variance of totals conceded
  std: number | null // the standard deviation of totals conceded
  /** Median of `final_runs_conceded / runs_at_10` over innings with reached_10_overs=1 AND runs_at_10 > 0 — paired with `p_double_at_10`. */
  escalation_ratio_median: number | null
  milestones: { // the chances of conceding under 100 or 150, 150, 200 or 230 plus, of going on to the next mark, and of doubling the 10-over score
    p_lt_100: ProbRecord
    p_lt_150: ProbRecord
    p_geq_150: ProbRecord
    p_geq_200: ProbRecord
    p_geq_230: ProbRecord
    /** Conditional chain: P(conceded ≥ 150 | conceded ≥ 100) — climbing here is bad. */
    p_150_given_100: ProbRecord
    p_200_given_150: ProbRecord
    p_230_given_200: ProbRecord
    /** Over-aware: P(final_runs_conceded ≥ 2 × runs_at_10 | reached_10_overs=1, runs_at_10>0). */
    p_double_at_10: ProbRecord
  }
}

/** The distribution of a team's economy rate per bowling innings. */
export interface TeamBowlingEconomyBlock {
  /** Pool economy — total_runs_conceded × 6 / total_legal_balls (balls-weighted, conventional career). */
  pool: number | null
  mean_per_innings: number | null // the unweighted mean of per-innings economies
  median_per_innings: number | null // the median economy of an innings
  variance: number | null // the variance of per-innings economy
  std: number | null // the standard deviation of per-innings economy
  /** Per-innings RPO list aligned with wickets.observations. */
  per_innings: number[]
  milestones: { // the chances of an economy of 6 or less, 7 or less, 9 or more and 10 or more
    p_econ_leq_6: ProbRecord
    p_econ_leq_7: ProbRecord
    p_econ_geq_9: ProbRecord
    p_econ_geq_10: ProbRecord
  }
}

/** A team's bowling totals in one phase over all the innings of a dossier. */
export interface TeamBowlingPhaseRollup {
  runs_total: number // runs conceded in the phase
  balls_total: number // legal balls bowled in the phase
  wickets_total: number // wickets taken in the phase
  innings_active: number // innings with at least one ball in the phase
}

/** The distribution of a team's bowling innings over one window: wickets, runs conceded, economy and phases. */
export interface TeamBowlingDossier {
  n_innings: number // innings in the window
  /** Max observation date in the scope (ISO YYYY-MM-DD). Drives the dormancy badge on the lifetime block. */
  last_match_date?: string | null
  /** Pool strike rate (balls/wkt) — server-computed (audit §4.3). Null when total_wickets=0. */
  pool_strike_rate: number | null
  /** Pool bowling average (runs/wkt) — server-computed (audit §4.3). Null when total_wickets=0. */
  pool_average: number | null
  wickets: TeamBowlingWicketsBlock // wickets per innings
  runs_conceded: TeamBowlingRunsConcededBlock // totals conceded
  economy: TeamBowlingEconomyBlock // economy per innings
  phase: { // the totals in the powerplay, middle and death overs
    powerplay: TeamBowlingPhaseRollup
    middle: TeamBowlingPhaseRollup
    death: TeamBowlingPhaseRollup
  }
}

/** A team's bowling distribution dossier from `/api/v1/teams/{team}/bowling/distribution`: lifetime and recent form. */
export interface TeamBowlingDistribution {
  team: string // the team
  scope: Record<string, string> // the filters in effect, without the empty ones
  lifetime: TeamBowlingDossier // all innings in scope
  form: { // the last 10 innings and the last 60 days, 6 months and year, with each window's deltas from lifetime
    last_10: TeamBowlingDossier
    last_60d: TeamBowlingDossier
    last_6mo: TeamBowlingDossier
    last_1yr: TeamBowlingDossier
    /** 12 entries: 4 windows × 3 metrics (wickets.mean, runs_conceded.mean, economy.pool). */
    delta: {
      last_10_wickets_mean_minus_lifetime: number | null
      last_10_runs_conceded_mean_minus_lifetime: number | null
      last_10_economy_pool_minus_lifetime: number | null
      last_60d_wickets_mean_minus_lifetime: number | null
      last_60d_runs_conceded_mean_minus_lifetime: number | null
      last_60d_economy_pool_minus_lifetime: number | null
      last_6mo_wickets_mean_minus_lifetime: number | null
      last_6mo_runs_conceded_mean_minus_lifetime: number | null
      last_6mo_economy_pool_minus_lifetime: number | null
      last_1yr_wickets_mean_minus_lifetime: number | null
      last_1yr_runs_conceded_mean_minus_lifetime: number | null
      last_1yr_economy_pool_minus_lifetime: number | null
    }
  }
  suggested_splits: SuggestedSplit[] // links to related scopes
}

// ─── Team fielding distribution dossier ─────────────────────────────────
//
// Mirror of /api/v1/teams/{team}/fielding/distribution. Spec:
// docs/internal/spec-distribution-stats.md §16.4 (backend) + §17.5 (frontend).
//
// Differs from the player-fielder dossier (§13/§14) in two ways:
//   1. `stumpings` is ALWAYS non-null at team grain (every senior team
//      has had a keeper at some point — for zero-stumping windows the
//      block still mounts with count=0, mean=0).
//   2. The Catches block carries 4 milestones (P=0/P≥3/P≥5/P≥7) — the
//      spec's wider milestone ladder for team grain. Run-outs and
//      stumpings keep the player-fielder 3-simple shape.

/** One fielding innings of a team in a distribution dossier. */
export interface TeamFieldingObservation {
  innings_id: number // the innings id
  match_id: number // the match id
  innings_number: number // the innings of the match
  date: string | null // the match date, as YYYY-MM-DD
  catches: number // catches taken, without substitutes' catches
  run_outs: number // run-outs made
  stumpings: number // stumpings made
  /** Substitute catches credited to the team in this innings (excluded from `catches`). */
  substitute_catches: number
  /** Total opposition wickets in the innings — denominator for the
   *  "X catches of Y wickets" sparkline tooltip on the Catches tab. */
  wickets_total: number
}

/** The distribution of a team's catches per fielding innings. */
export interface TeamFieldingCatchesBlock {
  total: number // catches over all innings
  mean_per_innings: number | null // catches per innings
  median: number | null // the median catches in an innings
  variance: number | null // the variance of catches per innings
  std: number | null // the standard deviation of catches per innings
  milestones: { // the chances of 0 catches, and of 3, 5 or 7 or more
    p_eq_0: ProbRecord
    p_geq_3: ProbRecord
    p_geq_5: ProbRecord
    p_geq_7: ProbRecord
  }
}

/** The distribution of a team's run-outs or stumpings per fielding innings. */
export interface TeamFieldingCountBlock {
  total: number // dismissals of this kind over all innings
  mean_per_innings: number | null // dismissals per innings
  median: number | null // the median dismissals in an innings
  variance: number | null // the variance of dismissals per innings
  std: number | null // the standard deviation of dismissals per innings
  milestones: { // the chances of 0, 1, and 2 or more in an innings
    p_eq_0: ProbRecord
    p_eq_1: ProbRecord
    p_geq_2: ProbRecord
  }
}

/** The distribution of a team's fielding innings over one window: catches, run-outs and stumpings. */
export interface TeamFieldingDossier {
  /** Note the field name divergence from player-fielder's `n_matches` /
   *  team-batting/bowling's `n_innings`. Distribution endpoint reports
   *  per-innings counts. */
  n_innings_fielded: number
  /** Total opposition wickets across the master sample — referenced in
   *  the dismissal-mix footer and the tooltip enrichment. */
  wickets_total: number
  /** Substitute catches in scope — surfaced for reconciliation; excluded from `catches.total`. */
  substitute_catches: number
  /** Max observation date in the scope (ISO YYYY-MM-DD). Drives the dormancy badge on the lifetime block. */
  last_match_date?: string | null
  observations: TeamFieldingObservation[] // each innings
  catches: TeamFieldingCatchesBlock // catches per innings
  run_outs: TeamFieldingCountBlock // run-outs per innings
  /** ALWAYS present at team grain. */
  stumpings: TeamFieldingCountBlock
}

/** A team's fielding distribution dossier from `/api/v1/teams/{team}/fielding/distribution`: lifetime and recent form. */
export interface TeamFieldingDistribution {
  team: string // the team
  scope: Record<string, string> // the filters in effect, without the empty ones
  lifetime: TeamFieldingDossier // all innings in scope
  form: { // the last 10 innings and the last 60 days, 6 months and year, with each window's deltas from lifetime
    last_10: TeamFieldingDossier
    last_60d: TeamFieldingDossier
    last_6mo: TeamFieldingDossier
    last_1yr: TeamFieldingDossier
    /** 12 entries: 4 windows × 3 metrics. */
    delta: {
      last_10_catches_mean_minus_lifetime: number | null
      last_10_run_outs_mean_minus_lifetime: number | null
      last_10_stumpings_mean_minus_lifetime: number | null
      last_60d_catches_mean_minus_lifetime: number | null
      last_60d_run_outs_mean_minus_lifetime: number | null
      last_60d_stumpings_mean_minus_lifetime: number | null
      last_6mo_catches_mean_minus_lifetime: number | null
      last_6mo_run_outs_mean_minus_lifetime: number | null
      last_6mo_stumpings_mean_minus_lifetime: number | null
      last_1yr_catches_mean_minus_lifetime: number | null
      last_1yr_run_outs_mean_minus_lifetime: number | null
      last_1yr_stumpings_mean_minus_lifetime: number | null
    }
  }
  suggested_splits: SuggestedSplit[] // links to related scopes
}

/** A bowler's record in one over of the innings, with the cohort's rates there. */
export interface BowlingOverDistributionEntry {
  over: number // the over, 1 to 20
  runs_conceded: number // runs conceded
  legal_balls: number // legal balls bowled
  wickets: number // wickets taken
  dots: number // dot balls
  boundaries: number // fours and sixes conceded
  /** Coarse legal-ball count per over (scope-key only, NOT narrowed by
   *  the six) — the over-mix histogram weight. `legal_balls` itself
   *  narrows under the six for the per-over economy bars; this stays
   *  coarse so the role-profile weighting keeps enough statistics.
   *  Tier-3 spec D-B2/D-B3. */
  mix_legal_balls: number
  /** Player's distinct innings-bowled count that touched this over
   *  (per playerscopestatsover.innings_bowled). Denominator for the
   *  player-side wickets-per-innings rate on the By Over chart. */
  innings_bowled: number
  // spec-mix-and-performance-charts.md §3.2 — per-bucket cohort
  // context for the By Over tab's Mix histogram + Performance-vs-
  // cohort chart. cohort_balls_share sums to 1.0 across the 20
  // entries. Null on buckets the cohort hasn't touched.
  cohort_balls_share: number | null // the cohort's share of balls in this over, 0 to 1
  cohort_economy: number | null // the cohort's runs per over in this over
  cohort_wickets_per_innings: number | null // the cohort's wickets per innings in this over
  /** Cohort boundaries (4s + 6s) conceded per over at this over,
   *  aggregated across every bowler at scope. Drives the new
   *  Boundaries/over panel on the By Over tab. User-asked 2026-05-22. */
  cohort_boundaries_per_over: number | null
}

/** How the bowling cohort was built: the player's over mix, and the cohort's size. */
export interface BowlingCohortMeta {
  match_dimension: 'over_mix' // what the cohort is weighted by
  over_mix: number[] // the player's share of balls in each of the 20 overs, summing to 1
  n_players: number // bowlers in the cohort
  n_balls_total: number // legal balls in the cohort
}

/** A bowler's career summary from `/api/v1/bowlers/{id}/summary`, each number with the cohort's average. */
export interface BowlingSummary {
  person_id: string // the bowler's person id
  name: string // the display name
  nationalities: NationalityEntry[] // the national teams played for, most matches first; empty for club-only players
  // Identity / formatted display fields stay flat.
  overs: string // overs bowled, as "123.4"
  best_figures: string | null // the best innings, as wickets/runs such as "4/21"; null with no wickets
  // Numeric fields envelope-wrapped per Phase 4.
  matches: MetricEnvelope // matches bowled in
  /** Squad appearances ("played") — headline matches count. `matches`
   *  above is matches BOWLED; the tile shows played + "bowled in N". */
  matches_played: MetricEnvelope
  innings: MetricEnvelope // innings bowled
  balls: MetricEnvelope // legal balls bowled
  runs_conceded: MetricEnvelope // runs given away
  wickets: MetricEnvelope // wickets taken
  four_wicket_hauls: MetricEnvelope // innings with 4 or more wickets
  fours_conceded: MetricEnvelope // fours hit off the bowler
  sixes_conceded: MetricEnvelope // sixes hit off the bowler
  boundaries_conceded: MetricEnvelope // fours and sixes hit off the bowler
  dots: MetricEnvelope // dot balls
  wides: MetricEnvelope // wides bowled
  noballs: MetricEnvelope // no-balls bowled
  maiden_overs: MetricEnvelope // overs with no runs conceded
  // Rate metrics (lower_better for econ/avg/SR; higher_better for dot_pct).
  average: MetricEnvelope // runs conceded per wicket
  economy: MetricEnvelope // runs conceded per over
  strike_rate: MetricEnvelope // balls per wicket
  dot_pct: MetricEnvelope // dot balls as a percentage of balls
  boundary_pct: MetricEnvelope // boundaries conceded as a percentage of balls
  wickets_per_over: MetricEnvelope // wickets per 6 balls
  balls_per_four: MetricEnvelope // balls per four conceded
  balls_per_six: MetricEnvelope // balls per six conceded
  balls_per_boundary: MetricEnvelope // balls per boundary conceded
  // Q6 per-innings rate envelopes (spec-player-baseline-parity.md
  // §3.3.3) — shipped session 1 in commit 55c890a. wickets_per_innings
  // is the bowling-side milestone-grade rate; maidens_per_innings
  // surfaces a low-volume but high-signal economy proxy.
  wickets_per_innings: MetricEnvelope // wickets per innings
  maidens_per_innings: MetricEnvelope // maiden overs per innings
  // spec-rate-vs-volume-audit.md §2.1 Group A — sibling rate to the
  // 4-fers volume tile.
  four_wicket_hauls_per_innings: MetricEnvelope // 4-wicket hauls per innings
  // Per-over distribution + cohort context.
  over_distribution: BowlingOverDistributionEntry[] // the record in each of the 20 overs
  cohort: BowlingCohortMeta | null // how the cohort was built; null when there is no cohort
  cohort_below_support: boolean // true when an over the player bowls has too few cohort balls, so the cohort rates are null
  cohort_cliff_buckets: number[] // the overs that have too few cohort balls
}

/** One innings of a bowler, from `/api/v1/bowlers/{id}/by-innings`. */
export interface BowlingInnings {
  match_id: number // the match id
  date: string // the match date, as YYYY-MM-DD
  team: string // the bowler's team
  opponent: string // the batting team
  tournament: string | null // the tournament's name; null for a match outside one
  overs: string // overs bowled, as "3.4"
  balls: number // legal balls bowled
  runs: number // runs conceded
  wickets: number // wickets taken
  economy: number | null // runs per over
  fours: number // fours conceded
  sixes: number // sixes conceded
  dots: number // dot balls
  maidens: number // maiden overs
  wides: number // wides bowled
  noballs: number // no-balls bowled
}

/** A bowler's record against one batter, from `/api/v1/bowlers/{id}/vs-batters`. */
export interface BatterMatchup {
  batter_id: string // the batter's person id
  batter_name: string // the batter's name
  balls: number // legal balls bowled to the batter
  runs_conceded: number // runs conceded to the batter
  wickets: number // times the bowler got the batter out
  average: number | null // runs per wicket; null with no wickets
  economy: number | null // runs per over
  strike_rate: number | null // balls per wicket; null with no wickets
  fours_conceded: number // fours hit by the batter
  sixes_conceded: number // sixes hit by the batter
  dots: number // dot balls
  dot_pct: number | null // dot balls as a percentage of balls
  balls_per_four: number | null // balls per four; null with no fours
  balls_per_six: number | null // balls per six; null with no sixes
  balls_per_boundary: number | null // balls per boundary; null with no boundaries
}

/** How a bowler takes wickets, from `/api/v1/bowlers/{id}/wickets`. */
export interface WicketAnalysis {
  total_wickets: number // wickets taken
  by_kind: Record<string, number> // wickets by kind, such as "caught" or "bowled"
  by_phase: Record<string, number> // wickets by phase: "powerplay", "middle", "death"
  by_over: { over_number: number; wickets: number }[] // wickets in each over
  top_victims: { // the batters the bowler got out most often, with the kinds of dismissal
    batter_id: string
    batter_name: string
    dismissals: number
    kinds: Record<string, number>
  }[]
}

/** The totals of one batter against one bowler. */
export interface HeadToHeadSummary {
  matches: number // matches where they met
  balls: number // legal balls the batter faced from the bowler
  runs: number // runs the batter scored off the bowler
  dismissals: number // times the bowler got the batter out
  average: number | null // runs per dismissal; null with no dismissals
  strike_rate: number | null // runs per 100 balls
  fours: number // fours hit
  sixes: number // sixes hit
  dots: number // dot balls
  dot_pct: number | null // dot balls as a percentage of balls
  balls_per_boundary: number | null // balls per boundary; null with no boundaries
}

/** One match where a batter faced a bowler. */
export interface HeadToHeadMatch {
  match_id: number // the match id
  date: string // the match date, as YYYY-MM-DD
  tournament: string | null // the tournament's name; null for a match outside one
  venue: string | null // the ground
  balls: number // legal balls faced from the bowler
  runs: number // runs scored off the bowler
  fours: number // fours hit
  sixes: number // sixes hit
  dismissed: boolean // true when the bowler got the batter out
  how_out: string | null // the kind of dismissal; null when not out to the bowler
}

/** A batter against a bowler, from `/api/v1/head-to-head/{batter}/{bowler}`: totals and splits. */
export interface HeadToHeadResponse {
  batter: { id: string; name: string; nationalities?: NationalityEntry[] } // the batter, with their national teams
  bowler: { id: string; name: string; nationalities?: NationalityEntry[] } // the bowler, with their national teams
  summary: HeadToHeadSummary // the totals
  dismissal_kinds: Record<string, number> // dismissals by kind, such as "caught" or "bowled"
  by_over: { over_number: number; balls: number; runs: number; wickets: number }[] // the totals in each over
  by_phase: { phase: string; balls: number; runs: number; wickets: number; strike_rate: number | null }[] // the totals in each phase
  by_season: { season: string; balls: number; runs: number; wickets: number; strike_rate: number | null }[] // the totals in each season
  by_match: HeadToHeadMatch[] // each match where they met
}

/**
 * A player's overview, built in the browser from the four discipline summaries.
 *
 * Composed player overview (client-side; see /players page).
 * The four sub-types already exist below — one nullable slot per discipline.
 * null = fetch 404'd (player doesn't bat/bowl/etc. in scope) or it failed.
 */
export interface PlayerProfile {
  batting: BattingSummary | null // the batting summary; null when absent
  bowling: BowlingSummary | null // the bowling summary; null when absent
  fielding: FieldingSummary | null // the fielding summary; null when absent
  keeping: KeepingSummary | null // the keeping summary; null when absent
}

// Fielding
/** A fielder's dismissals by the batting position of the batter out, with the cohort's share. */
export interface FieldingDismissalPositionEntry {
  bucket: number // the batting position bucket of the batter out, 1 to 10; 1 is the two openers merged
  catches: number // catches
  stumpings: number // stumpings
  run_outs: number // run-outs
  dismissals: number // all dismissals in this bucket
  // spec-mix-and-performance-charts.md §3.3 — per-bucket cohort
  // context for the By Dismissed Position tab. cohort partition is
  // keeper-binary (automatic from the player's is_keeper flag on the
  // /summary response). cohort_dismissals_share sums to 1.0 across
  // the 10 entries. Null on buckets the cohort hasn't touched.
  cohort_dismissals_share: number | null // the cohort's share of dismissals in this bucket, 0 to 1
  cohort_catches_per_match: number | null // the cohort's catches per match in this bucket
}

/** How the fielding cohort was built: keepers or outfielders, and the cohort's size. */
export interface FieldingCohortMeta {
  match_dimension: 'is_keeper' // what the cohort is split by
  is_keeper: 0 | 1 // 1 for the keepers' cohort, 0 for outfielders
  n_fielders: number // fielders in the cohort
  n_matches_total: number // matches fielded in the cohort
}

/** A fielder's career summary from `/api/v1/fielders/{id}/summary`, each number with the cohort's average. */
export interface FieldingSummary {
  person_id: string // the fielder's person id
  name: string // the display name
  nationalities: NationalityEntry[] // the national teams played for, most matches first; empty for club-only players
  // Numeric fields envelope-wrapped per Phase 4.
  matches: MetricEnvelope // squad appearances
  /** Activity-based denominator (XI ∧ opponent batted), narrows with the
   *  six. The By Dismissed Position tab's per-bucket catches/match divides
   *  by this (denominator B) rather than squad `matches`. */
  matches_fielded: MetricEnvelope
  catches: MetricEnvelope // catches, including caught-and-bowled
  stumpings: MetricEnvelope // stumpings
  run_outs: MetricEnvelope // run-outs
  caught_and_bowled: MetricEnvelope // caught-and-bowled, a part of `catches`
  total_dismissals: MetricEnvelope // all dismissals credited
  dismissals_per_match: MetricEnvelope // dismissals per match fielded
  catches_per_match: MetricEnvelope // catches per match fielded
  stumpings_per_match: MetricEnvelope // stumpings per match fielded
  run_outs_per_match: MetricEnvelope // run-outs per match fielded
  substitute_catches: MetricEnvelope // catches taken as a substitute fielder
  /** Tier 2 — innings where this person was assigned keeper. Used to gate the "Keeping" tab. */
  innings_kept: MetricEnvelope
  dismissal_position_distribution: FieldingDismissalPositionEntry[] // dismissals by the position of the batter out, 10 buckets
  cohort: FieldingCohortMeta | null // how the cohort was built; null when there is no cohort
  is_keeper: 0 | 1 // 1 when the player kept wicket in scope, which puts them in the keepers' cohort
}

// Keeping (Tier 2 fielding — wicketkeeper-specific stats)
/** How the keeping cohort was built: all keepers in scope. */
export interface KeepingCohortMeta {
  match_dimension: 'is_keeper' // what the cohort is split by
  is_keeper: 1 // always 1: the cohort is keepers
  n_keepers: number // keepers in the cohort
  n_matches_keeping: number // matches kept in the cohort
}

/** A keeper's career summary from `/api/v1/fielders/{id}/keeping/summary`. */
export interface KeepingSummary {
  person_id: string // the keeper's person id
  name: string // the display name
  innings_kept_by_confidence: { // innings kept, by how sure the keeper identification is
    definitive: number
    high: number
    medium: number
    low: number
  }
  // Numeric fields envelope-wrapped per Phase 4.
  innings_kept: MetricEnvelope // innings kept wicket
  stumpings: MetricEnvelope // stumpings
  keeping_catches: MetricEnvelope // catches taken while keeping
  run_outs_while_keeping: MetricEnvelope // run-outs made while keeping
  byes_conceded: MetricEnvelope // byes let through
  byes_per_innings: MetricEnvelope // byes per innings kept
  dismissals_while_keeping: MetricEnvelope // stumpings, catches and run-outs while keeping
  keeping_dismissals_per_innings: MetricEnvelope // dismissals per innings kept
  ambiguous_innings: MetricEnvelope // innings where the player was one of several possible keepers
  cohort: KeepingCohortMeta | null // the keeping cohort; null when the player kept no innings
}

/** A keeper's record in one season, from `/api/v1/fielders/{id}/keeping/by-season`. */
export interface KeepingSeason {
  season: string // the season, as "2023" or "2023/24"
  innings_kept: number // innings kept wicket
  stumpings: number // stumpings
  keeping_catches: number // catches taken while keeping
  run_outs_while_keeping: number // run-outs made while keeping
  byes_conceded: number // byes let through
  total_dismissals: number // stumpings, catches and run-outs while keeping
}

/** One innings a player kept wicket in, from `/api/v1/fielders/{id}/keeping/by-innings`. */
export interface KeepingInnings {
  match_id: number // the match id
  innings_number: number // the innings of the match
  date: string | null // the match date, as YYYY-MM-DD
  opponent: string // the batting team
  tournament: string | null // the tournament's name; null for a match outside one
  confidence: 'definitive' | 'high' | 'medium' | 'low' // how sure the keeper identification is
  method: string // how the keeper was identified
  stumpings: number // stumpings
  catches: number // catches
  run_outs: number // run-outs
  byes: number // byes let through
  total_dismissals: number // stumpings, catches and run-outs
}

/** An innings where the player may have kept wicket but no keeper was chosen, from `/api/v1/fielders/{id}/keeping/ambiguous`. */
export interface KeepingAmbiguousInnings {
  match_id: number // the match id
  innings_id: number // the innings id
  innings_number: number // the innings of the match
  date: string | null // the match date, as YYYY-MM-DD
  tournament: string | null // the tournament's name; null for a match outside one
  season: string // the season, as "2023" or "2023/24"
  fielding_team: string // the player's team, which fielded
  opponent: string // the batting team
  ambiguous_reason: string // why no keeper was chosen
  candidate_ids: string[] // the person ids that could have kept
  candidate_names: string[] // the names of `candidate_ids`, in the same order
}

/** One season row of a fielder's By Season table, from `/fielders/{id}/by-season`. */
export interface FieldingSeason {
  season: string // the season, as "2023" or "2023/24"
  catches: number // catches taken, excluding caught-and-bowled
  stumpings: number // stumpings made as wicketkeeper
  run_outs: number // run-outs the fielder was credited with
  caught_and_bowled: number // catches taken off the fielder's own bowling
  total: number // all dismissals the fielder took part in
  /** Matches the player appeared in this season — used to rescale
   *  the per-match cohort baseline back to per-season volume on the
   *  By Season chart (spec-player-baseline-parity.md §4.4). */
  matches: number
  // spec-rate-vs-volume-audit §2.1 Group B — per-match rates emitted
  // per /fielders/{id}/by-season row.
  dismissals_per_match?: number | null // dismissals per match; null when there are no matches
  catches_per_match?: number | null // catches per match; null when there are no matches
  stumpings_per_match?: number | null // stumpings per match; null when there are no matches
  run_outs_per_match?: number | null // run-outs per match; null when there are no matches
}

/** One phase row (powerplay, middle, death) of a fielder's dismissals. */
export interface FieldingPhase {
  phase: string // the phase name, such as "powerplay", "middle" or "death"
  overs: string // the overs the phase covers, as text
  catches: number // catches taken in the phase
  stumpings: number // stumpings in the phase
  run_outs: number // run-outs in the phase
  caught_and_bowled: number // caught-and-bowled dismissals in the phase
  total: number // all dismissals in the phase
  // spec-rate-vs-volume-audit §2.1 Group D3: per-match rates plus
  // the matches scalar denominator (constant across phases by design
  // — fielding is match-grain, not phase-grain).
  matches?: number // matches in scope; the same on every phase row
  total_per_match?: number | null // dismissals in the phase per match
  catches_per_match?: number | null // catches in the phase per match
  stumpings_per_match?: number | null // stumpings in the phase per match
  run_outs_per_match?: number | null // run-outs in the phase per match
}

/** A batter whom a fielder dismissed, with the count of each kind. */
export interface FieldingVictim {
  batter_id: string // the batter's person id
  batter_name: string // the batter's name
  catches: number // times the fielder caught this batter
  stumpings: number // times the fielder stumped this batter
  run_outs: number // times the fielder ran this batter out
  total: number // all dismissals of this batter by the fielder
}

/**
 * A batter whom a bowler dismissed, with the count of each kind.
 *
 * /bowlers/{id}/victims — full list of batters this bowler dismissed
 * at scope, sorted by total dismissals. Mirrors FieldingVictim with
 * bowling-side dismissal kinds. User-asked 2026-05-22.
 */
export interface BowlingVictim {
  batter_id: string // the batter's person id
  batter_name: string // the batter's name
  dismissals: number // all dismissals of this batter by the bowler
  bowled: number // times bowled
  caught: number // times caught
  lbw: number // times leg before wicket
  stumped: number // times stumped
  hit_wicket: number // times hit wicket
  caught_and_bowled: number // times caught by the bowler
}

/** One innings in which a fielder took part in a dismissal. */
export interface FieldingInnings {
  match_id: number // the match id
  date: string // the match date
  opponent: string | null // the batting team
  tournament: string | null // the tournament; null for a match outside one
  catches: number // catches taken in the innings
  stumpings: number // stumpings in the innings
  run_outs: number // run-outs in the innings
  total: number // all dismissals in the innings
}

/**
 * One match in a list of matches, with its result and both scores.
 *
 * Matches & scorecards
 */
export interface MatchListItem {
  match_id: number // the match id
  date: string | null // the first day of the match; null when unknown
  team1: string // the first team
  team2: string // the second team
  venue: string | null // the ground; null when unknown
  city: string | null // the city; null when unknown
  tournament: string | null // the tournament; null for a match outside one
  season: string | null // the season, as "2023" or "2023/24"
  winner: string | null // the winning team; null for a tie or no result
  result_text: string // the result in words
  team1_score: string | null // the first team's score as text; null when it did not bat
  team2_score: string | null // the second team's score as text; null when it did not bat
}

/** One batter's line on a scorecard. */
export interface ScorecardBatter {
  person_id: string | null // the batter's person id; null when unknown
  name: string // the batter's name
  dismissal: string // how the batter was out, in scorecard words
  /** Bowler credited with the wicket — null for not-out, run-out, retired, etc. */
  dismissal_bowler_id: string | null
  /** Fielder(s) involved in the dismissal (from fielding_credit). */
  dismissal_fielder_ids: string[]
  runs: number // runs scored
  balls: number // balls faced
  fours: number // fours hit
  sixes: number // sixes hit
  strike_rate: number // runs per 100 balls
}

/** One bowler's line on a scorecard. */
export interface ScorecardBowler {
  person_id: string | null // the bowler's person id; null when unknown
  name: string // the bowler's name
  overs: string // overs bowled, as "3.4"
  maidens: number // maiden overs
  runs: number // runs conceded
  wickets: number // wickets taken
  econ: number // runs conceded per over
  wides: number // wides bowled
  noballs: number // no-balls bowled
}

/** The extras of one innings, by kind. */
export interface ScorecardExtras {
  byes: number // byes
  legbyes: number // leg byes
  wides: number // wides
  noballs: number // no-balls
  penalty: number // penalty runs
  total: number // all extras
}

/** One wicket in an innings' fall of wickets. */
export interface ScorecardFallOfWicket {
  wicket: number // the wicket number, from 1
  score: number // the team's score when the wicket fell
  batter: string // the batter who was out
  over_ball: string // the over and ball of the wicket, overs from 1, as "12.3"
}

/** The runs and wickets of one over, and the running total. */
export interface OverProgression {
  over: number // the over number, from 1
  runs: number // runs scored in the over
  wickets: number // wickets that fell in the over
  cumulative: number // the team's total at the end of the over
}

/** One innings of a scorecard: totals, batting, bowling, extras and the keeper. */
export interface ScorecardInnings {
  innings_number: number // the innings number within the match
  team: string // the batting team
  is_super_over: boolean // true for a super-over innings
  label: string // the heading to show for the innings
  total_runs: number // the team's total
  wickets: number // wickets lost
  overs: string // overs faced, as "19.4"
  run_rate: number // runs per over
  batting: ScorecardBatter[] // the batters, in batting order
  did_not_bat: string[] // names of the players who did not bat
  extras: ScorecardExtras // the extras, by kind
  fall_of_wickets: ScorecardFallOfWicket[] // the wickets, in order
  bowling: ScorecardBowler[] // the bowlers' lines
  by_over: OverProgression[] // runs and wickets over by over
  /** Tier 2 — the wicketkeeper for this innings (of the FIELDING team).
   *  Null for super-overs; ambiguous innings have person_id=null plus
   *  candidate_ids/names + ambiguous_reason. */
  keeper: ScorecardKeeper | null
}

/** The match details at the top of a scorecard: teams, ground, toss, result and officials. */
export interface ScorecardInfo {
  match_id: number // the match id
  teams: string[] // the two teams
  venue: string | null // the ground; null when unknown
  city: string | null // the city; null when unknown
  dates: string[] // the days of the match
  tournament: string | null // the tournament; null for a match outside one
  season: string | null // the season, as "2023" or "2023/24"
  match_number: number | null // the match number within the event; null when not given
  stage: string | null // the stage, such as "Final"; null for a league match
  toss_winner: string | null // the team that won the toss
  toss_decision: string | null // what the toss winner chose, "bat" or "field"
  result_text: string // the result in words
  method: string | null // the method that decided the result, such as "D/L"; null when none
  player_of_match: string[] // names of the players of the match
  officials: Record<string, string[]> | null // officials' names by role; null when not given
  gender: string | null // "male" or "female"
  team_type: string | null // "international" or "club"
}

/** A match scorecard: its details and its innings. */
export interface Scorecard {
  info: ScorecardInfo // the match details
  innings: ScorecardInnings[] // the innings, in order, super overs included
}

/**
 * One ball of an innings, for the innings grid.
 *
 * Innings grid (per-delivery visualization)
 */
export interface InningsGridDelivery {
  over_ball: string // the over and ball, from 1, as "12.3"
  bowler: string // the bowler's name
  bowler_id: string | null // the bowler's person id; null when unknown
  bowler_index: number | null // the bowler's index in the innings' `bowlers`
  batter: string // the striker's name
  batter_id: string | null // the striker's person id; null when unknown
  batter_index: number // the striker's index in the innings' `batters`
  non_striker: string // the non-striker's name
  non_striker_index: number | null // the non-striker's index in the innings' `batters`
  runs_batter: number // runs off the bat
  runs_extras: number // extras on this ball
  runs_total: number // all runs on this ball
  extras_wides: number // wide runs
  extras_noballs: number // no-ball runs
  extras_byes: number // byes
  extras_legbyes: number // leg byes
  cumulative_runs: number // the team's total after this ball
  cumulative_wickets: number // wickets fallen after this ball
  wicket_kind: string | null // the kind of dismissal; null when no wicket fell
  wicket_player_out: string | null // the name of the batter out; null when no wicket fell
  wicket_player_out_index: number | null // the index of the batter out in `batters`; null when no wicket fell
  wicket_text: string | null // the dismissal in scorecard words; null when no wicket fell
}

/** One innings of the innings grid: its batters and bowlers in order of appearance, and every ball. */
export interface InningsGridInnings {
  innings_number: number // the innings number within the match
  team: string // the batting team
  batters: string[] // batters' names, in order of first appearance
  batter_ids: (string | null)[] // person ids, in the same order as `batters`
  bowlers: string[] // bowlers' names, in order of first appearance
  bowler_ids: (string | null)[] // person ids, in the same order as `bowlers`
  deliveries: InningsGridDelivery[] // every ball, in order
  total_balls: number // the number of deliveries, extras included
  total_runs: number // the team's total
  total_wickets: number // wickets lost
}

/** The innings grid of a match: every ball of every innings. */
export interface InningsGridResponse {
  match_id: number // the match id
  innings: InningsGridInnings[] // the innings, in order
}

// ============================================================
// Team stats — batting / bowling / fielding / partnerships
// (see docs/internal/spec-team-stats.md)
// ============================================================

/** A team's innings total, with the match it came from. */
export interface TeamInningsTotal {
  runs: number // the total
  match_id: number // the match id
  innings_number: number // the innings number within the match
}

/** A team's batting in scope; each metric comes with the scope average and the difference from it. */
export interface TeamBattingSummary {
  team: string // the team
  innings_batted: MetricEnvelope // innings batted
  total_runs: MetricEnvelope // runs scored
  legal_balls: MetricEnvelope // legal balls faced
  run_rate: MetricEnvelope // runs per over
  boundary_pct: MetricEnvelope // percent of legal balls hit for four or six
  dot_pct: MetricEnvelope // percent of legal balls with no run
  fours: MetricEnvelope // fours hit
  sixes: MetricEnvelope // sixes hit
  fifties: MetricEnvelope // individual scores of 50 to 99
  hundreds: MetricEnvelope // individual scores of 100 or more
  avg_innings_total: MetricEnvelope // the average innings total
  avg_1st_innings_total: MetricEnvelope // the average total when batting first
  avg_2nd_innings_total: MetricEnvelope // the average total when batting second
  highest_total: TeamInningsTotal | null // the highest total; null when the team did not bat
  lowest_all_out_total: TeamInningsTotal | null // the lowest total when all out; null when never all out
}

/** One season of a team's batting. */
export interface TeamBattingSeason {
  season: string // the season, as "2023" or "2023/24"
  innings_batted: number // innings batted
  total_runs: number // runs scored
  legal_balls: number // legal balls faced
  avg_innings_total: number | null // the average innings total
  run_rate: number | null // runs per over
  boundary_pct: number | null // percent of legal balls hit for four or six
  dot_pct: number | null // percent of legal balls with no run
  fours: number // fours hit
  sixes: number // sixes hit
  highest_total: number // the highest innings total
  lowest_all_out_total: number | null // the lowest total when all out; null when never all out
}

/** A team's batting in one phase (powerplay, middle, death). */
export interface TeamBattingPhase {
  phase: string // the phase name, such as "powerplay"
  overs_range: number[] // the first and last over of the phase
  runs: number // runs scored in the phase
  balls: number // legal balls faced in the phase
  run_rate: MetricEnvelope // runs per over, with the scope average
  wickets_lost: number // wickets lost in the phase
  boundary_pct: MetricEnvelope // percent of balls hit for four or six, with the scope average
  dot_pct: MetricEnvelope // percent of balls with no run, with the scope average
  fours: number // fours hit
  sixes: number // sixes hit
}

/**
 * A team's batting in one innings of the match (batting first or second).
 *
 * Per-innings_number batting band — sibling of TeamBattingPhase from
 * /api/v1/teams/{team}/batting/by-inning. Spec: spec-inning-split.md §3.2.
 */
export interface TeamBattingInning {
  inning_no: number // 0 when batting first, 1 when batting second
  label: string // "1st innings" or "2nd innings"
  runs: number // runs scored
  balls: number // legal balls faced
  run_rate: MetricEnvelope // runs per over, with the scope average
  wickets_lost: number // wickets lost
  boundary_pct: MetricEnvelope // percent of balls hit for four or six, with the scope average
  dot_pct: MetricEnvelope // percent of balls with no run, with the scope average
  fours: number // fours hit
  sixes: number // sixes hit
}

/** One of a team's leading run scorers in scope. */
export interface TeamTopBatter {
  person_id: string // the batter's person id
  name: string // the batter's name
  runs: number // runs scored for the team
  balls: number // balls faced
  strike_rate: number | null // runs per 100 balls; null when no balls faced
  fours: number // fours hit
  sixes: number // sixes hit
  innings: number // innings batted
}

/** A team's bowling in scope; each metric comes with the scope average and the difference from it. */
export interface TeamBowlingSummary {
  team: string // the team
  innings_bowled: MetricEnvelope // innings in the field
  matches: MetricEnvelope // matches played
  runs_conceded: MetricEnvelope // runs conceded
  legal_balls: MetricEnvelope // legal balls bowled
  overs: MetricEnvelope // overs bowled
  wickets: MetricEnvelope // wickets taken
  economy: MetricEnvelope // runs conceded per over
  strike_rate: MetricEnvelope // balls per wicket
  average: MetricEnvelope // runs conceded per wicket
  dot_pct: MetricEnvelope // percent of legal balls with no run
  fours_conceded: MetricEnvelope // fours conceded
  sixes_conceded: MetricEnvelope // sixes conceded
  boundaries_conceded: MetricEnvelope // fours and sixes conceded
  wides: MetricEnvelope // wides bowled
  noballs: MetricEnvelope // no-balls bowled
  wides_per_match: MetricEnvelope // wides per match
  noballs_per_match: MetricEnvelope // no-balls per match
  avg_opposition_total: MetricEnvelope // the opponents' average innings total
  worst_conceded: TeamInningsTotal | null // the highest total conceded; null when none
  best_defence: { runs: number; match_id: number } | null // the lowest score of a failed chase against the team; null when none
}

/** One season of a team's bowling. */
export interface TeamBowlingSeason {
  season: string // the season, as "2023" or "2023/24"
  innings_bowled: number // innings in the field
  runs_conceded: number // runs conceded
  legal_balls: number // legal balls bowled
  overs: number // overs bowled
  wickets: number // wickets taken
  economy: number | null // runs conceded per over
  avg_opposition_total: number | null // the opponents' average innings total
  dot_pct: number | null // percent of legal balls with no run
  boundaries_conceded: number // fours and sixes conceded
  worst_conceded: number // the highest total conceded
}

/** A team's bowling in one innings of the match (bowling first or second). */
export interface TeamBowlingInning {
  inning_no: number // the match innings: 0 for the first, 1 for the second
  label: string // "1st innings" or "2nd innings"
  runs_conceded: number // runs conceded
  balls: number // legal balls bowled
  economy: MetricEnvelope // runs conceded per over, with the scope average
  wickets: number // wickets taken
  boundary_pct: MetricEnvelope // percent of balls hit for four or six, with the scope average
  dot_pct: MetricEnvelope // percent of balls with no run, with the scope average
  fours_conceded: number // fours conceded
  sixes_conceded: number // sixes conceded
}

/** A team's bowling in one phase (powerplay, middle, death). */
export interface TeamBowlingPhase {
  phase: string // the phase name, such as "powerplay"
  overs_range: number[] // the first and last over of the phase
  runs_conceded: number // runs conceded in the phase
  balls: number // legal balls bowled in the phase
  economy: MetricEnvelope // runs conceded per over, with the scope average
  wickets: number // wickets taken in the phase
  boundary_pct: MetricEnvelope // percent of balls hit for four or six, with the scope average
  dot_pct: MetricEnvelope // percent of balls with no run, with the scope average
  fours_conceded: number // fours conceded
  sixes_conceded: number // sixes conceded
}

/** One of a team's leading wicket takers in scope. */
export interface TeamTopBowler {
  person_id: string // the bowler's person id
  name: string // the bowler's name
  wickets: number // wickets taken for the team
  runs_conceded: number // runs conceded
  balls: number // legal balls bowled
  overs: number // overs bowled
  economy: number | null // runs conceded per over; null when no balls bowled
  average: number | null // runs conceded per wicket; null when no wickets
  strike_rate: number | null // balls per wicket; null when no wickets
  innings: number // innings bowled in
}

/** A team's fielding in scope; each metric comes with the scope average and the difference from it. */
export interface TeamFieldingSummary {
  team: string // the team
  matches: MetricEnvelope // matches played
  catches: MetricEnvelope // catches taken
  caught_and_bowled: MetricEnvelope // caught-and-bowled dismissals
  stumpings: MetricEnvelope // stumpings
  run_outs: MetricEnvelope // run-outs
  total_dismissals_contributed: MetricEnvelope // dismissals in which a fielder took part
  catches_per_match: MetricEnvelope // catches per match
  stumpings_per_match: MetricEnvelope // stumpings per match
  run_outs_per_match: MetricEnvelope // run-outs per match
}

/** A team's fielding in one innings of the match (fielding first or second). */
export interface TeamFieldingInning {
  inning_no: number // the match innings: 0 for the first, 1 for the second
  label: string // "1st innings" or "2nd innings"
  matches: number // matches with this innings
  catches: number // catches taken
  caught_and_bowled: number // caught-and-bowled dismissals
  stumpings: number // stumpings
  run_outs: number // run-outs
  total_dismissals_contributed: number // dismissals in which a fielder took part
  catches_per_match: MetricEnvelope // catches per match, with the scope average
  stumpings_per_match: MetricEnvelope // stumpings per match, with the scope average
  run_outs_per_match: MetricEnvelope // run-outs per match, with the scope average
}

/** A team's partnerships in one innings of the match (first or second). */
export interface TeamPartnershipsInning {
  inning_no: number // the match innings: 0 for the first, 1 for the second
  label: string // "1st innings" or "2nd innings"
  n: MetricEnvelope // the number of partnerships, with the scope average
  avg_runs: MetricEnvelope // average runs per partnership, with the scope average
  avg_balls: number | null // average balls per partnership
  best_runs: number // the highest partnership
}

/** Aggregate partnership stats for a team in the current filter scope.
 *  Returned by /api/v1/teams/{team}/partnerships/summary. */
export interface TeamPartnershipsSummary {
  team: string // the team
  side: 'batting' | 'bowling' // the team's partnerships, or those of its opponents against it
  total: MetricEnvelope // the number of partnerships
  count_50_plus: MetricEnvelope // partnerships of 50 runs or more
  count_100_plus: MetricEnvelope // partnerships of 100 runs or more
  avg_runs: MetricEnvelope // average runs per partnership
  /** The highest partnership, with its two batters; null when there are none. */
  highest: {
    runs: number
    balls: number
    match_id: number
    date: string | null
    batter1: { person_id: string; name: string | null }
    batter2: { person_id: string; name: string | null }
  } | null
  /** The pair with the most runs together, with their count and best stand; null when there are none. */
  best_pair: {
    batter1: { person_id: string; name: string }
    batter2: { person_id: string; name: string }
    n: number
    total_runs: number
    best_runs: number
  } | null
}

/** Bundle fetched for each column in the Teams → Compare tab. Each
 *  sub-fetch is wrapped in `.catch(() => null)` so a single 404 or
 *  scope-empty discipline doesn't sink the whole column.
 *
 *  Includes both the summary endpoints (top-of-column rows) and the
 *  expansion-row data (phase bands under batting/bowling, partnership-
 *  by-wicket sub-rows, season-trajectory inputs). All fetched in
 *  parallel as a single composer call so the grid only waits once. */
export interface TeamProfile {
  summary: TeamSummary | null // results and toss; null when the fetch failed
  batting: TeamBattingSummary | null // batting summary; null when the fetch failed
  bowling: TeamBowlingSummary | null // bowling summary; null when the fetch failed
  fielding: TeamFieldingSummary | null // fielding summary; null when the fetch failed
  partnerships: TeamPartnershipsSummary | null // partnerships summary; null when the fetch failed
  batting_by_phase: { phases: TeamBattingPhase[] } | null // batting by phase; null when the fetch failed
  bowling_by_phase: { phases: TeamBowlingPhase[] } | null // bowling by phase; null when the fetch failed
  /** Partnerships by wicket; null when the fetch failed. */
  partnerships_by_wicket: { team: string; side: 'batting' | 'bowling'; by_wicket: PartnershipByWicket[] } | null
  batting_by_season: { seasons: TeamBattingSeason[] } | null // batting by season; null when the fetch failed
  bowling_by_season: { seasons: TeamBowlingSeason[] } | null // bowling by season; null when the fetch failed
  fielding_by_season: { seasons: TeamFieldingSeason[] } | null // fielding by season; null when the fetch failed
  /** Partnerships by season; null when the fetch failed. */
  partnerships_by_season: { team: string; side: 'batting' | 'bowling'; by_season: TeamPartnershipsSeason[] } | null
}

/** Per-season partnership aggregates returned by
 *  /teams/{team}/partnerships/by-season + /scope/averages/partnerships/by-season. */
export interface TeamPartnershipsSeason {
  season: string // the season, as "2023" or "2023/24"
  total: number // the number of partnerships
  count_50_plus: number // partnerships of 50 runs or more
  count_100_plus: number // partnerships of 100 runs or more
  avg_runs: number | null // average runs per partnership
  best_runs: number | null // the highest partnership
}

// ─── Scope averages — pool-weighted league baselines ─────────────────
// The "average team" counterpart to the team interfaces above. Same
// fields where applicable; per-team identity-bearing stuff (captain,
// home ground, list of keepers, "best pair") is dropped or replaced
// with scope-level identity (highest team total carries the team
// that scored it; league's record partnership at each wicket carries
// pair identity).
//
// Rendered in the Teams > Compare tab's "Average" column —
// see TeamCompareGrid + ScopeAverageColumn.

/** Match results across the whole scope, for the Average column. */
export interface ScopeSummary {
  matches: number // matches in scope
  decided: number // matches with a winner
  ties: number // tied matches
  no_results: number // matches with no result
  toss_decided: number // matches with a known toss winner
  bat_first_wins: number // matches won by the team batting first
  field_first_wins: number // matches won by the team fielding first
  bat_first_win_pct: number | null // percent of decided matches won batting first
}

/**
 * Batting across the whole scope, for the Average column.
 *
 * /scope/averages/* response types.
 *
 * IMPORTANT — type-API contract:
 * Per spec-avg-column-per-innings.md Commit 2 (2026-04-26), these
 * types deliberately OMIT `innings_batted` / `innings_bowled` —
 * the avg endpoint drops those fields because they'd always be 1
 * under per-innings semantic. If you bring them back to the
 * backend response, add them back here too. The reverse is also
 * true: any field you remove from the backend response MUST be
 * removed from these types so consumers compile-fail rather than
 * silently fall through `?? 0` and produce wrong UI gates (the
 * 2026-04-27 empty-section bug).
 */
export interface ScopeBattingSummary {
  total_runs: number // runs scored in scope
  legal_balls: number // legal balls faced
  run_rate: number | null // runs per over
  boundary_pct: number | null // percent of legal balls hit for four or six
  dot_pct: number | null // percent of legal balls with no run
  fours: number // fours hit
  sixes: number // sixes hit
  avg_1st_innings_total: number | null // the average first-innings total
  avg_2nd_innings_total: number | null // the average second-innings total
  /** The highest team total in scope, with the team that made it; null when there are none. */
  highest_total: {
    runs: number
    team: string | null
    match_id: number
    innings_number: number
  } | null
}

/** One season of batting across the whole scope. */
export interface ScopeBattingSeason {
  season: string // the season, as "2023" or "2023/24"
  total_runs: number // runs scored
  legal_balls: number // legal balls faced
  run_rate: number | null // runs per over
  boundary_pct: number | null // percent of legal balls hit for four or six
  dot_pct: number | null // percent of legal balls with no run
  fours: number // fours hit
  sixes: number // sixes hit
}

/** Bowling across the whole scope, for the Average column. */
export interface ScopeBowlingSummary {
  matches: number // matches in scope
  runs_conceded: number // runs conceded
  legal_balls: number // legal balls bowled
  overs: number // overs bowled
  wickets: number // wickets taken
  economy: number | null // runs conceded per over
  strike_rate: number | null // balls per wicket
  average: number | null // runs conceded per wicket
  dot_pct: number | null // percent of legal balls with no run
  fours_conceded: number // fours conceded
  sixes_conceded: number // sixes conceded
  boundaries_conceded: number // fours and sixes conceded
  wides: number // wides bowled
  noballs: number // no-balls bowled
  wides_per_match: number | null // wides per match
  noballs_per_match: number | null // no-balls per match
}

/** One season of bowling across the whole scope. */
export interface ScopeBowlingSeason {
  season: string // the season, as "2023" or "2023/24"
  runs_conceded: number // runs conceded
  legal_balls: number // legal balls bowled
  overs: number // overs bowled
  wickets: number // wickets taken
  economy: number | null // runs conceded per over
  dot_pct: number | null // percent of legal balls with no run
  boundaries_conceded: number // fours and sixes conceded
}

/** Fielding across the whole scope, for the Average column. */
export interface ScopeFieldingSummary {
  matches: number // matches in scope
  catches: number // catches taken
  caught_and_bowled: number // caught-and-bowled dismissals
  stumpings: number // stumpings
  run_outs: number // run-outs
  total_dismissals_contributed: number // dismissals in which a fielder took part
  catches_per_match: number | null // catches per match
  stumpings_per_match: number | null // stumpings per match
  run_outs_per_match: number | null // run-outs per match
}

/** One season of fielding across the whole scope. */
export interface ScopeFieldingSeason {
  season: string // the season, as "2023" or "2023/24"
  matches: number // matches in the season
  catches: number // catches taken
  stumpings: number // stumpings
  run_outs: number // run-outs
  total_dismissals_contributed: number // dismissals in which a fielder took part
  catches_per_match: number | null // catches per match
  stumpings_per_match: number | null // stumpings per match
  run_outs_per_match: number | null // run-outs per match
}

/** Partnerships across the whole scope, for the Average column. */
export interface ScopePartnershipsSummary {
  total: number // the number of partnerships
  count_50_plus: number // partnerships of 50 runs or more
  count_100_plus: number // partnerships of 100 runs or more
  avg_runs: number | null // average runs per partnership
  /** League-wide highest single partnership in scope — has identity
   *  (specific pair, match, team that scored it). */
  highest: {
    runs: number
    balls: number
    match_id: number
    date: string | null
    team: string | null
    batter1: { person_id: string; name: string | null }
    batter2: { person_id: string; name: string | null }
  } | null
}

/** Flat-shape phase rows from /scope/averages/batting/by-phase
 *  (scope-side endpoint kept flat — it IS the baseline, no
 *  delta-against-itself to compute). The team-side
 *  TeamBattingPhase has envelope-wrapped fields. */
export interface ScopeBattingPhaseFlat {
  phase: string // the phase name, such as "powerplay"
  overs_range: number[] // the first and last over of the phase
  runs: number // runs scored in the phase
  balls: number // legal balls faced in the phase
  run_rate: number | null // runs per over
  wickets_lost: number // wickets lost in the phase
  boundary_pct: number | null // percent of balls hit for four or six
  dot_pct: number | null // percent of balls with no run
  fours: number // fours hit
  sixes: number // sixes hit
}

/** Bowling across the whole scope in one phase, with plain numbers. */
export interface ScopeBowlingPhaseFlat {
  phase: string // the phase name, such as "powerplay"
  overs_range: number[] // the first and last over of the phase
  runs_conceded: number // runs conceded in the phase
  balls: number // legal balls bowled in the phase
  economy: number | null // runs conceded per over
  wickets: number // wickets taken in the phase
  boundary_pct: number | null // percent of balls hit for four or six
  dot_pct: number | null // percent of balls with no run
  fours_conceded: number // fours conceded
  sixes_conceded: number // sixes conceded
}

/** Partnerships across the whole scope at one wicket, with the record stand. */
export interface ScopePartnershipByWicket {
  wicket_number: number // the wicket the partnership was for, from 1
  n: number // the number of partnerships
  avg_runs: number | null // average runs per partnership
  avg_balls: number | null // average balls per partnership
  best_runs: number | null // the highest partnership
  /** League's record partnership at this wicket position — carries
   *  pair + match identity (different from the team-side endpoint:
   *  no team filter, so the holder can be any team in scope). */
  best_partnership: {
    partnership_id: number
    match_id: number
    date: string | null
    season: string | null
    tournament: string | null
    team: string | null
    runs: number
    balls: number
    batter1: { person_id: string; name: string | null }
    batter2: { person_id: string; name: string | null }
  } | null
}

/** One season of partnerships across the whole scope. */
export interface ScopePartnershipsSeason {
  season: string // the season, as "2023" or "2023/24"
  total: number // the number of partnerships
  count_50_plus: number // partnerships of 50 runs or more
  count_100_plus: number // partnerships of 100 runs or more
  avg_runs: number | null // average runs per partnership
  best_runs: number | null // the highest partnership
}

/** Bundle fetched for the Average column in the Teams > Compare tab.
 *  Mirrors TeamProfile shape so columns can be rendered side-by-side. */
export interface ScopeAverageProfile {
  summary: ScopeSummary | null // match results; null when the fetch failed
  batting: ScopeBattingSummary | null // batting summary; null when the fetch failed
  bowling: ScopeBowlingSummary | null // bowling summary; null when the fetch failed
  fielding: ScopeFieldingSummary | null // fielding summary; null when the fetch failed
  partnerships: ScopePartnershipsSummary | null // partnerships summary; null when the fetch failed
  batting_by_phase: { by_phase: ScopeBattingPhaseFlat[] } | null // batting by phase; null when the fetch failed
  bowling_by_phase: { by_phase: ScopeBowlingPhaseFlat[] } | null // bowling by phase; null when the fetch failed
  partnerships_by_wicket: { by_wicket: ScopePartnershipByWicket[] } | null // partnerships by wicket; null when the fetch failed
  batting_by_season: { by_season: ScopeBattingSeason[] } | null // batting by season; null when the fetch failed
  bowling_by_season: { by_season: ScopeBowlingSeason[] } | null // bowling by season; null when the fetch failed
  fielding_by_season: { by_season: ScopeFieldingSeason[] } | null // fielding by season; null when the fetch failed
  partnerships_by_season: { by_season: ScopePartnershipsSeason[] } | null // partnerships by season; null when the fetch failed
}

// ─── Player-cohort by-season + by-phase (spec-player-baseline-parity.md §3.2) ───
// Position-mix-weighted (batting), over-mix-weighted (bowling), or
// keeper-binary (fielding) cohort baselines at by-season + by-phase
// granularity. Each row's metric fields are null when the per-bucket
// sample minimums failed for that season/phase (Q4 — chart renders a
// gap, chip subtitle suppresses).

/** One season of the batting cohort baseline, weighted by the player's mix of batting positions. */
export interface ScopePlayerBattingSeason {
  season: string // the season, as "2023" or "2023/24"
  mix: number[] // the player's share of innings at each of the 10 batting-position buckets
  n_players: number // players in the cohort
  n_innings: number // cohort innings
  below_support: boolean // true when a bucket the player uses has too few innings; the rates are then null
  cliff_buckets: number[] // the position buckets that have too few innings
  total_runs: number | null // cohort runs
  run_rate: number | null // runs per over
  strike_rate: number | null // runs per 100 balls
  boundary_pct: number | null // percent of balls hit for four or six
  dot_pct: number | null // percent of balls with no run
  balls_per_four: number | null // balls per four
  balls_per_boundary: number | null // balls per four or six
  sixes_per_innings: number | null // sixes per innings
  fours_per_innings: number | null // fours per innings
  boundaries_per_innings: number | null // fours and sixes per innings
  // spec-rate-vs-volume-audit §2.1 Group C — scope-flat per-season
  // rates aggregated from the parent playerscopestats table.
  runs_per_innings: number | null // runs per innings
  hundreds_per_innings: number | null // hundreds per innings
  fifties_per_innings: number | null // fifties per innings
  thirties_per_innings: number | null // scores of 30 to 49 per innings
  ducks_per_innings: number | null // ducks per innings
}

/** One phase of the batting cohort baseline, weighted by the player's mix of batting positions in that phase. */
export interface ScopePlayerBattingPhase {
  phase: string // "powerplay", "middle" or "death"
  phase_bucket: number // 1 for powerplay, 2 for middle, 3 for death
  n_players: number // players in the cohort
  n_innings_in_phase: number // cohort innings in the phase
  below_support: boolean // true when a bucket the player uses has too few innings; the rates are then null
  strike_rate: number | null // runs per 100 balls
  dot_pct: number | null // percent of balls with no run
  boundary_pct: number | null // percent of balls hit for four or six
  balls_per_four: number | null // balls per four
  balls_per_boundary: number | null // balls per four or six
  runs_per_innings_in_phase: number | null // runs per innings in the phase
  sixes_per_innings: number | null // sixes per innings in the phase
  fours_per_innings: number | null // fours per innings in the phase
  boundaries_per_innings: number | null // fours and sixes per innings in the phase
}

/** One season of the bowling cohort baseline, weighted by the player's mix of overs bowled. */
export interface ScopePlayerBowlingSeason {
  season: string // the season, as "2023" or "2023/24"
  mix: number[] // the player's share of balls in each over, 1 to 20
  n_players: number // players in the cohort
  n_balls: number // cohort balls
  below_support: boolean // true when an over the player bowls has too few balls; the rates are then null
  cliff_overs: number[] // the overs that have too few balls
  economy: number | null // runs conceded per over
  bowling_avg: number | null // runs conceded per wicket
  strike_rate: number | null // balls per wicket
  dot_pct: number | null // percent of balls with no run
  boundary_pct: number | null // percent of balls hit for four or six
  balls_per_boundary: number | null // balls per four or six
  wickets_per_over: number | null // wickets per over
  wickets_per_innings: number | null // wickets per innings bowled
  maidens_per_innings: number | null // maidens per innings bowled
  // spec-rate-vs-volume-audit §2.1 Group C — scope-flat per-season
  // four-wicket-haul rate.
  four_wicket_hauls_per_innings: number | null // hauls of four or more wickets per innings bowled
}

/** One phase of the bowling cohort baseline, weighted by the player's mix of overs in that phase. */
export interface ScopePlayerBowlingPhase {
  phase: string // "powerplay", "middle" or "death"
  phase_bucket: number // 1 for powerplay, 2 for middle, 3 for death
  mix: number[] // the player's share of balls in each over of `overs`
  overs: number[] // the overs of the phase
  n_players: number // players in the cohort
  n_balls_in_phase: number // cohort balls in the phase
  below_support: boolean // true when an over the player bowls has too few balls; the rates are then null
  cliff_overs: number[] // the overs that have too few balls
  economy: number | null // runs conceded per over
  strike_rate: number | null // balls per wicket
  dot_pct: number | null // percent of balls with no run
  boundary_pct: number | null // percent of balls hit for four or six
  wickets_per_over: number | null // wickets per over
  wickets_per_innings_in_phase: number | null // wickets per innings in the phase
}

/** One season of the fielding cohort baseline: keepers or outfielders, as the player is. */
export interface ScopePlayerFieldingSeason {
  season: string // the season, as "2023" or "2023/24"
  is_keeper: number // 1 for the keepers' cohort, 0 for the outfielders'
  n_players: number // players in the cohort
  n_matches: number // cohort matches
  below_support: boolean // true when the cohort is too small; the rates are then null
  catches_per_match: number | null // catches per match
  stumpings_per_match: number | null // stumpings per match
  run_outs_per_match: number | null // run-outs per match
  dismissals_per_match: number | null // all fielding dismissals per match
}

/** One phase of the fielding cohort baseline: keepers or outfielders, as the player is. */
export interface ScopePlayerFieldingPhase {
  phase: string // "powerplay", "middle" or "death"
  phase_bucket: number // 1 for powerplay, 2 for middle, 3 for death
  is_keeper: number // 1 for the keepers' cohort, 0 for the outfielders'
  n_players: number // players in the cohort
  n_matches: number // cohort matches
  below_support: boolean // true when the cohort is too small; the rates are then null
  catches_per_match: number | null // catches in the phase per match
  stumpings_per_match: number | null // stumpings in the phase per match
  run_outs_per_match: number | null // run-outs in the phase per match
  dismissals_per_match: number | null // all fielding dismissals in the phase per match
}

/** One season of a team's fielding. */
export interface TeamFieldingSeason {
  season: string // the season, as "2023" or "2023/24"
  catches: number // catches taken
  caught_and_bowled: number // caught-and-bowled dismissals
  stumpings: number // stumpings
  run_outs: number // run-outs
  matches: number // matches played
  catches_per_match: number | null // catches per match
  stumpings_per_match: number | null // stumpings per match
  run_outs_per_match: number | null // run-outs per match
  total_dismissals_contributed: number // dismissals in which a fielder took part
}

/** One of a team's leading fielders in scope. */
export interface TeamTopFielder {
  person_id: string // the fielder's person id
  name: string // the fielder's name
  catches: number // catches taken
  caught_and_bowled: number // caught-and-bowled dismissals
  stumpings: number // stumpings
  run_outs: number // run-outs
  total: number // all dismissals the fielder took part in
}

/** One batter's share of a partnership. */
export interface PartnershipBatterInfo {
  person_id: string | null // the batter's person id; null when unknown
  name: string // the batter's name
  runs: number // runs the batter scored in the partnership
  balls: number // balls the batter faced in the partnership
}

/** A single partnership, with its match and both batters. */
export interface PartnershipRefInfo {
  partnership_id: number // the partnership id
  match_id: number // the match id
  date: string | null // the match date
  season: string // the season, as "2023" or "2023/24"
  tournament: string | null // the tournament; null for a match outside one
  opponent: string // the other team
  runs: number // runs in the partnership
  balls: number // balls in the partnership
  batter1: PartnershipBatterInfo // the first batter
  batter2: PartnershipBatterInfo // the second batter
}

/** A team's partnerships at one wicket, with the scope average and the best stand. */
export interface PartnershipByWicket {
  wicket_number: number // the wicket the partnership was for, from 1
  n: MetricEnvelope // the number of partnerships, with the scope average
  avg_runs: MetricEnvelope // average runs per partnership, with the scope average
  avg_balls: number | null // average balls per partnership
  best_runs: number // the highest partnership
  best_partnership: PartnershipRefInfo | null // the highest partnership in full; null when none
}

/** One cell of the partnership heatmap: a season and a wicket. */
export interface PartnershipHeatmapCell {
  season: string // the season, as "2023" or "2023/24"
  wicket_number: number // the wicket, from 1
  avg_runs: number // average runs per partnership
  n: number // the number of partnerships
}

/** A team's average partnership by season and wicket. */
export interface PartnershipHeatmap {
  team: string // the team
  side: 'batting' | 'bowling' // the team's partnerships, or those of its opponents against it
  seasons: string[] // the seasons in the heatmap
  wickets: number[] // the wickets in the heatmap, from 1
  cells: PartnershipHeatmapCell[] // the cells, each a season and a wicket
}

/** A team's batting by season and phase: run rate and wickets lost in each cell. */
export interface BattingPhaseSeasonHeatmap {
  team: string // the team
  seasons: string[] // the seasons in the heatmap
  phases: string[] // the phases in the heatmap
  cells: { // the cells, each a season and a phase
    season: string
    phase: string
    run_rate: number | null
    wickets_lost: number
    wickets_per_innings: number | null
    innings: number
    balls: number
  }[]
}

/** A team's bowling by season and phase: economy and wickets taken in each cell. */
export interface BowlingPhaseSeasonHeatmap {
  team: string // the team
  seasons: string[] // the seasons in the heatmap
  phases: string[] // the phases in the heatmap
  cells: { // the cells, each a season and a phase
    season: string
    phase: string
    economy: number | null
    wickets: number
    wickets_per_innings: number | null
    innings: number
    balls: number
  }[]
}

/** One pair of batters in a best-pairs list, with their partnerships together. */
export interface PartnershipPairEntry {
  rank: number // the pair's rank, from 1
  batter1: { person_id: string; name: string } // the first batter
  batter2: { person_id: string; name: string } // the second batter
  n: number // partnerships the pair shared
  avg_runs: number // average runs per partnership
  avg_balls: number // average balls per partnership
  best_runs: number // the pair's highest partnership
  total_runs: number // runs the pair made together
}

/** The best pairs at one wicket. */
export interface PartnershipBestPairsByWicket {
  wicket_number: number // the wicket, from 1
  pairs: PartnershipPairEntry[] // the pairs, best first
}

/** A team's best batting pairs at each wicket. */
export interface PartnershipBestPairsResponse {
  team: string // the team
  side: 'batting' | 'bowling' // the team's pairs, or its opponents' pairs against it
  min_n: number // the fewest partnerships a pair needs to be listed
  top_n: number // the most pairs listed per wicket
  by_wicket: PartnershipBestPairsByWicket[] // the pairs, wicket by wicket
}

/** One of a team's highest partnerships. */
export interface PartnershipTopEntry {
  partnership_id: number // the partnership id
  match_id: number // the match id
  date: string | null // the match date
  season: string // the season, as "2023" or "2023/24"
  tournament: string | null // the tournament; null for a match outside one
  opponent: string // the other team
  wicket_number: number | null // the wicket the partnership was for, from 1
  runs: number // runs in the partnership
  balls: number // balls in the partnership
  unbroken: boolean // true when no wicket ended the partnership
  ended_by_kind: string | null // the kind of dismissal that ended it; null when unbroken
  batter1: PartnershipBatterInfo // the first batter
  batter2: PartnershipBatterInfo // the second batter
}

// ─── Tournaments ────────────────────────────────────────────────────

/** One tournament on the Tournaments landing page. */
export interface TournamentLandingEntry {
  canonical: string // the tournament's canonical name
  editions: number // the number of seasons played
  matches: number // matches played
  most_titles: { team: string; titles: number } | null // the team with the most titles; null when none
  latest_edition: { season: string; champion: string } | null // the latest season and its champion; null when none
  team_type: string | null // "international" or "club"
  gender: string | null // "male" or "female"
}

/** A bilateral rivalry between two international teams, with its record. */
export interface RivalryEntry {
  team1: string // the first team
  team2: string // the second team
  matches: number // matches played
  team1_wins: number // wins for the first team
  team2_wins: number // wins for the second team
  ties: number // tied matches
  no_result: number // matches with no result
  /** The latest meeting; absent or null when none. */
  latest_match?: {
    match_id: number
    date: string | null
    winner: string | null
    /** Canonical tournament name. `null` ⇒ meeting was a pure bilateral. */
    tournament: string | null
    season: string
  } | null
}

/** A rivalry between two club teams in one tournament, with its record. */
export interface ClubRivalryEntry {
  team1: string // the first team
  team2: string // the second team
  tournament: string // the tournament they meet in
  matches: number // matches played
  team1_wins: number // wins for the first team
  team2_wins: number // wins for the second team
  ties: number // tied matches
  no_result: number // matches with no result
}

/** A recent season of a tournament, for the Tournaments landing page. */
export interface RecentEditionEntry {
  tournament: string // the tournament
  season: string // the season, as "2023" or "2023/24"
  last_match_date: string // the date of the season's last match
  gender: string | null // "male" or "female"
  team_type: string | null // "international" or "club"
  champion: string | null // the champion; null when there is none yet
}

/** The Tournaments landing page: recent seasons, international events and rivalries, and club leagues. */
export interface TournamentsLanding {
  recent_editions: RecentEditionEntry[] // the five latest seasons, newest first
  /** International cricket: ICC events, bilateral rivalries and other events. */
  international: {
    icc_events: TournamentLandingEntry[]
    bilateral_rivalries: {
      men: { top: RivalryEntry[]; other_count: number }
      women: { top: RivalryEntry[]; other_count: number }
      other_threshold: number
    }
    other_international: TournamentLandingEntry[]
  }
  /** Club cricket: leagues by kind, and rivalries. */
  club: {
    franchise_leagues: TournamentLandingEntry[]
    domestic_leagues: TournamentLandingEntry[]
    women_franchise: TournamentLandingEntry[]
    other: TournamentLandingEntry[]
    rivalries: {
      men: ClubRivalryEntry[]
      women: ClubRivalryEntry[]
    }
  }
}

/** A player's id and name. */
export interface PersonRef {
  person_id: string // the person id
  name: string // the name
}

/** One team's leaders within a tournament or rivalry. */
export interface TournamentSummaryByTeam {
  top_scorer: (PersonRef & { runs: number }) | null // the team's top run scorer; null when none
  top_wicket_taker: (PersonRef & { wickets: number }) | null // the team's top wicket taker; null when none
  /** The team's highest individual score; null when none. */
  highest_individual: (PersonRef & {
    runs: number; match_id: number; date: string | null
  }) | null
  /** The team's largest partnership; null when none. */
  largest_partnership: {
    runs: number; match_id: number; date: string | null
    batter1: PersonRef; batter2: PersonRef
  } | null
}

/** The dossier of a tournament, a rivalry or a tier: totals, champions, leaders, records and the draw. */
export interface TournamentSummary {
  canonical: string | null // the tournament's canonical name; null when no tournament is chosen
  variants: string[] // the event names in the data that map to this tournament
  editions: number // the number of seasons
  matches: number // matches played
  total_runs: number // runs scored
  total_wickets: number // wickets taken
  total_sixes: number // sixes hit
  total_fours: number // fours hit
  run_rate: number | null // runs per over
  boundary_pct: number | null // percent of legal balls hit for four or six
  dot_pct: number | null // percent of legal balls with no run
  most_titles: { team: string; titles: number } | null // the team with the most titles; null when none
  /** Each season's champion and final. */
  champions_by_season: {
    season: string
    /** Cricsheet event_name (NOT canonical). Present at tier mode so
     *  the Champions table can render a Tournament column across rows.
     *  In tournament-mode, every row's tournament equals the dossier's
     *  tournament so the field is redundant. */
    tournament: string | null
    champion: string
    match_id: number
    team1: string
    team2: string
    team1_score: string | null
    team2_score: string | null
    date: string | null
  }[]
  top_scorer_alltime: (PersonRef & { team: string | null; runs: number }) | null // the top run scorer in scope; null when none
  top_wicket_taker_alltime: (PersonRef & { team: string | null; wickets: number }) | null // the top wicket taker in scope; null when none
  /** Top 5 international teams by win % (min 100 games) at tier mode.
   *  Empty list when in tournament/rivalry mode (teams[] is shown
   *  instead). Sourced from precomputed bucketbaselinematch rows. */
  top_teams_international: {
    team: string
    played: number
    wins: number
    losses: number
    win_pct: number | null
  }[]
  /** Top 5 club teams by win % at tier mode. Same shape as
   *  top_teams_international. Empty in tournament/rivalry mode. */
  top_teams_club: {
    team: string
    played: number
    wins: number
    losses: number
    win_pct: number | null
  }[]
  /** The highest individual score in scope; null when none. */
  highest_individual: (PersonRef & {
    team: string | null; runs: number
    match_id: number; date: string | null
  }) | null
  /** The highest team total in scope; null when none. */
  highest_team_total: {
    team: string; total: number; match_id: number
    opponent: string; date: string | null
  } | null
  /** The largest partnership in scope; null when none. */
  largest_partnership: {
    runs: number; match_id: number
    team: string | null; opponent: string | null
    date: string | null
    batter1: PersonRef; batter2: PersonRef
  } | null
  /** The best bowling figures in one innings; null when none. */
  best_bowling: (PersonRef & {
    team: string | null
    figures: string; wickets: number; runs: number
    match_id: number; date: string | null
  }) | null
  /** The most fielding dismissals by one player in one match; null when none. */
  best_fielding: (PersonRef & {
    team: string | null
    catches: number; stumpings: number; run_outs: number; caught_bowled: number
    total: number
    match_id: number; date: string | null
  }) | null
  teams: { name: string; matches: number }[] // the teams that played, with their match counts
  /** The group-stage groups of each season, with their teams. */
  groups: {
    season: string
    group: string
    teams: { team: string; matches: number }[]
  }[]
  /** The knockout matches, with their stage and result. */
  knockouts: {
    match_id: number
    season: string
    stage: string
    tournament: string | null
    team1: string
    team2: string
    winner: string | null
    margin: string
    venue: string | null
    date: string | null
    team1_score: string | null
    team2_score: string | null
  }[]
  by_team: Record<string, TournamentSummaryByTeam> | null // each team's leaders, by team name; null unless a team and an opponent are set
  /** The win record between the team and the opponent; null unless both are set. */
  head_to_head: {
    team1: string
    team2: string
    team1_wins: number
    team2_wins: number
    ties: number
    no_result: number
  } | null
}

/** One season of a tournament: champion, runner-up, final, scoring and leaders. */
export interface TournamentSeason {
  season: string // the season, as "2023" or "2023/24"
  matches: number // matches played
  champion: string | null // the winner of the final; null when there was none
  champion_record: { played: number; won: number } | null // the champion's matches and wins that season
  runner_up: string | null // the loser of the final; null when there was none
  runner_up_record: { played: number; won: number } | null // the runner-up's matches and wins that season
  final_match_id: number | null // the final's match id; null when there was none
  final_team1: string | null // the final's first team
  final_team2: string | null // the final's second team
  final_team1_score: string | null // the first team's score in the final, as text
  final_team2_score: string | null // the second team's score in the final, as text
  run_rate: number | null // runs per over in the season
  boundary_pct: number | null // percent of legal balls hit for four or six
  total_sixes: number // sixes hit in the season
  top_scorer: (PersonRef & { runs: number }) | null // the season's top run scorer; null when none
  top_wicket_taker: (PersonRef & { wickets: number }) | null // the season's top wicket taker; null when none
}

/** One team's row in a points table. */
export interface PointsTableRow {
  team: string // the team
  played: number // matches played
  wins: number // matches won
  losses: number // matches lost
  ties: number // tied matches
  nr: number // matches with no result
  points: number // league points
  runs_for: number // runs scored
  balls_for: number // balls faced
  runs_against: number // runs conceded
  balls_against: number // balls bowled
  nrr: number | null // net run rate; null when it cannot be worked out
}

/** The points table of one group, or of the whole league. */
export interface TournamentPointsTable {
  group: string | null // the group name; null for a league with no groups
  rows: PointsTableRow[] // the teams, in table order
}

/** The points tables of one tournament season, from league matches only. */
export interface TournamentPointsTableResponse {
  canonical: string // the tournament's canonical name
  season: string | null // the season; null when the filters span several seasons
  tables: TournamentPointsTable[] // one table per group; empty when the filters span several seasons
  reason?: string // why `tables` is empty, such as "multi_season"
}

/** A team total in a tournament's records. */
export interface TournamentRecordTeamTotal {
  team: string // the batting team
  runs: number // the total
  opponent: string // the bowling team
  match_id: number // the match id
  date: string | null // the match date
  tournament: string | null // the tournament
  season: string | null // the season, as "2023" or "2023/24"
}

/** A win in a tournament's records, by runs or by wickets. */
export interface TournamentRecordWin {
  winner: string // the winning team
  loser: string // the losing team
  margin: number // the margin, in runs or in wickets as the list says
  match_id: number // the match id
  date: string | null // the match date
  tournament: string | null // the tournament
  season: string | null // the season, as "2023" or "2023/24"
}

/** A partnership in a tournament's records. */
export interface TournamentRecordPartnership {
  runs: number // runs in the partnership
  batter1: PersonRef // the first batter
  batter2: PersonRef // the second batter
  teams: string // the two teams, as text
  team1: string // the match's first team
  team2: string // the match's second team
  batting_team: string // the team the pair batted for
  match_id: number // the match id
  date: string | null // the match date
  tournament: string | null // the tournament
  season: string | null // the season, as "2023" or "2023/24"
}

/** A bowling performance in a tournament's records. */
export interface TournamentRecordBowling {
  person_id: string // the bowler's person id
  name: string // the bowler's name
  wickets: number // wickets taken
  runs: number // runs conceded
  balls: number // legal balls bowled
  figures: string // wickets and runs, as "5/35"
  match_id: number // the match id
  date: string | null // the match date
  tournament: string | null // the tournament
  season: string | null // the season, as "2023" or "2023/24"
}

/** An individual innings in a tournament's records. */
export interface TournamentRecordBatting {
  person_id: string // the batter's person id
  name: string // the batter's name
  runs: number // runs scored
  balls: number // balls faced
  fours: number // fours hit
  sixes: number // sixes hit
  not_out: boolean // true when the batter was not out
  figures: string // runs and balls, as "141* (54)"
  match_id: number // the match id
  date: string | null // the match date
  tournament: string | null // the tournament
  season: string | null // the season, as "2023" or "2023/24"
}

/** A match in a tournament's records for the most sixes. */
export interface TournamentRecordMatchSixes {
  match_id: number // the match id
  sixes: number // sixes hit by both teams
  teams: string // the two teams, as text
  team1: string // the first team
  team2: string // the second team
  date: string | null // the match date
  tournament: string | null // the tournament
  season: string | null // the season, as "2023" or "2023/24"
}

// Per-player records — /api/v1/{batters,bowlers,fielders}/{id}/records

/** One of a batter's innings in the batter's records. */
export interface PlayerBattingRecord {
  runs: number // runs scored
  balls: number // balls faced
  fours: number // fours hit
  sixes: number // sixes hit
  not_out: boolean // true when the batter was not out
  figures: string  // "141 (54)" or "141* (54)"
  strike_rate: number | null // runs per 100 balls
  match_id: number // the match id
  opponent: string // the bowling team
  team: string // the batter's team
  date: string | null // the match date
  tournament: string | null // the tournament; null for a match outside one
  season: string | null // the season, as "2023" or "2023/24"
}

/** A batter's records: highest scores, fastest fifties and hundreds, most sixes and fours, best strike rates. */
export interface BatterRecords {
  person_id: string // the batter's person id
  name: string // the batter's name
  highest_scores: PlayerBattingRecord[] // the highest scores
  fastest_50s: PlayerBattingRecord[] // the fifties made off the fewest balls
  fastest_100s: PlayerBattingRecord[] // the hundreds made off the fewest balls
  most_sixes_innings: PlayerBattingRecord[] // the innings with the most sixes
  most_fours_innings: PlayerBattingRecord[] // the innings with the most fours
  best_strike_rates: PlayerBattingRecord[] // the innings with the highest strike rates
}

/** One of a bowler's innings in the bowler's records. */
export interface PlayerBowlingRecord {
  wickets: number // wickets taken
  runs: number // runs conceded
  balls: number // legal balls bowled
  overs: string // overs bowled, as "4.0"
  economy: number | null // runs conceded per over
  figures: string  // "5/35"
  match_id: number // the match id
  opponent: string // the batting team
  team: string // the bowler's team
  date: string | null // the match date
  tournament: string | null // the tournament; null for a match outside one
  season: string | null // the season, as "2023" or "2023/24"
}

/** A bowler's records: best figures and most economical spells. */
export interface BowlerRecords {
  person_id: string // the bowler's person id
  name: string // the bowler's name
  best_figures: PlayerBowlingRecord[] // the best bowling figures
  most_economical: PlayerBowlingRecord[] // the innings with the lowest economy
}

/** One of a fielder's matches in the fielder's records. */
export interface PlayerFieldingRecord {
  catches: number // catches taken
  stumpings: number // stumpings
  run_outs: number // run-outs
  dismissals: number // all fielding dismissals
  match_id: number // the match id
  opponent: string // the other team
  team: string // the fielder's team
  date: string | null // the match date
  tournament: string | null // the tournament; null for a match outside one
  season: string | null // the season, as "2023" or "2023/24"
}

/** A fielder's records: the matches with the most catches, stumpings and dismissals. */
export interface FielderRecords {
  person_id: string // the fielder's person id
  name: string // the fielder's name
  most_catches_match: PlayerFieldingRecord[] // the matches with the most catches
  most_stumpings_match: PlayerFieldingRecord[] // the matches with the most stumpings
  most_dismissals_match: PlayerFieldingRecord[] // the matches with the most dismissals
}

/** A tournament's records: team totals, wins, partnerships, batting, bowling and sixes. */
export interface TournamentRecords {
  canonical: string // the tournament's canonical name
  highest_team_totals: TournamentRecordTeamTotal[] // the highest team totals
  lowest_all_out_totals: TournamentRecordTeamTotal[] // the lowest totals when all out
  biggest_wins_by_runs: TournamentRecordWin[] // the widest wins by runs
  biggest_wins_by_wickets: TournamentRecordWin[] // the widest wins by wickets
  largest_partnerships: TournamentRecordPartnership[] // the largest partnerships
  best_individual_batting: TournamentRecordBatting[] // the highest individual scores
  best_bowling_figures: TournamentRecordBowling[] // the best bowling figures
  most_sixes_in_a_match: TournamentRecordMatchSixes[] // the matches with the most sixes
}

/** A tournament's partnerships at one wicket, with the best stand. */
export interface TournamentPartnershipByWicket {
  wicket_number: number // the wicket, from 1
  n: number // the number of partnerships
  avg_runs: number | null // average runs per partnership
  avg_balls: number | null // average balls per partnership
  best_runs: number | null // the highest partnership
  /** The highest partnership in full; null when none. */
  best_partnership: {
    runs: number
    balls: number
    match_id: number
    season: string
    date: string | null
    batting_team: string
    opponent: string
    batter1: { person_id: string | null; name: string }
    batter2: { person_id: string | null; name: string }
  } | null
}

/** A tournament's partnerships, wicket by wicket. */
export interface TournamentPartnershipsByWicket {
  tournament: string // the tournament
  side: 'batting' | 'bowling' // with a team: its partnerships, or its opponents' against it
  filter_team: string | null // the team the list is narrowed to; null for all teams
  by_wicket: TournamentPartnershipByWicket[] // one row per wicket
}

/** One of a tournament's highest partnerships. */
export interface TournamentPartnershipTopEntry {
  partnership_id: number // the partnership id
  runs: number // runs in the partnership
  balls: number // balls in the partnership
  wicket_number: number | null // the wicket the partnership was for, from 1
  unbroken: boolean // true when no wicket ended the partnership
  ended_by_kind: string | null // the kind of dismissal that ended it; null when unbroken
  match_id: number // the match id
  season: string // the season, as "2023" or "2023/24"
  tournament: string | null // the tournament
  date: string | null // the match date
  batting_team: string // the team the pair batted for
  opponent: string // the bowling team
  batter1: { person_id: string | null; name: string; runs: number; balls: number } // the first batter and their share
  batter2: { person_id: string | null; name: string; runs: number; balls: number } // the second batter and their share
}

/** A tournament's highest partnerships. */
export interface TournamentPartnershipsTop {
  tournament: string // the tournament
  side: 'batting' | 'bowling' // with a team: its partnerships, or its opponents' against it
  filter_team: string | null // the team the list is narrowed to; null for all teams
  partnerships: TournamentPartnershipTopEntry[] // the partnerships, highest first
}

/** A tournament's highest partnerships at each wicket. */
export interface TournamentPartnershipsTopByWicket {
  tournament: string // the tournament
  side: 'batting' | 'bowling' // with a team: its partnerships, or its opponents' against it
  filter_team: string | null // the team the list is narrowed to; null for all teams
  per_wicket: number // the most partnerships listed per wicket
  /** The partnerships, wicket by wicket. */
  by_wicket: {
    wicket_number: number
    partnerships: TournamentPartnershipTopEntry[]
  }[]
}

/** A tournament's average partnership by season and wicket. */
export interface TournamentPartnershipsHeatmap {
  tournament: string // the tournament
  side: 'batting' | 'bowling' // with a team: its partnerships, or its opponents' against it
  filter_team: string | null // the team the heatmap is narrowed to; null for all teams
  seasons: string[] // the seasons in the heatmap
  wickets: number[] // the wickets in the heatmap, from 1
  cells: { season: string; wicket_number: number; avg_runs: number | null; n: number }[] // average runs and count per cell
}

/** The record between two teams: results, last match, leaders and notable matches. */
export interface RivalrySummary {
  team1: string // the first team
  team2: string // the second team
  matches: number // matches played
  team1_wins: number // wins for the first team
  team2_wins: number // wins for the second team
  ties: number // tied matches
  no_result: number // matches with no result
  /** The latest match between them; null when none. */
  last_match: {
    match_id: number; date: string | null
    winner: string | null; result: string | null; by: string | null
  } | null
  by_series_type: Record<string, number> // matches by kind: "icc_event", "bilateral_tour" or "other"
  top_scorer_in_rivalry: (PersonRef & { runs: number }) | null // the top run scorer; null when none
  top_wicket_taker_in_rivalry: (PersonRef & { wickets: number }) | null // the top wicket taker; null when none
  highest_individual: (PersonRef & { runs: number; match_id: number; date: string | null }) | null // the highest score; null when none
  largest_partnership: { runs: number; match_id: number } | null // the largest partnership; null when none
  closest_match: { margin: string; winner: string; match_id: number; date: string | null } | null // the narrowest win; null when none
  biggest_win: { winner: string; margin: string; match_id: number; date: string | null } | null // the widest win; null when none
}

// ─── Venues (Phase 2) ────────────────────────────────────────────────

/** A ground, with its city, country and match count. */
export interface VenueInfo {
  venue: string // the ground's name
  city: string | null // the city; null when unknown
  country: string | null // the country; null when unknown
  matches: number // matches played there
}

/** A ground on the Venues landing page. */
export interface VenueLandingEntry {
  venue: string // the ground's name
  city: string | null // the city; null when unknown
  matches: number // matches played there
}

/** The grounds of one country on the Venues landing page. */
export interface VenueCountryGroup {
  country: string // the country
  matches: number // matches played in the country
  venues: VenueLandingEntry[] // the country's grounds
}

/** The Venues landing page: grounds grouped by country. */
export interface VenuesLanding {
  by_country: VenueCountryGroup[] // the countries, each with its grounds
}

// ─── Venues (Phase 3 — dossier) ──────────────────────────────────────

/** Matches at a ground in one tournament, gender and season. */
export interface VenueTGSRow {
  tournament: string // the tournament
  gender: string | null // "male" or "female"
  season: string // the season, as "2023" or "2023/24"
  matches: number // matches played
}

/** A team total at a ground. */
export interface VenueTotalEntry {
  runs: number // the total
  team: string // the batting team
  opponent: string // the bowling team
  match_id: number // the match id
  season: string | null // the season, as "2023" or "2023/24"
  date: string | null // the match date
}

/** How often the toss winner won, for one toss decision. */
export interface VenueTossWinEntry {
  wins: number // matches the toss winner won
  decided: number // matches with a winner
  win_pct: number | null // percent of decided matches the toss winner won
}

/** The dossier of a ground: matches, first-innings totals, results, toss, phases and records. */
export interface VenueSummary {
  venue: string // the ground's name
  city: string | null // the city; null when unknown
  country: string | null // the country; null when unknown
  matches: number // matches played there
  by_tournament_gender_season: VenueTGSRow[] // matches by tournament, gender and season
  avg_first_innings_total: number | null // the average first-innings total
  first_innings_sample: number // matches with a first innings, behind the average and the win split
  bat_first_wins: number // matches won by the team batting first
  chase_wins: number // matches won by the chasing team
  indecisive: number // matches won by neither side
  bat_first_win_pct: number | null // percent of `first_innings_sample` won batting first
  chase_win_pct: number | null // percent of `first_innings_sample` won chasing
  toss_decision_split: Record<string, number> // matches by toss decision, "bat" or "field"
  toss_and_win_pct: Record<string, VenueTossWinEntry> // how often the toss winner won, by toss decision
  boundary_pct_by_phase: { powerplay: number | null; middle: number | null; death: number | null } // boundary percent in each phase
  dot_pct_by_phase: { powerplay: number | null; middle: number | null; death: number | null } // dot-ball percent in each phase
  highest_total: VenueTotalEntry | null // the highest total; null when none
  lowest_all_out: VenueTotalEntry | null // the lowest total when all out; null when none
}

// ─── League (above-tournament scope dossier) ─────────────────────────

/** A team's win record in the league overview. */
export interface LeagueTopTeamRow {
  team: string // the team
  played: number // matches played
  wins: number // matches won
  losses: number // matches lost
  win_pct: number | null // percent of matches won
}

/** A team total among the league overview's best moments. */
export interface LeagueBestMomentTeamTotal {
  team: string // the batting team
  runs: number // the total
  match_id: number // the match id
  season: string | null // the season, as "2023" or "2023/24"
  tournament: string | null // the tournament; null for a match outside one
  opponent: string // the bowling team
  date: string | null // the match date
}

/** A win among the league overview's best moments, by runs or by wickets. */
export interface LeagueBestMomentWinMargin {
  winner: string // the winning team
  loser: string // the losing team
  margin: number // the margin, in runs or in wickets as the field name says
  match_id: number // the match id
  season: string | null // the season, as "2023" or "2023/24"
  tournament: string | null // the tournament; null for a match outside one
  date: string | null // the match date
}

/** The match with the most sixes among the league overview's best moments. */
export interface LeagueBestMomentMatchSixes {
  match_id: number // the match id
  season: string | null // the season, as "2023" or "2023/24"
  tournament: string | null // the tournament; null for a match outside one
  team1: string // the first team
  team2: string // the second team
  sixes: number // sixes hit by both teams
  date: string | null // the match date
}

/** The league overview: counts, the top teams, and the best moments in scope. */
export interface LeagueOverview {
  matches: number // matches in scope
  innings: number // innings in scope
  teams_count: number // teams in scope
  tournaments_count: number // tournaments in scope
  min_games_threshold: number // the fewest matches a team needs to be ranked
  /** Top 5 international teams in scope (≥min_games). Empty when the
   *  FilterBar narrows team_type to club. */
  top_teams_international: LeagueTopTeamRow[]
  /** Top 5 club teams in scope (≥min_games). Empty when the FilterBar
   *  narrows team_type to international. */
  top_teams_club: LeagueTopTeamRow[]
  /** Records in scope: totals, wins and the match with the most sixes; each null when none. */
  best_moments: {
    highest_total: LeagueBestMomentTeamTotal | null
    lowest_all_out: LeagueBestMomentTeamTotal | null
    biggest_win_runs: LeagueBestMomentWinMargin | null
    biggest_win_wickets: LeagueBestMomentWinMargin | null
    most_sixes_match: LeagueBestMomentMatchSixes | null
  }
}

/** One season's champion of a tournament in the league view, with its final. */
export interface LeagueChampionRow {
  season: string // the season, as "2023" or "2023/24"
  tournament: string // the tournament
  champion: string // the winner of the final
  runner_up: string // the loser of the final
  final_match_id: number // the final's match id
  final_team1: string // the final's first team
  final_team2: string // the final's second team
  final_team1_score: string | null // the first team's score in the final, as text
  final_team2_score: string | null // the second team's score in the final, as text
  date: string | null // the date of the final
}
