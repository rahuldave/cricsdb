/**
 * Gender-tiered global baseline anchors for distribution sparklines.
 * Spec: internal_docs/spec-distribution-stats.md §12.2.6.
 *
 * Empirical centres rounded to whole numbers, derived from
 * `cricket.db` at the date of writing (2026-05-06).
 *
 * Bowling — across all qualifying spells (≥12 legal balls):
 *
 *   Bucket             spells   wkts/spell   runs/spell   RPO
 *   ─────────────────  ──────   ──────────   ──────────   ────
 *   Men (intl + club)  92,322   1.08         26.2         7.8
 *   Women (intl+club)  31,703   0.97         20.0         6.1
 *   All T20           136,964   1.05         25.0         7.5
 *
 * Batting — per-innings (no min-balls filter; every innings counts):
 *
 *   Bucket             innings  runs/inn  balls/inn  SR
 *   ─────────────────  ───────  ────────  ─────────  ─────
 *   All men           157,832   17.6      14.0       125
 *   All women          46,579   13.3      14.0       95
 *   All T20           204,411   16.6      14.0       118
 *
 * Refresh script: see commit 91eaaad (bowling) + this module's
 * commit (batting). Same SQL pattern: per-innings aggregation
 * grouped by gender, AVG(value), pool ratio for SR/RPO.
 */

export interface GlobalBowlingBaselines {
  /** Mean wickets per qualifying spell. */
  wickets: number
  /** Mean runs conceded per qualifying spell. */
  runs: number
  /** Pool economy in RPO across qualifying spells. */
  rpo: number
}

export interface GlobalBattingBaselines {
  /** Mean runs per innings (no min-balls floor). */
  runs: number
  /** Pool strike rate (runs × 100 / balls faced) across innings. */
  sr: number
}

// ─── Bowling baselines ────────────────────────────────────────────────

export const BOWLING_GLOBAL_ALL_T20: GlobalBowlingBaselines = {
  wickets: 1, runs: 25, rpo: 7,
}
export const BOWLING_GLOBAL_MEN: GlobalBowlingBaselines = {
  wickets: 1, runs: 26, rpo: 8,
}
export const BOWLING_GLOBAL_WOMEN: GlobalBowlingBaselines = {
  wickets: 1, runs: 20, rpo: 6,
}

export function pickBowlingBaseline(
  scope: Record<string, string>,
): GlobalBowlingBaselines {
  const g = scope.gender
  if (g === 'male') return BOWLING_GLOBAL_MEN
  if (g === 'female') return BOWLING_GLOBAL_WOMEN
  return BOWLING_GLOBAL_ALL_T20
}

// ─── Batting baselines ────────────────────────────────────────────────

export const BATTING_GLOBAL_ALL_T20: GlobalBattingBaselines = {
  runs: 17, sr: 118,
}
export const BATTING_GLOBAL_MEN: GlobalBattingBaselines = {
  runs: 18, sr: 125,
}
export const BATTING_GLOBAL_WOMEN: GlobalBattingBaselines = {
  runs: 13, sr: 95,
}

export function pickBattingBaseline(
  scope: Record<string, string>,
): GlobalBattingBaselines {
  const g = scope.gender
  if (g === 'male') return BATTING_GLOBAL_MEN
  if (g === 'female') return BATTING_GLOBAL_WOMEN
  return BATTING_GLOBAL_ALL_T20
}

// ─── Team-batting baselines ───────────────────────────────────────────
//
// Per-innings team batting (super-over excluded), 2026-05-08 snapshot:
//
//   Bucket             innings  runs/inn  mean RR  pool RR
//   ─────────────────  ───────  ────────  ───────  ───────
//   All men             19,952  147.7     8.03     7.99
//   All women            6,088  112.4     6.34     6.28
//   All T20             26,040  139.5     7.63     7.60
//
// Whole-number rounded per spec §17.2 — "men's IPL team innings ≈ 167
// runs" is an IPL-specific anchor; gender-global is a wider centre.

export interface GlobalTeamBattingBaselines {
  /** Mean runs per innings at team grain. */
  runs: number
  /** Pool RR — total_runs * 6 / total_balls (balls-weighted). */
  rr: number
}

export const TEAM_BATTING_GLOBAL_ALL_T20: GlobalTeamBattingBaselines = {
  runs: 140, rr: 8,
}
export const TEAM_BATTING_GLOBAL_MEN: GlobalTeamBattingBaselines = {
  runs: 148, rr: 8,
}
export const TEAM_BATTING_GLOBAL_WOMEN: GlobalTeamBattingBaselines = {
  runs: 112, rr: 6,
}

export function pickTeamBattingBaseline(
  scope: Record<string, string>,
): GlobalTeamBattingBaselines {
  const g = scope.gender
  if (g === 'male') return TEAM_BATTING_GLOBAL_MEN
  if (g === 'female') return TEAM_BATTING_GLOBAL_WOMEN
  return TEAM_BATTING_GLOBAL_ALL_T20
}

// ─── Team-bowling baselines ───────────────────────────────────────────
//
// Per-innings team bowling — same denominator as team-batting (every
// batting innings is a bowling-team innings). 2026-05-08 snapshot:
//
//   Bucket             innings  wkts/inn  runs/inn  pool RPO
//   ─────────────────  ───────  ────────  ────────  ────────
//   All men             19,952  6.28      147.7     7.99
//   All women            6,088  6.05      112.4     6.28
//   All T20             26,040  6.23      139.5     7.60
//
// Wicket-counting follows §16.3.1's team-credited 4-kind exclusion
// list (run-outs counted; retired/obstructing excluded). Whole-number
// rounded per spec §17.2.

export interface GlobalTeamBowlingBaselines {
  /** Mean wickets credited per team-innings. */
  wickets: number
  /** Mean runs conceded per team-innings. */
  runs: number
  /** Pool RPO — total_runs_conceded × 6 / total_legal_balls. */
  rpo: number
}

export const TEAM_BOWLING_GLOBAL_ALL_T20: GlobalTeamBowlingBaselines = {
  wickets: 6, runs: 140, rpo: 8,
}
export const TEAM_BOWLING_GLOBAL_MEN: GlobalTeamBowlingBaselines = {
  wickets: 6, runs: 148, rpo: 8,
}
export const TEAM_BOWLING_GLOBAL_WOMEN: GlobalTeamBowlingBaselines = {
  wickets: 6, runs: 112, rpo: 6,
}

export function pickTeamBowlingBaseline(
  scope: Record<string, string>,
): GlobalTeamBowlingBaselines {
  const g = scope.gender
  if (g === 'male') return TEAM_BOWLING_GLOBAL_MEN
  if (g === 'female') return TEAM_BOWLING_GLOBAL_WOMEN
  return TEAM_BOWLING_GLOBAL_ALL_T20
}

// ─── Team-fielding baselines ──────────────────────────────────────────
//
// Per-innings team fielding (super-over excluded), 2026-05-08 snapshot.
// Catches exclude substitutes per spec §16.4.
//
//   Bucket             innings  catches/inn  run_outs/inn  stumpings/inn
//   ─────────────────  ───────  ───────────  ────────────  ─────────────
//   All men             19,952  3.93         0.54          0.18
//   All women            6,088  2.86         0.99          0.33
//   All T20             26,040  3.68         0.65          0.21
//
// Whole-number rounded for the integer-y metrics (catches, run_outs);
// stumpings rounds to 0 across the board so the gender-global line
// won't render visibly — the scope-baseline (team's lifetime mean,
// typically ~0.2-0.5) becomes the visible reference on that tab.

export interface GlobalTeamFieldingBaselines {
  /** Mean catches per team-innings (substitute catches excluded). */
  catches: number
  /** Mean run-outs per team-innings. */
  run_outs: number
  /** Mean stumpings per team-innings — typically 0 at whole-number resolution. */
  stumpings: number
}

export const TEAM_FIELDING_GLOBAL_ALL_T20: GlobalTeamFieldingBaselines = {
  catches: 4, run_outs: 1, stumpings: 0,
}
export const TEAM_FIELDING_GLOBAL_MEN: GlobalTeamFieldingBaselines = {
  catches: 4, run_outs: 1, stumpings: 0,
}
export const TEAM_FIELDING_GLOBAL_WOMEN: GlobalTeamFieldingBaselines = {
  catches: 3, run_outs: 1, stumpings: 0,
}

export function pickTeamFieldingBaseline(
  scope: Record<string, string>,
): GlobalTeamFieldingBaselines {
  const g = scope.gender
  if (g === 'male') return TEAM_FIELDING_GLOBAL_MEN
  if (g === 'female') return TEAM_FIELDING_GLOBAL_WOMEN
  return TEAM_FIELDING_GLOBAL_ALL_T20
}
