export interface FilterParams {
  gender?: string
  team_type?: string
  tournament?: string
  season_from?: string
  season_to?: string
  /** Player-page rivalry scope — match-level pair filter. Backend reads
   *  these as `filter_team` / `filter_opponent` query params. */
  filter_team?: string
  filter_opponent?: string
  /** Ambient venue filter — narrows every filter-consuming endpoint to
   *  a single canonical venue (e.g. "Wankhede Stadium, Mumbai"). Set
   *  via the FilterBar VenueSearch on any tab. */
  filter_venue?: string
  team?: string
  opponent?: string
  /** Page-local aux filter — Series-tab pill (all/bilateral/icc/club).
   *  NOT in FILTER_KEYS (the FilterBar UI doesn't drive it; it's not
   *  part of scope-link letter URLs), but `useFilters` surfaces it so
   *  every endpoint consumer can pass it through to the backend, where
   *  it lands in AuxParams. Mirror of api/filters.py::AuxParams. */
  series_type?: string
}

export interface Tournament {
  event_name: string
  team_type: string
  gender: string
  matches: number
  seasons: string[]
}

export interface TeamInfo {
  name: string
  matches: number
  team_type: string
  gender: string
}

export interface PlayerSearchResult {
  id: string
  name: string
  unique_name: string
  innings: number
}

/** Per-metric envelope on the 5 team-compare summary endpoints.
 *  See `api/metrics_metadata.py` for direction map. Spec-1 UI renders
 *  only `value`; the other fields are shipped for Spec-2 surfaces
 *  (player compare, leaderboard delta columns, H2H baseline).
 *  See `internal_docs/outlook-comparisons.md`. */
export interface MetricEnvelope {
  value: number | null
  scope_avg: number | null
  delta_pct: number | null
  direction: 'higher_better' | 'lower_better' | null
  sample_size: number | null
}

export interface TeamSummary {
  team: string
  matches: MetricEnvelope
  wins: MetricEnvelope
  losses: MetricEnvelope
  ties: MetricEnvelope
  no_results: MetricEnvelope
  win_pct: MetricEnvelope
  toss_wins: MetricEnvelope
  bat_first_wins: MetricEnvelope
  field_first_wins: MetricEnvelope
  /** Present only when no gender filter is active AND the team has
   *  matches in BOTH genders within the current filter scope. */
  gender_breakdown: { male: number; female: number } | null
  /** Tier 2 — keepers used by this team (sorted by innings kept desc). */
  keepers: { person_id: string; name: string; innings_kept: number }[]
  /** Count of this team's fielding innings with no identified keeper. */
  keeper_ambiguous_innings: number
}

/** Keeper info attached to each innings on the scorecard endpoint. */
export interface ScorecardKeeper {
  person_id: string | null
  name: string | null
  method: string | null
  confidence: 'definitive' | 'high' | 'medium' | 'low' | null
  ambiguous_reason?: string
  candidate_ids?: string[]
  candidate_names?: string[]
}

export interface TeamResult {
  match_id: number
  date: string
  opponent: string
  venue: string | null
  city: string | null
  tournament: string | null
  toss_winner: string | null
  toss_decision: string | null
  result: string
  margin: string | null
  player_of_match: string[] | null
}

export interface TeamSeasonRecord {
  season: string
  matches: number
  wins: number
  losses: number
  ties: number
  no_results: number
  win_pct: number | null
}

export interface TeamPlayer {
  person_id: string
  name: string
  bat_avg: number | null
  bowl_sr: number | null
}

export interface TeamSeasonTurnover {
  prev_season: string
  new_count: number
  left_count: number
}

export interface TeamPlayersSeasonBucket {
  season: string
  players: TeamPlayer[]
  turnover: TeamSeasonTurnover | null
}

export interface TeamPlayersBySeason {
  seasons: TeamPlayersSeasonBucket[]
}

export interface TeamsLandingEntry {
  name: string
  matches: number
  gender?: string | null
}

export interface TeamsLandingTournamentGroup {
  tournament: string
  matches: number
  teams: TeamsLandingEntry[]
}

export interface TeamsLanding {
  international: {
    men: { regular: TeamsLandingEntry[]; associate: TeamsLandingEntry[] }
    women: { regular: TeamsLandingEntry[]; associate: TeamsLandingEntry[] }
  }
  club: {
    franchise_leagues: TeamsLandingTournamentGroup[]
    domestic_leagues: TeamsLandingTournamentGroup[]
    women_franchise: TeamsLandingTournamentGroup[]
    other: TeamsLandingTournamentGroup[]
  }
}

export interface BattingLeaderEntry {
  person_id: string
  name: string
  runs: number
  balls: number
  dismissals: number
  average: number | null
  strike_rate: number | null
  /** Dominant team in scope. Only set on tournament/rivalry leaders
   *  (not on the landing /batters/leaders). Used by TournamentDossier's
   *  rivalry context links to flip filter_team/filter_opponent per row. */
  team?: string | null
}

export interface BattingLeaders {
  by_runs: BattingLeaderEntry[]
  by_average: BattingLeaderEntry[]
  by_strike_rate: BattingLeaderEntry[]
  thresholds: { min_balls: number; min_dismissals: number }
}

export interface BowlingLeaderEntry {
  person_id: string
  name: string
  balls: number
  runs_conceded: number
  wickets: number
  strike_rate: number | null
  economy: number | null
  team?: string | null
}

export interface BowlingLeaders {
  by_wickets: BowlingLeaderEntry[]
  by_strike_rate: BowlingLeaderEntry[]
  by_economy: BowlingLeaderEntry[]
  thresholds: { min_balls: number; min_wickets: number }
}

export interface FieldingLeaderEntry {
  person_id: string
  name: string
  total: number
  catches: number
  stumpings: number
  run_outs?: number  // only present on by_dismissals
  c_and_b?: number
  team?: string | null
}

export interface FieldingLeaders {
  by_dismissals: FieldingLeaderEntry[]
  by_keeper_dismissals: FieldingLeaderEntry[]
  /** Present on /series/fielders-leaders only — top fielders by run-out
   *  count in scope. Absent on the batters-landing-style /fielders/leaders. */
  by_run_outs?: FieldingLeaderEntry[]
}

export interface TeamVsOpponent {
  team: string
  opponent: string
  overall: { matches: number; wins: number; losses: number; ties: number }
  by_season: TeamSeasonRecord[]
  matches: TeamResult[]
}

export interface OpponentRollup {
  name: string
  matches: number
  wins: number
  losses: number
  ties: number
  no_results: number
  win_pct: number | null
}

export interface OpponentMatrixCell {
  season: string
  opponent: string
  matches: number
  wins: number
  losses: number
  ties: number
  win_pct: number | null
}

export interface OpponentsMatrix {
  team: string
  seasons: string[]
  opponents: OpponentRollup[]
  cells: OpponentMatrixCell[]
}

export interface NationalityEntry {
  team: string
  gender: string
  matches: number
}

export interface BattingSummary {
  person_id: string
  name: string
  nationalities: NationalityEntry[]
  matches: number
  innings: number
  runs: number
  balls_faced: number
  not_outs: number
  dismissals: number
  average: number | null
  strike_rate: number | null
  highest_score: number
  hundreds: number
  fifties: number
  thirties: number
  ducks: number
  fours: number
  sixes: number
  boundaries: number
  dots: number
  dot_pct: number | null
  balls_per_four: number | null
  balls_per_six: number | null
  balls_per_boundary: number | null
}

export interface BattingInnings {
  match_id: number
  date: string
  team: string
  opponent: string
  venue: string | null
  tournament: string | null
  runs: number
  balls: number
  fours: number
  sixes: number
  strike_rate: number | null
  not_out: boolean
  how_out: string | null
  dismissed_by: string | null
}

export interface BowlerMatchup {
  bowler_id: string
  bowler_name: string
  balls: number
  runs: number
  dismissals: number
  average: number | null
  strike_rate: number | null
  fours: number
  sixes: number
  dots: number
  dot_pct: number | null
  balls_per_four: number | null
  balls_per_six: number | null
  balls_per_boundary: number | null
}

export interface OverStats {
  over_number: number
  balls: number
  runs: number
  fours: number
  sixes: number
  dots: number
  dismissals: number
  strike_rate: number | null
  dot_pct: number | null
  boundary_pct: number | null
  balls_per_four: number | null
  balls_per_six: number | null
  balls_per_boundary: number | null
}

export interface PhaseStats {
  phase: string
  overs: string
  balls: number
  runs: number
  fours: number
  sixes: number
  dots: number
  dismissals: number
  strike_rate: number | null
  dot_pct: number | null
  boundary_pct: number | null
}

export interface SeasonBattingStats {
  season: string
  innings: number
  runs: number
  balls: number
  average: number | null
  strike_rate: number | null
  fours: number
  sixes: number
  fifties: number
  hundreds: number
  dismissals: number
  balls_per_boundary: number | null
}

export interface DismissalAnalysis {
  total_dismissals: number
  by_kind: Record<string, number>
  by_phase: Record<string, number>
  by_over: { over_number: number; dismissals: number }[]
  top_bowlers: {
    bowler_id: string
    bowler_name: string
    dismissals: number
    kinds: Record<string, number>
  }[]
}

export interface InterWicketStats {
  wickets_down: number
  innings_count: number
  balls: number
  runs: number
  fours: number
  sixes: number
  strike_rate: number | null
  dismissals: number
  avg_balls_before_next_wicket: number | null
}

export interface BowlingSummary {
  person_id: string
  name: string
  nationalities: NationalityEntry[]
  matches: number
  innings: number
  balls: number
  overs: string
  runs_conceded: number
  wickets: number
  average: number | null
  economy: number | null
  strike_rate: number | null
  best_figures: string | null
  four_wicket_hauls: number
  fours_conceded: number
  sixes_conceded: number
  boundaries_conceded: number
  dots: number
  dot_pct: number | null
  wides: number
  noballs: number
  balls_per_four: number | null
  balls_per_six: number | null
  balls_per_boundary: number | null
  maiden_overs: number
}

export interface BowlingInnings {
  match_id: number
  date: string
  team: string
  opponent: string
  tournament: string | null
  overs: string
  balls: number
  runs: number
  wickets: number
  economy: number | null
  fours: number
  sixes: number
  dots: number
  maidens: number
  wides: number
  noballs: number
}

export interface BatterMatchup {
  batter_id: string
  batter_name: string
  balls: number
  runs_conceded: number
  wickets: number
  average: number | null
  economy: number | null
  strike_rate: number | null
  fours_conceded: number
  sixes_conceded: number
  dots: number
  dot_pct: number | null
  balls_per_four: number | null
  balls_per_six: number | null
  balls_per_boundary: number | null
}

export interface WicketAnalysis {
  total_wickets: number
  by_kind: Record<string, number>
  by_phase: Record<string, number>
  by_over: { over_number: number; wickets: number }[]
  top_victims: {
    batter_id: string
    batter_name: string
    dismissals: number
    kinds: Record<string, number>
  }[]
}

export interface HeadToHeadSummary {
  matches: number
  balls: number
  runs: number
  dismissals: number
  average: number | null
  strike_rate: number | null
  fours: number
  sixes: number
  dots: number
  dot_pct: number | null
  balls_per_boundary: number | null
}

export interface HeadToHeadMatch {
  match_id: number
  date: string
  tournament: string | null
  venue: string | null
  balls: number
  runs: number
  fours: number
  sixes: number
  dismissed: boolean
  how_out: string | null
}

export interface HeadToHeadResponse {
  batter: { id: string; name: string; nationalities?: NationalityEntry[] }
  bowler: { id: string; name: string; nationalities?: NationalityEntry[] }
  summary: HeadToHeadSummary
  dismissal_kinds: Record<string, number>
  by_over: { over_number: number; balls: number; runs: number; wickets: number }[]
  by_phase: { phase: string; balls: number; runs: number; wickets: number; strike_rate: number | null }[]
  by_season: { season: string; balls: number; runs: number; wickets: number; strike_rate: number | null }[]
  by_match: HeadToHeadMatch[]
}

// Composed player overview (client-side; see /players page).
// The four sub-types already exist below — one nullable slot per discipline.
// null = fetch 404'd (player doesn't bat/bowl/etc. in scope) or it failed.
export interface PlayerProfile {
  batting: BattingSummary | null
  bowling: BowlingSummary | null
  fielding: FieldingSummary | null
  keeping: KeepingSummary | null
}

// Fielding
export interface FieldingSummary {
  person_id: string
  name: string
  nationalities: NationalityEntry[]
  matches: number
  catches: number
  stumpings: number
  run_outs: number
  caught_and_bowled: number
  total_dismissals: number
  dismissals_per_match: number | null
  substitute_catches: number
  /** Tier 2 — innings where this person was assigned keeper. Used to gate the "Keeping" tab. */
  innings_kept: number
}

// Keeping (Tier 2 fielding — wicketkeeper-specific stats)
export interface KeepingSummary {
  person_id: string
  name: string
  innings_kept: number
  innings_kept_by_confidence: {
    definitive: number
    high: number
    medium: number
    low: number
  }
  stumpings: number
  keeping_catches: number
  run_outs_while_keeping: number
  byes_conceded: number
  byes_per_innings: number | null
  dismissals_while_keeping: number
  keeping_dismissals_per_innings: number | null
  ambiguous_innings: number
}

export interface KeepingSeason {
  season: string
  innings_kept: number
  stumpings: number
  keeping_catches: number
  run_outs_while_keeping: number
  byes_conceded: number
  total_dismissals: number
}

export interface KeepingInnings {
  match_id: number
  innings_number: number
  date: string | null
  opponent: string
  tournament: string | null
  confidence: 'definitive' | 'high' | 'medium' | 'low'
  method: string
  stumpings: number
  catches: number
  run_outs: number
  byes: number
  total_dismissals: number
}

export interface KeepingAmbiguousInnings {
  match_id: number
  innings_id: number
  innings_number: number
  date: string | null
  tournament: string | null
  season: string
  fielding_team: string
  opponent: string
  ambiguous_reason: string
  candidate_ids: string[]
  candidate_names: string[]
}

export interface FieldingSeason {
  season: string
  catches: number
  stumpings: number
  run_outs: number
  caught_and_bowled: number
  total: number
}

export interface FieldingPhase {
  phase: string
  overs: string
  catches: number
  stumpings: number
  run_outs: number
  caught_and_bowled: number
  total: number
}

export interface FieldingVictim {
  batter_id: string
  batter_name: string
  catches: number
  stumpings: number
  run_outs: number
  total: number
}

export interface FieldingInnings {
  match_id: number
  date: string
  opponent: string | null
  tournament: string | null
  catches: number
  stumpings: number
  run_outs: number
  total: number
}

// Matches & scorecards
export interface MatchListItem {
  match_id: number
  date: string | null
  team1: string
  team2: string
  venue: string | null
  city: string | null
  tournament: string | null
  season: string | null
  winner: string | null
  result_text: string
  team1_score: string | null
  team2_score: string | null
}

export interface ScorecardBatter {
  person_id: string | null
  name: string
  dismissal: string
  /** Bowler credited with the wicket — null for not-out, run-out, retired, etc. */
  dismissal_bowler_id: string | null
  /** Fielder(s) involved in the dismissal (from fielding_credit). */
  dismissal_fielder_ids: string[]
  runs: number
  balls: number
  fours: number
  sixes: number
  strike_rate: number
}

export interface ScorecardBowler {
  person_id: string | null
  name: string
  overs: string
  maidens: number
  runs: number
  wickets: number
  econ: number
  wides: number
  noballs: number
}

export interface ScorecardExtras {
  byes: number
  legbyes: number
  wides: number
  noballs: number
  penalty: number
  total: number
}

export interface ScorecardFallOfWicket {
  wicket: number
  score: number
  batter: string
  over_ball: string
}

export interface OverProgression {
  over: number
  runs: number
  wickets: number
  cumulative: number
}

export interface ScorecardInnings {
  innings_number: number
  team: string
  is_super_over: boolean
  label: string
  total_runs: number
  wickets: number
  overs: string
  run_rate: number
  batting: ScorecardBatter[]
  did_not_bat: string[]
  extras: ScorecardExtras
  fall_of_wickets: ScorecardFallOfWicket[]
  bowling: ScorecardBowler[]
  by_over: OverProgression[]
  /** Tier 2 — the wicketkeeper for this innings (of the FIELDING team).
   *  Null for super-overs; ambiguous innings have person_id=null plus
   *  candidate_ids/names + ambiguous_reason. */
  keeper: ScorecardKeeper | null
}

export interface ScorecardInfo {
  match_id: number
  teams: string[]
  venue: string | null
  city: string | null
  dates: string[]
  tournament: string | null
  season: string | null
  match_number: number | null
  stage: string | null
  toss_winner: string | null
  toss_decision: string | null
  result_text: string
  method: string | null
  player_of_match: string[]
  officials: Record<string, string[]> | null
  gender: string | null
  team_type: string | null
}

export interface Scorecard {
  info: ScorecardInfo
  innings: ScorecardInnings[]
}

// Innings grid (per-delivery visualization)
export interface InningsGridDelivery {
  over_ball: string
  bowler: string
  bowler_id: string | null
  bowler_index: number | null
  batter: string
  batter_id: string | null
  batter_index: number
  non_striker: string
  non_striker_index: number | null
  runs_batter: number
  runs_extras: number
  runs_total: number
  extras_wides: number
  extras_noballs: number
  extras_byes: number
  extras_legbyes: number
  cumulative_runs: number
  cumulative_wickets: number
  wicket_kind: string | null
  wicket_player_out: string | null
  wicket_player_out_index: number | null
  wicket_text: string | null
}

export interface InningsGridInnings {
  innings_number: number
  team: string
  batters: string[]
  batter_ids: (string | null)[]
  bowlers: string[]
  bowler_ids: (string | null)[]
  deliveries: InningsGridDelivery[]
  total_balls: number
  total_runs: number
  total_wickets: number
}

export interface InningsGridResponse {
  match_id: number
  innings: InningsGridInnings[]
}

// ============================================================
// Team stats — batting / bowling / fielding / partnerships
// (see internal_docs/spec-team-stats.md)
// ============================================================

export interface TeamInningsTotal {
  runs: number
  match_id: number
  innings_number: number
}

export interface TeamBattingSummary {
  team: string
  innings_batted: MetricEnvelope
  total_runs: MetricEnvelope
  legal_balls: MetricEnvelope
  run_rate: MetricEnvelope
  boundary_pct: MetricEnvelope
  dot_pct: MetricEnvelope
  fours: MetricEnvelope
  sixes: MetricEnvelope
  fifties: MetricEnvelope
  hundreds: MetricEnvelope
  avg_1st_innings_total: MetricEnvelope
  avg_2nd_innings_total: MetricEnvelope
  highest_total: TeamInningsTotal | null
  lowest_all_out_total: TeamInningsTotal | null
}

export interface TeamBattingSeason {
  season: string
  innings_batted: number
  total_runs: number
  legal_balls: number
  avg_innings_total: number | null
  run_rate: number | null
  boundary_pct: number | null
  dot_pct: number | null
  fours: number
  sixes: number
  highest_total: number
  lowest_all_out_total: number | null
}

export interface TeamBattingPhase {
  phase: string
  overs_range: number[]
  runs: number
  balls: number
  run_rate: MetricEnvelope
  wickets_lost: number
  boundary_pct: MetricEnvelope
  dot_pct: MetricEnvelope
  fours: number
  sixes: number
}

export interface TeamTopBatter {
  person_id: string
  name: string
  runs: number
  balls: number
  strike_rate: number | null
  fours: number
  sixes: number
  innings: number
}

export interface TeamBowlingSummary {
  team: string
  innings_bowled: MetricEnvelope
  matches: MetricEnvelope
  runs_conceded: MetricEnvelope
  legal_balls: MetricEnvelope
  overs: MetricEnvelope
  wickets: MetricEnvelope
  economy: MetricEnvelope
  strike_rate: MetricEnvelope
  average: MetricEnvelope
  dot_pct: MetricEnvelope
  fours_conceded: MetricEnvelope
  sixes_conceded: MetricEnvelope
  wides: MetricEnvelope
  noballs: MetricEnvelope
  wides_per_match: MetricEnvelope
  noballs_per_match: MetricEnvelope
  avg_opposition_total: MetricEnvelope
  worst_conceded: TeamInningsTotal | null
  best_defence: { runs: number; match_id: number } | null
}

export interface TeamBowlingSeason {
  season: string
  innings_bowled: number
  runs_conceded: number
  legal_balls: number
  overs: number
  wickets: number
  economy: number | null
  avg_opposition_total: number | null
  dot_pct: number | null
  boundaries_conceded: number
  worst_conceded: number
}

export interface TeamBowlingPhase {
  phase: string
  overs_range: number[]
  runs_conceded: number
  balls: number
  economy: MetricEnvelope
  wickets: number
  boundary_pct: MetricEnvelope
  dot_pct: MetricEnvelope
  fours_conceded: number
  sixes_conceded: number
}

export interface TeamTopBowler {
  person_id: string
  name: string
  wickets: number
  runs_conceded: number
  balls: number
  overs: number
  economy: number | null
  average: number | null
  strike_rate: number | null
  innings: number
}

export interface TeamFieldingSummary {
  team: string
  matches: MetricEnvelope
  catches: MetricEnvelope
  caught_and_bowled: MetricEnvelope
  stumpings: MetricEnvelope
  run_outs: MetricEnvelope
  total_dismissals_contributed: MetricEnvelope
  catches_per_match: MetricEnvelope
  stumpings_per_match: MetricEnvelope
  run_outs_per_match: MetricEnvelope
}

/** Aggregate partnership stats for a team in the current filter scope.
 *  Returned by /api/v1/teams/{team}/partnerships/summary. */
export interface TeamPartnershipsSummary {
  team: string
  side: 'batting' | 'bowling'
  total: MetricEnvelope
  count_50_plus: MetricEnvelope
  count_100_plus: MetricEnvelope
  avg_runs: MetricEnvelope
  highest: {
    runs: number
    balls: number
    match_id: number
    date: string | null
    batter1: { person_id: string; name: string | null }
    batter2: { person_id: string; name: string | null }
  } | null
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
  summary: TeamSummary | null
  batting: TeamBattingSummary | null
  bowling: TeamBowlingSummary | null
  fielding: TeamFieldingSummary | null
  partnerships: TeamPartnershipsSummary | null
  batting_by_phase: { phases: TeamBattingPhase[] } | null
  bowling_by_phase: { phases: TeamBowlingPhase[] } | null
  partnerships_by_wicket: { team: string; side: 'batting' | 'bowling'; by_wicket: PartnershipByWicket[] } | null
  batting_by_season: { seasons: TeamBattingSeason[] } | null
  bowling_by_season: { seasons: TeamBowlingSeason[] } | null
  fielding_by_season: { seasons: TeamFieldingSeason[] } | null
  partnerships_by_season: { team: string; side: 'batting' | 'bowling'; by_season: TeamPartnershipsSeason[] } | null
}

/** Per-season partnership aggregates returned by
 *  /teams/{team}/partnerships/by-season + /scope/averages/partnerships/by-season. */
export interface TeamPartnershipsSeason {
  season: string
  total: number
  count_50_plus: number
  count_100_plus: number
  avg_runs: number | null
  best_runs: number | null
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

export interface ScopeSummary {
  matches: number
  decided: number
  ties: number
  no_results: number
  toss_decided: number
  bat_first_wins: number
  field_first_wins: number
  bat_first_win_pct: number | null
}

export interface ScopeBattingSummary {
  innings_batted: number
  total_runs: number
  legal_balls: number
  run_rate: number | null
  boundary_pct: number | null
  dot_pct: number | null
  fours: number
  sixes: number
  avg_1st_innings_total: number | null
  avg_2nd_innings_total: number | null
  highest_total: {
    runs: number
    team: string | null
    match_id: number
    innings_number: number
  } | null
}

export interface ScopeBattingSeason {
  season: string
  innings_batted: number
  total_runs: number
  legal_balls: number
  run_rate: number | null
  boundary_pct: number | null
  dot_pct: number | null
  fours: number
  sixes: number
}

export interface ScopeBowlingSummary {
  innings_bowled: number
  matches: number
  runs_conceded: number
  legal_balls: number
  overs: number
  wickets: number
  economy: number | null
  strike_rate: number | null
  average: number | null
  dot_pct: number | null
  fours_conceded: number
  sixes_conceded: number
  wides: number
  noballs: number
  wides_per_match: number | null
  noballs_per_match: number | null
}

export interface ScopeBowlingSeason {
  season: string
  innings_bowled: number
  runs_conceded: number
  legal_balls: number
  overs: number
  wickets: number
  economy: number | null
  dot_pct: number | null
  boundaries_conceded: number
}

export interface ScopeFieldingSummary {
  matches: number
  catches: number
  caught_and_bowled: number
  stumpings: number
  run_outs: number
  total_dismissals_contributed: number
  catches_per_match: number | null
  stumpings_per_match: number | null
  run_outs_per_match: number | null
}

export interface ScopeFieldingSeason {
  season: string
  matches: number
  catches: number
  stumpings: number
  run_outs: number
  total_dismissals_contributed: number
  catches_per_match: number | null
  stumpings_per_match: number | null
  run_outs_per_match: number | null
}

export interface ScopePartnershipsSummary {
  total: number
  count_50_plus: number
  count_100_plus: number
  avg_runs: number | null
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
  phase: string
  overs_range: number[]
  runs: number
  balls: number
  run_rate: number | null
  wickets_lost: number
  boundary_pct: number | null
  dot_pct: number | null
  fours: number
  sixes: number
}

export interface ScopeBowlingPhaseFlat {
  phase: string
  overs_range: number[]
  runs_conceded: number
  balls: number
  economy: number | null
  wickets: number
  boundary_pct: number | null
  dot_pct: number | null
  fours_conceded: number
  sixes_conceded: number
}

export interface ScopePartnershipByWicket {
  wicket_number: number
  n: number
  avg_runs: number | null
  avg_balls: number | null
  best_runs: number | null
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

export interface ScopePartnershipsSeason {
  season: string
  total: number
  count_50_plus: number
  count_100_plus: number
  avg_runs: number | null
  best_runs: number | null
}

/** Bundle fetched for the Average column in the Teams > Compare tab.
 *  Mirrors TeamProfile shape so columns can be rendered side-by-side. */
export interface ScopeAverageProfile {
  summary: ScopeSummary | null
  batting: ScopeBattingSummary | null
  bowling: ScopeBowlingSummary | null
  fielding: ScopeFieldingSummary | null
  partnerships: ScopePartnershipsSummary | null
  batting_by_phase: { by_phase: ScopeBattingPhaseFlat[] } | null
  bowling_by_phase: { by_phase: ScopeBowlingPhaseFlat[] } | null
  partnerships_by_wicket: { by_wicket: ScopePartnershipByWicket[] } | null
  batting_by_season: { by_season: ScopeBattingSeason[] } | null
  bowling_by_season: { by_season: ScopeBowlingSeason[] } | null
  fielding_by_season: { by_season: ScopeFieldingSeason[] } | null
  partnerships_by_season: { by_season: ScopePartnershipsSeason[] } | null
}

export interface TeamFieldingSeason {
  season: string
  catches: number
  caught_and_bowled: number
  stumpings: number
  run_outs: number
  matches: number
  catches_per_match: number | null
  stumpings_per_match: number | null
  run_outs_per_match: number | null
  total_dismissals_contributed: number
}

export interface TeamTopFielder {
  person_id: string
  name: string
  catches: number
  caught_and_bowled: number
  stumpings: number
  run_outs: number
  total: number
}

export interface PartnershipBatterInfo {
  person_id: string | null
  name: string
  runs: number
  balls: number
}

export interface PartnershipRefInfo {
  partnership_id: number
  match_id: number
  date: string | null
  season: string
  tournament: string | null
  opponent: string
  runs: number
  balls: number
  batter1: PartnershipBatterInfo
  batter2: PartnershipBatterInfo
}

export interface PartnershipByWicket {
  wicket_number: number
  n: MetricEnvelope
  avg_runs: MetricEnvelope
  avg_balls: number | null
  best_runs: number
  best_partnership: PartnershipRefInfo | null
}

export interface PartnershipHeatmapCell {
  season: string
  wicket_number: number
  avg_runs: number
  n: number
}

export interface PartnershipHeatmap {
  team: string
  side: 'batting' | 'bowling'
  seasons: string[]
  wickets: number[]
  cells: PartnershipHeatmapCell[]
}

export interface BattingPhaseSeasonHeatmap {
  team: string
  seasons: string[]
  phases: string[]
  cells: {
    season: string
    phase: string
    run_rate: number | null
    wickets_lost: number
    wickets_per_innings: number | null
    innings: number
    balls: number
  }[]
}

export interface BowlingPhaseSeasonHeatmap {
  team: string
  seasons: string[]
  phases: string[]
  cells: {
    season: string
    phase: string
    economy: number | null
    wickets: number
    wickets_per_innings: number | null
    innings: number
    balls: number
  }[]
}

export interface PartnershipPairEntry {
  rank: number
  batter1: { person_id: string; name: string }
  batter2: { person_id: string; name: string }
  n: number
  avg_runs: number
  avg_balls: number
  best_runs: number
  total_runs: number
}

export interface PartnershipBestPairsByWicket {
  wicket_number: number
  pairs: PartnershipPairEntry[]
}

export interface PartnershipBestPairsResponse {
  team: string
  side: 'batting' | 'bowling'
  min_n: number
  top_n: number
  by_wicket: PartnershipBestPairsByWicket[]
}

export interface PartnershipTopEntry {
  partnership_id: number
  match_id: number
  date: string | null
  season: string
  tournament: string | null
  opponent: string
  wicket_number: number | null
  runs: number
  balls: number
  unbroken: boolean
  ended_by_kind: string | null
  batter1: PartnershipBatterInfo
  batter2: PartnershipBatterInfo
}

// ─── Tournaments ────────────────────────────────────────────────────

export interface TournamentLandingEntry {
  canonical: string
  editions: number
  matches: number
  most_titles: { team: string; titles: number } | null
  latest_edition: { season: string; champion: string } | null
  team_type: string | null
  gender: string | null
}

export interface RivalryEntry {
  team1: string
  team2: string
  matches: number
  team1_wins: number
  team2_wins: number
  ties: number
  no_result: number
  latest_match?: {
    match_id: number
    date: string | null
    winner: string | null
    /** Canonical tournament name. `null` ⇒ meeting was a pure bilateral. */
    tournament: string | null
    season: string
  } | null
}

export interface ClubRivalryEntry {
  team1: string
  team2: string
  tournament: string
  matches: number
  team1_wins: number
  team2_wins: number
  ties: number
  no_result: number
}

export interface TournamentsLanding {
  international: {
    icc_events: TournamentLandingEntry[]
    bilateral_rivalries: {
      men: { top: RivalryEntry[]; other_count: number }
      women: { top: RivalryEntry[]; other_count: number }
      other_threshold: number
    }
    other_international: TournamentLandingEntry[]
  }
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

export interface PersonRef {
  person_id: string
  name: string
}

export interface TournamentSummaryByTeam {
  top_scorer: (PersonRef & { runs: number }) | null
  top_wicket_taker: (PersonRef & { wickets: number }) | null
  highest_individual: (PersonRef & {
    runs: number; match_id: number; date: string | null
  }) | null
  largest_partnership: {
    runs: number; match_id: number; date: string | null
    batter1: PersonRef; batter2: PersonRef
  } | null
}

export interface TournamentSummary {
  canonical: string | null
  variants: string[]
  editions: number
  matches: number
  total_runs: number
  total_wickets: number
  total_sixes: number
  total_fours: number
  run_rate: number | null
  boundary_pct: number | null
  dot_pct: number | null
  most_titles: { team: string; titles: number } | null
  champions_by_season: {
    season: string
    champion: string
    match_id: number
    team1: string
    team2: string
    team1_score: string | null
    team2_score: string | null
    date: string | null
  }[]
  top_scorer_alltime: (PersonRef & { team: string | null; runs: number }) | null
  top_wicket_taker_alltime: (PersonRef & { team: string | null; wickets: number }) | null
  highest_individual: (PersonRef & {
    team: string | null; runs: number
    match_id: number; date: string | null
  }) | null
  highest_team_total: {
    team: string; total: number; match_id: number
    opponent: string; date: string | null
  } | null
  largest_partnership: {
    runs: number; match_id: number
    team: string | null; opponent: string | null
    date: string | null
    batter1: PersonRef; batter2: PersonRef
  } | null
  best_bowling: (PersonRef & {
    team: string | null
    figures: string; wickets: number; runs: number
    match_id: number; date: string | null
  }) | null
  best_fielding: (PersonRef & {
    team: string | null
    catches: number; stumpings: number; run_outs: number; caught_bowled: number
    total: number
    match_id: number; date: string | null
  }) | null
  teams: { name: string; matches: number }[]
  groups: {
    season: string
    group: string
    teams: { team: string; matches: number }[]
  }[]
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
  by_team: Record<string, TournamentSummaryByTeam> | null
  head_to_head: {
    team1: string
    team2: string
    team1_wins: number
    team2_wins: number
    ties: number
    no_result: number
  } | null
}

export interface TournamentSeason {
  season: string
  matches: number
  champion: string | null
  champion_record: { played: number; won: number } | null
  runner_up: string | null
  runner_up_record: { played: number; won: number } | null
  final_match_id: number | null
  final_team1: string | null
  final_team2: string | null
  final_team1_score: string | null
  final_team2_score: string | null
  run_rate: number | null
  boundary_pct: number | null
  total_sixes: number
  top_scorer: (PersonRef & { runs: number }) | null
  top_wicket_taker: (PersonRef & { wickets: number }) | null
}

export interface PointsTableRow {
  team: string
  played: number
  wins: number
  losses: number
  ties: number
  nr: number
  points: number
  runs_for: number
  balls_for: number
  runs_against: number
  balls_against: number
  nrr: number | null
}

export interface TournamentPointsTable {
  group: string | null
  rows: PointsTableRow[]
}

export interface TournamentPointsTableResponse {
  canonical: string
  season: string | null
  tables: TournamentPointsTable[]
  reason?: string
}

export interface TournamentRecordTeamTotal {
  team: string
  runs: number
  opponent: string
  match_id: number
  date: string | null
  tournament: string | null
  season: string | null
}

export interface TournamentRecordWin {
  winner: string
  loser: string
  margin: number
  match_id: number
  date: string | null
  tournament: string | null
  season: string | null
}

export interface TournamentRecordPartnership {
  runs: number
  batter1: PersonRef
  batter2: PersonRef
  teams: string
  team1: string
  team2: string
  batting_team: string
  match_id: number
  date: string | null
  tournament: string | null
  season: string | null
}

export interface TournamentRecordBowling {
  person_id: string
  name: string
  wickets: number
  runs: number
  balls: number
  figures: string
  match_id: number
  date: string | null
  tournament: string | null
  season: string | null
}

export interface TournamentRecordBatting {
  person_id: string
  name: string
  runs: number
  balls: number
  fours: number
  sixes: number
  not_out: boolean
  figures: string
  match_id: number
  date: string | null
  tournament: string | null
  season: string | null
}

export interface TournamentRecordMatchSixes {
  match_id: number
  sixes: number
  teams: string
  team1: string
  team2: string
  date: string | null
  tournament: string | null
  season: string | null
}

export interface TournamentRecords {
  canonical: string
  highest_team_totals: TournamentRecordTeamTotal[]
  lowest_all_out_totals: TournamentRecordTeamTotal[]
  biggest_wins_by_runs: TournamentRecordWin[]
  biggest_wins_by_wickets: TournamentRecordWin[]
  largest_partnerships: TournamentRecordPartnership[]
  best_individual_batting: TournamentRecordBatting[]
  best_bowling_figures: TournamentRecordBowling[]
  most_sixes_in_a_match: TournamentRecordMatchSixes[]
}

export interface TournamentPartnershipByWicket {
  wicket_number: number
  n: number
  avg_runs: number | null
  avg_balls: number | null
  best_runs: number | null
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

export interface TournamentPartnershipsByWicket {
  tournament: string
  side: 'batting' | 'bowling'
  filter_team: string | null
  by_wicket: TournamentPartnershipByWicket[]
}

export interface TournamentPartnershipTopEntry {
  partnership_id: number
  runs: number
  balls: number
  wicket_number: number | null
  unbroken: boolean
  ended_by_kind: string | null
  match_id: number
  season: string
  tournament: string | null
  date: string | null
  batting_team: string
  opponent: string
  batter1: { person_id: string | null; name: string; runs: number; balls: number }
  batter2: { person_id: string | null; name: string; runs: number; balls: number }
}

export interface TournamentPartnershipsTop {
  tournament: string
  side: 'batting' | 'bowling'
  filter_team: string | null
  partnerships: TournamentPartnershipTopEntry[]
}

export interface TournamentPartnershipsTopByWicket {
  tournament: string
  side: 'batting' | 'bowling'
  filter_team: string | null
  per_wicket: number
  by_wicket: {
    wicket_number: number
    partnerships: TournamentPartnershipTopEntry[]
  }[]
}

export interface TournamentPartnershipsHeatmap {
  tournament: string
  side: 'batting' | 'bowling'
  filter_team: string | null
  seasons: string[]
  wickets: number[]
  cells: { season: string; wicket_number: number; avg_runs: number | null; n: number }[]
}

export interface RivalrySummary {
  team1: string
  team2: string
  matches: number
  team1_wins: number
  team2_wins: number
  ties: number
  no_result: number
  last_match: {
    match_id: number; date: string | null
    winner: string | null; result: string | null; by: string | null
  } | null
  by_series_type: Record<string, number>
  top_scorer_in_rivalry: (PersonRef & { runs: number }) | null
  top_wicket_taker_in_rivalry: (PersonRef & { wickets: number }) | null
  highest_individual: (PersonRef & { runs: number; match_id: number; date: string | null }) | null
  largest_partnership: { runs: number; match_id: number } | null
  closest_match: { margin: string; winner: string; match_id: number; date: string | null } | null
  biggest_win: { winner: string; margin: string; match_id: number; date: string | null } | null
}

// ─── Venues (Phase 2) ────────────────────────────────────────────────

export interface VenueInfo {
  venue: string
  city: string | null
  country: string | null
  matches: number
}

export interface VenueLandingEntry {
  venue: string
  city: string | null
  matches: number
}

export interface VenueCountryGroup {
  country: string
  matches: number
  venues: VenueLandingEntry[]
}

export interface VenuesLanding {
  by_country: VenueCountryGroup[]
}

// ─── Venues (Phase 3 — dossier) ──────────────────────────────────────

export interface VenueTGSRow {
  tournament: string
  gender: string | null
  season: string
  matches: number
}

export interface VenueTotalEntry {
  runs: number
  team: string
  opponent: string
  match_id: number
  season: string | null
  date: string | null
}

export interface VenueTossWinEntry {
  wins: number
  decided: number
  win_pct: number | null
}

export interface VenueSummary {
  venue: string
  city: string | null
  country: string | null
  matches: number
  by_tournament_gender_season: VenueTGSRow[]
  avg_first_innings_total: number | null
  first_innings_sample: number
  bat_first_wins: number
  chase_wins: number
  indecisive: number
  bat_first_win_pct: number | null
  chase_win_pct: number | null
  toss_decision_split: Record<string, number>
  toss_and_win_pct: Record<string, VenueTossWinEntry>
  boundary_pct_by_phase: { powerplay: number | null; middle: number | null; death: number | null }
  dot_pct_by_phase: { powerplay: number | null; middle: number | null; death: number | null }
  highest_total: VenueTotalEntry | null
  lowest_all_out: VenueTotalEntry | null
}
