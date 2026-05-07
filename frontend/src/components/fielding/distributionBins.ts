/**
 * Discrete bin helpers for the fielder Distribution panel histograms.
 * Spec: internal_docs/spec-distribution-stats.md §14.2.3.
 *
 * Three fixed bins per metric tab: 0 / 1 / ≥2. Catches max ~5/match,
 * stumpings ~3, run-outs ~2 in T20 — collapsing 2+ into a single
 * tier keeps the visual contract aligned with the three-tier palette
 * (INDIGO/SAGE/OCHRE) and the matching ProbChip tints.
 */

export type CountBinTier = 'zero' | 'one' | 'multi'

export interface CountBinRow {
  bin: number          // 0, 1, 2 (where 2 means "≥2")
  label: string        // "0", "1", "≥2"
  count: number
  tier: CountBinTier
}

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
  observations: { [k: string]: number }[],
  key: string,
): CountBinRow[] {
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
