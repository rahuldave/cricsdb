export interface FilterParams {
  gender?: string
  team_type?: string
  tournament?: string
  season_from?: string
  season_to?: string
  team?: string
  opponent?: string
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

export interface TeamSummary {
  team: string
  matches: number
  wins: number
  losses: number
  ties: number
  no_results: number
  win_pct: number | null
  toss_wins: number
  bat_first_wins: number
  field_first_wins: number
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

export interface TeamVsOpponent {
  team: string
  opponent: string
  overall: { matches: number; wins: number; losses: number; ties: number }
  by_season: TeamSeasonRecord[]
  matches: TeamResult[]
}

export interface BattingSummary {
  person_id: string
  name: string
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
  batter: { id: string; name: string }
  bowler: { id: string; name: string }
  summary: HeadToHeadSummary
  dismissal_kinds: Record<string, number>
  by_over: { over_number: number; balls: number; runs: number; wickets: number }[]
  by_phase: { phase: string; balls: number; runs: number; wickets: number; strike_rate: number | null }[]
  by_season: { season: string; balls: number; runs: number; wickets: number; strike_rate: number | null }[]
  by_match: HeadToHeadMatch[]
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
  batter: string
  batter_index: number
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
  deliveries: InningsGridDelivery[]
  total_balls: number
  total_runs: number
  total_wickets: number
}

export interface InningsGridResponse {
  match_id: number
  innings: InningsGridInnings[]
}
