/**
 * Bins and tiers for the batter Distribution panel's runs and strike-rate histograms.
 *
 * Pure helpers for the batter Distribution panel histogram. Spec:
 * internal_docs/spec-distribution-stats.md §9.2.2.
 *
 * Bin definition: 20 width-10 bins from [0,9] through [190,199] +
 * a [200+] terminal catch-all = 21 bins (indices 0..20). For each
 * observation, `binIndex(runs)` returns 0..20 by `runs / 10` and 20
 * for any runs ≥ 200 (today the catch-all never fires — max is 172
 * Finch / 171 Gayle).
 *
 * Render rule: emit bins from index 0 through max(9, binIndex(maxRuns))
 * inclusive — always at least the 0-99 floor (10 bins) so a tail
 * batter's chart shows the empty right side and reads "this is a
 * bowler" at a glance. Above 99 the empty upper tail vanishes.
 * @packageDocumentation
 */

/** Tier of a runs bin: failure (0-9), building (10-49) or impact (50+). */
export type RunsBinTier = 'failure' | 'building' | 'impact'

/** One bar of the runs histogram. */
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

/**
 * Bin index for a single innings score.
 * @param runs the runs scored in the innings
 * @returns the bin index, `runs / 10` rounded down, or 20 for 200 and more
 */
export function binIndex(runs: number): number {
  if (runs >= 200) return 20
  if (runs < 0) return 0  // defensive — runs never negative in practice
  return Math.floor(runs / 10)
}

/**
 * Display label for a bin.
 * @param idx the bin index
 * @returns the label, such as "0-9", or "200+" for bin 20
 */
export function binLabel(idx: number): string {
  if (idx === 20) return '200+'
  return `${idx * 10}-${idx * 10 + 9}`
}

/**
 * Tier for a bin (matches WISDEN_RUN_TIERS keys). 3-tier collapse:
 *  failure (0-9) / building (10-49) / impact (50+).
 * @param idx the bin index
 * @returns the bin's tier
 */
export function binTier(idx: number): RunsBinTier {
  if (idx === 0) return 'failure'   // 0-9
  if (idx < 5) return 'building'    // 10-49
  return 'impact'                    // 50+
}

// ─── Strike Rate bins + tiers ───────────────────────────────────────

/** Tier of a strike-rate bin: slow (under 100), mid (100-149) or explosive (150+). */
export type SRBinTier = 'slow' | 'mid' | 'explosive'

/** One bar of the strike-rate histogram. */
export interface SRBinRow {
  bin: number // the bin index, 0..8; 8 is the "200+" catch-all
  label: string // the display label, such as "100-124" or "200+"
  count: number // the number of innings in this bin
  tier: SRBinTier // the tier for colour coding
}

/**
 * Width-25 SR bin index. SR ≥ 200 → 8 (terminal "200+").
 * @param sr the strike rate of one innings
 * @returns the bin index, 0..8
 */
export function srBinIndex(sr: number): number {
  if (sr >= 200) return 8
  if (sr < 0) return 0
  return Math.floor(sr / 25)
}

/**
 * Display label for a strike-rate bin.
 * @param idx the bin index
 * @returns the label, such as "0-24", or "200+" for bin 8
 */
export function srBinLabel(idx: number): string {
  if (idx === 8) return '200+'
  return `${idx * 25}-${idx * 25 + 24}`
}

/**
 * Tier for a strike-rate bin. 3-tier collapse: slow (<100) / mid (100-149) / explosive (150+).
 * @param idx the bin index
 * @returns the bin's tier
 */
export function srBinTier(idx: number): SRBinTier {
  if (idx < 4) return 'slow'        // 0-99
  if (idx < 6) return 'mid'         // 100-149
  return 'explosive'                 // 150+
}

/**
 * Per-innings SR from runs+balls. 0-ball innings → 0.
 * @param runs the runs scored
 * @param balls the balls faced
 * @returns the strike rate to one decimal place, or 0 when no balls were faced
 */
export function perInningsSR(runs: number, balls: number): number {
  return balls > 0 ? +(runs * 100 / balls).toFixed(1) : 0
}

/**
 * Build the strike-rate histogram rows, low to high, always through bin 6 (150-174).
 * Innings with a null `strike_rate` (no balls faced) are skipped.
 */
export function buildSRHistogramRows(
  observations: { runs: number; balls: number; strike_rate: number | null }[], // the innings, with the server's strike rate
): SRBinRow[] { // one row per rendered bin
  const counts = new Array(9).fill(0)
  let maxSR = -1
  for (const o of observations) {
    // Server-computed strike_rate (audit §4.5). Null only when balls=0;
    // skip those observations from the SR histogram (no SR to bin).
    if (o.strike_rate === null) continue
    const sr = o.strike_rate
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
 * @param observations the innings, each with its runs
 * @returns one row per rendered bin
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
