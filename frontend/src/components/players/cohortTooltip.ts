/** Tooltip phrasing for the "vs cohort N" line on player baseline tiles.
 *
 *  Spec: docs/internal/spec-player-compare-average.md §3.4.
 *
 *  Two phrasings depending on mix concentration:
 *    - Concentrated (one bucket ≥ 0.70):
 *        "Position-mix cohort — Opener (54% of innings); 287
 *         players in cohort"
 *    - Spread (no bucket ≥ 0.70):
 *        "Position-mix cohort — Opener 54%, #3 28%, #4 12%, #5 6%;
 *         cohort: 412 players, 8,917 innings"
 *
 *  Fielding (keeper/outfielder binary) uses a different phrasing
 *  shape — no mix; the partition is named directly:
 *    "Keeper-cohort baseline — 232 keepers, 2,166 keeping matches"
 *    "Outfielder-cohort baseline — 1,247 outfielders, 42,891 matches"
 */
import type {
  BattingCohortMeta,
  BowlingCohortMeta,
  FieldingCohortMeta,
  KeepingCohortMeta,
} from '../../types'


function batting_bucket_label(b: number): string {
  return b === 1 ? 'Opener' : `#${b + 1}`
}


/**
 * Name a baseline bucket: 'Opener' or '#N' for a batting or fielding position, 'Over N' for bowling.
 * @param kind the discipline the bucket belongs to
 * @param bucket the 1-based bucket number; batting bucket 1 is positions 1 and 2 merged
 * @returns the label
 */
export function bucketLabel(kind: 'batting' | 'bowling' | 'fielding', bucket: number): string {
  if (kind === 'batting' || kind === 'fielding') {
    return batting_bucket_label(bucket)
  }
  return `Over ${bucket}`
}


function fmtPct(x: number): string {
  // Drop the trailing ".0" on integer percentages.
  const pct = Math.round(x * 1000) / 10
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`
}


function fmtCount(n: number): string {
  return n.toLocaleString()
}


/**
 * Describe a batting cohort for a tooltip: its position mix, the number of players and, when the mix is spread, of innings.
 * @param cohort the cohort's position mix and counts
 * @returns the tooltip text
 */
export function battingCohortTooltip(cohort: BattingCohortMeta): string {
  const mix = cohort.position_mix
  const concentrated = mix.findIndex(w => w >= 0.70)
  if (concentrated >= 0) {
    const label = batting_bucket_label(concentrated + 1)
    return (
      `Position-mix cohort — ${label} (${fmtPct(mix[concentrated])} of innings); `
      + `${fmtCount(cohort.n_players)} players`
    )
  }
  // Spread — list every non-trivial bucket (> 1%) in descending weight.
  const entries = mix
    .map((w, i) => ({ bucket: i + 1, w }))
    .filter(e => e.w >= 0.01)
    .sort((a, b) => b.w - a.w)
    .map(e => `${batting_bucket_label(e.bucket)} ${fmtPct(e.w)}`)
    .join(', ')
  return (
    `Position-mix cohort — ${entries}; `
    + `${fmtCount(cohort.n_players)} players, `
    + `${fmtCount(cohort.n_innings_total)} innings`
  )
}


/**
 * Describe a bowling cohort for a tooltip: its over mix (at most 8 overs), the number of bowlers and, when the mix is spread, of balls.
 * @param cohort the cohort's over mix and counts
 * @returns the tooltip text
 */
export function bowlingCohortTooltip(cohort: BowlingCohortMeta): string {
  const mix = cohort.over_mix
  const concentrated = mix.findIndex(w => w >= 0.70)
  if (concentrated >= 0) {
    return (
      `Over-mix cohort — Over ${concentrated + 1} (${fmtPct(mix[concentrated])} of balls); `
      + `${fmtCount(cohort.n_players)} bowlers`
    )
  }
  const entries = mix
    .map((w, i) => ({ over: i + 1, w }))
    .filter(e => e.w >= 0.01)
    .sort((a, b) => b.w - a.w)
    .slice(0, 8) // Cap at top-8 overs — 20-bucket spreads get verbose.
    .map(e => `Over ${e.over} ${fmtPct(e.w)}`)
    .join(', ')
  return (
    `Over-mix cohort — ${entries}; `
    + `${fmtCount(cohort.n_players)} bowlers, `
    + `${fmtCount(cohort.n_balls_total)} balls`
  )
}


/**
 * Describe a fielding cohort for a tooltip: keepers or outfielders, and how many fielders and matches it holds.
 * @param cohort the cohort's keeper flag and counts
 * @returns the tooltip text
 */
export function fieldingCohortTooltip(cohort: FieldingCohortMeta): string {
  const partition = cohort.is_keeper ? 'Keeper' : 'Outfielder'
  const partitionPlural = cohort.is_keeper ? 'keepers' : 'outfielders'
  return (
    `${partition} cohort — `
    + `${fmtCount(cohort.n_fielders)} ${partitionPlural}, `
    + `${fmtCount(cohort.n_matches_total)} matches`
  )
}


/**
 * Describe a keeping cohort for a tooltip: how many keepers and keeping matches it holds.
 * @param cohort the cohort's counts
 * @returns the tooltip text
 */
export function keepingCohortTooltip(cohort: KeepingCohortMeta): string {
  return (
    `Keeping cohort — `
    + `${fmtCount(cohort.n_keepers)} keepers, `
    + `${fmtCount(cohort.n_matches_keeping)} keeping matches`
  )
}


// ─── One-line cohort summaries ───────────────────────────────────────
//
// Short phrases for the COHORT line on ScopedPageHeader (the second
// row that sits below the SCOPE pill on Batting / Bowling / Fielding).
// The tooltips above retain the full mix breakdown for hover.
//
// Every "{scope}" token is replaced by ScopedPageHeader with a small-
// caps oxblood inline marker so the reader's eye links the phrase
// back to the SCOPE line above.

/**
 * Return the one-line batting cohort phrase for `ScopedPageHeader`, with a `{scope}` token to replace.
 * @param _cohort unused; the phrase is the same for every cohort
 * @returns the phrase
 */
export function battingCohortLine(_cohort: BattingCohortMeta | null): string {
  return "all batters at {scope}, weighted to this player's position mix"
}

/**
 * Return the one-line bowling cohort phrase for `ScopedPageHeader`, with a `{scope}` token to replace.
 * @param _cohort unused; the phrase is the same for every cohort
 * @returns the phrase
 */
export function bowlingCohortLine(_cohort: BowlingCohortMeta | null): string {
  return "all bowlers at {scope}, weighted to this player's over mix"
}

/**
 * Return the one-line fielding cohort phrase for `ScopedPageHeader`, with a `{scope}` token to replace.
 * @param cohort the cohort; a keeper cohort gets the keeper phrase, anything else the outfielder one
 * @returns the phrase
 */
export function fieldingCohortLine(cohort: FieldingCohortMeta | null): string {
  if (cohort?.is_keeper === 1) return 'every keeper in this {scope}'
  return 'every outfielder in this {scope}'
}
