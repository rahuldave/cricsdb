/**
 * Discrete bin helpers for the fielder Distribution panel histograms.
 *
 * Spec: docs/internal/spec-distribution-stats.md §14.2.3.
 *
 * Three fixed bins per metric tab: 0 / 1 / ≥2. Catches max ~5/match,
 * stumpings ~3, run-outs ~2 in T20 — collapsing 2+ into a single
 * tier keeps the visual contract aligned with the three-tier palette
 * (INDIGO/SAGE/OCHRE) and the matching ProbChip tints.
 * @packageDocumentation
 */

/** The tier of a count bin: `zero`, `one`, or `multi` for 2 or more. */
export type CountBinTier = 'zero' | 'one' | 'multi'

/** One bar of the count histogram. */
export interface CountBinRow {
  bin: number          // 0, 1, 2 (where 2 means "≥2")
  label: string        // "0", "1", "≥2"
  count: number        // the number of matches in this bin
  tier: CountBinTier   // the tier, which picks the bar colour
}

/**
 * Return the tier of a bin.
 * @param bin the bin: 0, 1, or 2 for 2 or more
 * @returns `zero`, `one` or `multi`
 */
export function countBinTier(bin: number): CountBinTier {
  if (bin === 0) return 'zero'
  if (bin === 1) return 'one'
  return 'multi'
}

/**
 * Build the fixed three-bar histogram. Always renders all three bins
 * (no "show-through" logic needed at three bars). The zero bar is
 * almost always tallest; the chart axis auto-scales.
 */
export function buildCountHistogramRows(
  observations: { [k: string]: number }[], // one row per match
  key: string, // the metric to count, such as `catches`; a missing value counts as 0
): CountBinRow[] { // the three bars 0, 1 and ≥2, in that order
  const counts = [0, 0, 0]  // index 0 = =0, 1 = =1, 2 = ≥2
  for (const o of observations) {
    const v = o[key] ?? 0
    if (v <= 0) counts[0] += 1
    else if (v === 1) counts[1] += 1
    else counts[2] += 1
  }
  return [
    { bin: 0, label: '0',  count: counts[0], tier: 'zero' },
    { bin: 1, label: '1',  count: counts[1], tier: 'one' },
    { bin: 2, label: '≥2', count: counts[2], tier: 'multi' },
  ]
}
