/**
 * Pure helpers for the batter Distribution panel histogram. Spec:
 * internal_docs/spec-distribution-stats.md §9.2.2.
 *
 * Bin definition: 21 width-10 bins from [0,9] through [190,199] +
 * a [200+] terminal catch-all = 22 bins (indices 0..21). For each
 * observation, `binIndex(runs)` returns 0..20 by `runs / 10` and 20
 * for any runs ≥ 200 (today the catch-all never fires — max is 172
 * Finch / 171 Gayle).
 *
 * Render rule: emit bins from index 0 through max(9, binIndex(maxRuns))
 * inclusive — always at least the 0-99 floor (10 bins) so a tail
 * batter's chart shows the empty right side and reads "this is a
 * bowler" at a glance. Above 99 the empty upper tail vanishes.
 */

export type RunsBinTier = 'failure' | 'building' | 'fifty' | 'century' | 'rare'

export interface RunsBinRow {
  /** Bin index (0..20). 20 = the [200+] catch-all. */
  bin: number
  /** Display label e.g. "0-9" or "200+". */
  label: string
  /** Inning count in this bin under the active window. */
  count: number
  /** Tier for color coding (matches WISDEN_RUN_TIERS keys). */
  tier: RunsBinTier
}

/** Bin index for a single innings score. */
export function binIndex(runs: number): number {
  if (runs >= 200) return 20
  if (runs < 0) return 0  // defensive — runs never negative in practice
  return Math.floor(runs / 10)
}

/** Display label for a bin. */
export function binLabel(idx: number): string {
  if (idx === 20) return '200+'
  return `${idx * 10}-${idx * 10 + 9}`
}

/** Tier for a bin (matches WISDEN_RUN_TIERS keys). */
export function binTier(idx: number): RunsBinTier {
  if (idx === 0) return 'failure'    // 0-9
  if (idx < 5) return 'building'     // 10-49
  if (idx < 10) return 'fifty'       // 50-99
  if (idx < 15) return 'century'     // 100-149
  return 'rare'                       // 150+
}

/**
 * Build the histogram row list for an observation set. Returns one
 * row per rendered bin, ordered low → high. Always renders bins
 * 0..9 (the 0-99 floor); extends further if any obs reaches a higher
 * bin.
 */
export function buildHistogramRows(observations: { runs: number }[]): RunsBinRow[] {
  const counts = new Array(22).fill(0)
  let maxRuns = -1
  for (const o of observations) {
    const i = binIndex(o.runs)
    counts[i] += 1
    if (o.runs > maxRuns) maxRuns = o.runs
  }
  const lastIdx = Math.max(9, maxRuns >= 0 ? binIndex(maxRuns) : 9)
  const rows: RunsBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: binLabel(i),
      count: counts[i],
      tier: binTier(i),
    })
  }
  return rows
}
