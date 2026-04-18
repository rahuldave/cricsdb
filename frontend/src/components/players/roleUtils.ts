import type { PlayerProfile, FilterParams } from '../../types'

// Per-discipline "has meaningful data" gates. Thresholds mirror the
// existing leaderboard minimums so a landing-ranked player doesn't
// render a row the leaderboard itself would have excluded.
export const hasBatting  = (p: PlayerProfile) => (p.batting?.innings ?? 0) > 0
export const hasBowling  = (p: PlayerProfile) => (p.bowling?.balls ?? 0) > 0
export const hasFielding = (p: PlayerProfile) => {
  const f = p.fielding
  if (!f) return false
  return (f.catches + f.stumpings + f.run_outs) > 0
}
export const hasKeeping  = (p: PlayerProfile) => (p.keeping?.innings_kept ?? 0) > 0

// Role-classification thresholds. These are stricter than the "has data"
// gates above — they decide whether someone is meaningfully a batter /
// bowler FOR THE IDENTITY LINE, not whether to render a row at all.
//
// Raw ball counts aren't enough: Bumrah has ~100 balls faced spread
// across 36 innings (≈2.8 balls/inn, avg < 3). He passes a raw
// "balls_faced >= 100" check but he's a #10 tail-ender, not a batter
// for our purposes. Similarly Kohli has 403 balls bowled across 388
// matches — a gimmick over here or there, not a bowler.
//
// "batted": needs a real sample (innings ≥ 5), substantive time at
// the crease (balls/inn ≥ 5), and a non-tailender average (≥ 10).
//
// "bowled": sufficient raw balls (≥ 60 = 10 overs), AND regular
// rotation into the attack — measured as balls per TOTAL career
// match, not balls per match-bowled-in. bowling.matches counts only
// matches where the bowler actually sent down a delivery, which
// flatters anyone who bowled once or twice. fielding.matches is the
// true denominator (everyone fields every match).
export const ROLE_BATTED_MIN_INNINGS        = 5
export const ROLE_BATTED_MIN_BALLS_PER_INN  = 5
export const ROLE_BATTED_MIN_AVERAGE        = 10
export const ROLE_BOWLED_MIN_BALLS          = 60
export const ROLE_BOWLED_MIN_BALLS_PER_MATCH = 3
export const KEEPING_INNINGS_THRESHOLD      = 3

/** Primary-role label for the identity line. See spec §"Primary-role
 *  label — definition" (thresholds refined in-repo to exclude tail-
 *  enders and one-over-a-season dabblers — see constants above).
 *  Recomputed per profile so narrowing scope can truthfully flip
 *  Kohli from "specialist batter" to "all-rounder" if he bowled
 *  meaningfully there. */
export function classifyRole(p: PlayerProfile): string {
  const b = p.batting
  const bw = p.bowling
  const batted = !!b
    && b.innings >= ROLE_BATTED_MIN_INNINGS
    && b.balls_faced / Math.max(b.innings, 1) >= ROLE_BATTED_MIN_BALLS_PER_INN
    && (b.average ?? 0) >= ROLE_BATTED_MIN_AVERAGE
  // Use total career matches (from fielding — everyone fields every
  // match) as the denominator, falling back to bowling.matches only
  // if fielding is missing for some reason.
  const totalMatches = Math.max(
    p.fielding?.matches ?? 0,
    p.batting?.matches  ?? 0,
    bw?.matches ?? 0,
    1,
  )
  const bowled = !!bw
    && bw.balls >= ROLE_BOWLED_MIN_BALLS
    && bw.balls / totalMatches >= ROLE_BOWLED_MIN_BALLS_PER_MATCH
  const kept = (p.keeping?.innings_kept ?? 0) >= KEEPING_INNINGS_THRESHOLD
  const fielded = hasFielding(p)

  if (kept && batted)      return 'keeper-batter'
  if (kept)                return 'wicketkeeper'
  if (batted && bowled)    return 'all-rounder'
  if (batted)              return 'specialist batter'
  if (bowled)              return 'specialist bowler'
  if (fielded)             return 'fielder'
  return 'no matches in scope'
}

/** "375 matches" — the larger of any discipline's match count, which
 *  handles specialist roles where one summary may be null. */
export function matchesInScope(p: PlayerProfile): number {
  return Math.max(
    p.batting?.matches  ?? 0,
    p.bowling?.matches  ?? 0,
    p.fielding?.matches ?? 0,
  )
}

/** Build the query-string carry for a discipline deep-dive link —
 *  all active FilterBar params plus the player ID. */
export function carryFilters(filters: FilterParams): Record<string, string> {
  const out: Record<string, string> = {}
  if (filters.gender)          out.gender          = filters.gender
  if (filters.team_type)       out.team_type       = filters.team_type
  if (filters.tournament)      out.tournament      = filters.tournament
  if (filters.season_from)     out.season_from     = filters.season_from
  if (filters.season_to)       out.season_to       = filters.season_to
  if (filters.filter_team)     out.filter_team     = filters.filter_team
  if (filters.filter_opponent) out.filter_opponent = filters.filter_opponent
  if (filters.filter_venue)    out.filter_venue    = filters.filter_venue
  return out
}
