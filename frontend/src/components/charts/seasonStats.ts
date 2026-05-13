/** Std-dev of `rows.map(accessor)`, skipping null/undefined values.
 *  Returns null when fewer than 2 finite samples exist — caller's signal
 *  to omit `± σ` on the StatCard (spec-series-trend-charts.md §D4).
 *
 *  Uses the population formula (divide by N), not sample (N-1). We're
 *  treating the in-scope seasons as the population of interest, not a
 *  sample of some larger universe of imaginary seasons. */
export function seasonStdDev<T>(
  rows: readonly T[] | null | undefined,
  accessor: (r: T) => number | null | undefined,
): number | null {
  if (!rows || rows.length < 2) return null
  const vals: number[] = []
  for (const r of rows) {
    const v = accessor(r)
    if (typeof v === 'number' && Number.isFinite(v)) vals.push(v)
  }
  if (vals.length < 2) return null
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length
  const variance = vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length
  return Math.sqrt(variance)
}
