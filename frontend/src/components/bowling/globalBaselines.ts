/**
 * Gender-tiered global baseline anchors for the bowler Distribution
 * sparkline. Spec: internal_docs/spec-distribution-stats.md §12.2.6.
 *
 * Empirical centres rounded to whole numbers, derived from
 * `cricket.db` at the date of writing (2026-05-06) across all
 * qualifying spells (≥12 legal balls):
 *
 *   Bucket             spells   wkts/spell   runs/spell   RPO
 *   ─────────────────  ──────   ──────────   ──────────   ────
 *   Men (intl + club)  92,322   1.08         26.2         7.8
 *   Women (intl+club)  31,703   0.97         20.0         6.1
 *   All T20           136,964   1.05         25.0         7.5
 *
 * Refresh script: see commit 6343779 — same SQL across delivery JOIN
 * innings JOIN match with HAVING legal_balls >= 12. Re-run yearly
 * if the cricket landscape shifts materially (women's tier-2
 * normalising upward, etc.).
 */

export interface GlobalBaselines {
  /** Mean wickets per qualifying spell. */
  wickets: number
  /** Mean runs conceded per qualifying spell. */
  runs: number
  /** Pool economy in RPO across qualifying spells. */
  rpo: number
}

/** All-T20 average — used when no gender filter is set. */
export const GLOBAL_ALL_T20: GlobalBaselines = {
  wickets: 1,
  runs: 25,
  rpo: 7,
}

export const GLOBAL_MEN: GlobalBaselines = {
  wickets: 1,
  runs: 26,
  rpo: 8,
}

export const GLOBAL_WOMEN: GlobalBaselines = {
  wickets: 1,
  runs: 20,
  rpo: 6,
}

/** Pick the right bucket from the active filter scope's gender field. */
export function pickGlobalBaseline(scope: Record<string, string>): GlobalBaselines {
  const g = scope.gender
  if (g === 'male') return GLOBAL_MEN
  if (g === 'female') return GLOBAL_WOMEN
  return GLOBAL_ALL_T20
}
