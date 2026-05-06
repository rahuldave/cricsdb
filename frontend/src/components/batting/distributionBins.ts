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

export type RunsBinTier = 'failure' | 'building' | 'impact'

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

/** Tier for a bin (matches WISDEN_RUN_TIERS keys). 3-tier collapse:
 *  failure (0-9) / building (10-49) / impact (50+). */
export function binTier(idx: number): RunsBinTier {
  if (idx === 0) return 'failure'   // 0-9
  if (idx < 5) return 'building'    // 10-49
  return 'impact'                    // 50+
}

// ─── Strike Rate bins + tiers ───────────────────────────────────────

export type SRBinTier = 'slow' | 'mid' | 'explosive'

export interface SRBinRow {
  bin: number
  label: string
  count: number
  tier: SRBinTier
}

/** Width-25 SR bin index. SR ≥ 200 → 8 (terminal "200+"). */
export function srBinIndex(sr: number): number {
  if (sr >= 200) return 8
  if (sr < 0) return 0
  return Math.floor(sr / 25)
}

export function srBinLabel(idx: number): string {
  if (idx === 8) return '200+'
  return `${idx * 25}-${idx * 25 + 24}`
}

/** 3-tier collapse: slow (<100) / mid (100-149) / explosive (150+). */
export function srBinTier(idx: number): SRBinTier {
  if (idx < 4) return 'slow'        // 0-99
  if (idx < 6) return 'mid'         // 100-149
  return 'explosive'                 // 150+
}

/** Per-innings SR from runs+balls. 0-ball innings → 0. */
export function perInningsSR(runs: number, balls: number): number {
  return balls > 0 ? +(runs * 100 / balls).toFixed(1) : 0
}

export function buildSRHistogramRows(
  observations: { runs: number; balls: number }[],
): SRBinRow[] {
  const counts = new Array(9).fill(0)
  let maxSR = -1
  for (const o of observations) {
    if (o.balls === 0) continue
    const sr = perInningsSR(o.runs, o.balls)
    const i = srBinIndex(sr)
    counts[i] += 1
    if (sr > maxSR) maxSR = sr
  }
  // Always render through bin index 6 ([150,174]) so a "no fast
  // innings" right-side reads at-a-glance as anchor signal.
  const lastIdx = Math.max(6, maxSR >= 0 ? srBinIndex(maxSR) : 6)
  const rows: SRBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: srBinLabel(i),
      count: counts[i],
      tier: srBinTier(i),
    })
  }
  return rows
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
