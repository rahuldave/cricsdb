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
