/**
 * Bins and tiers for the bowler Distribution panel's wickets, economy and runs-conceded histograms.
 *
 * Pure helpers for the bowler Distribution panel histograms. Spec:
 * docs/internal/spec-distribution-stats.md §12.2.2 / §12.2.3 / §12.2.4.
 *
 * Three different bin schemes — discrete wickets, continuous economy
 * (per-over rate), continuous runs-conceded — each with its own
 * "always-show-through" floor that makes a non-strike bowler's empty
 * upper-tail recognizable at a glance.
 * @packageDocumentation
 */

// ─── Wickets — discrete integer bars ────────────────────────────────

/** Tier of a wickets bin: wicketless (0), building (1-2) or strike (3+). */
export type WicketBinTier = 'wicketless' | 'building' | 'strike'

/** One bar of the wickets histogram. */
export interface WicketBinRow {
  bin: number          // 0..6, 6 means "6+" catch-all
  label: string        // "0", "1", ..., "5", "6+"
  count: number // the number of innings in this bin
  tier: WicketBinTier // the tier for colour coding
}

/**
 * Discrete wicket bin. 0..5 are exact integer values; 6 is the
 * "6+ wickets" catch-all (rare in T20; one bowler has hit 7 in our
 * dataset, none have hit 8).
 * @param w the wickets taken in one innings
 * @returns the bin index, 0..6
 */
export function wicketBin(w: number): number {
  if (w >= 6) return 6
  if (w < 0) return 0
  return w
}

/**
 * Display label for a wickets bin.
 * @param idx the bin index
 * @returns the label, such as "3", or "6+" for bin 6
 */
export function wicketLabel(idx: number): string {
  if (idx === 6) return '6+'
  return String(idx)
}

/**
 * Tier for a wickets bin.
 * @param idx the bin index
 * @returns wicketless for 0, building for 1-2, strike for 3 and more
 */
export function wicketTier(idx: number): WicketBinTier {
  if (idx === 0) return 'wicketless'
  if (idx <= 2) return 'building'   // 1-2
  return 'strike'                    // 3+
}

/**
 * Build wicket histogram rows. Always renders bins 0..5 (the
 * "show through 5+" floor — see spec §12.2.2 — so a non-strike
 * bowler's chart shows the empty right side and reads "this isn't
 * a wicket-taker" at a glance). Extends to bin 6 only when an
 * observation reaches 6+.
 */
export function buildWicketHistogramRows(
  observations: { wickets: number }[], // the innings, each with its wickets
): WicketBinRow[] { // one row per rendered bin, low to high
  const counts = new Array(7).fill(0)
  let maxWkts = 0
  for (const o of observations) {
    const i = wicketBin(o.wickets)
    counts[i] += 1
    if (o.wickets > maxWkts) maxWkts = o.wickets
  }
  const lastIdx = Math.max(5, wicketBin(maxWkts))
  const rows: WicketBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: wicketLabel(i),
      count: counts[i],
      tier: wicketTier(i),
    })
  }
  return rows
}

// ─── Economy — continuous, width-1 RPO bins ─────────────────────────

/** One bar of the economy histogram. */
export interface EconomyBinRow {
  /** Bin index 0..N. Bin i covers [3+i, 4+i) RPO. */
  bin: number
  label: string  // "<4", "4-5", ..., "12-13", "13+"
  count: number // the number of innings in this bin
  tier: LowerIsBetterTier // the tier for colour coding
}

/** Tier for an economy bin index (3-tier: tight / mid / loose). */
function economyBinTier(idx: number): LowerIsBetterTier {
  if (idx <= 3) return 'tight'   // bins covering RPO < 7
  if (idx <= 5) return 'mid'     // 7-9 RPO
  return 'loose'                  // ≥ 9 RPO
}

/**
 * Economy bin. RPO < 4 → 0 (under-4 catch); RPO ≥ 13 → 10 (13+ catch).
 * Otherwise floor(econ - 3): [4,5)→1, [5,6)→2, ..., [12,13)→9.
 * @param rpo the economy of one innings, in runs per over
 * @returns the bin index, 0..10
 */
export function economyBin(rpo: number): number {
  if (rpo < 4) return 0
  if (rpo >= 13) return 10
  return Math.floor(rpo - 3)
}

/**
 * Display label for an economy bin.
 * @param idx the bin index
 * @returns the label: "<4" for bin 0, "13+" for bin 10, otherwise such as "6-7"
 */
export function economyLabel(idx: number): string {
  if (idx === 0) return '<4'
  if (idx === 10) return '13+'
  const lo = idx + 3
  return `${lo}-${lo + 1}`
}

/**
 * Build the economy histogram rows, low to high.
 *
 * Always-render-through floor at index 9 (covers [3, 13)) so every
 * bowler's chart spans the same x-axis — comparable across players.
 */
export function buildEconomyHistogramRows(
  perInnings: number[], // the economy of each innings, in runs per over
): EconomyBinRow[] { // one row per rendered bin
  const counts = new Array(11).fill(0)
  let maxRpo = 0
  for (const e of perInnings) {
    const i = economyBin(e)
    counts[i] += 1
    if (e > maxRpo) maxRpo = e
  }
  const lastIdx = Math.max(9, economyBin(maxRpo))
  const rows: EconomyBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: economyLabel(i),
      count: counts[i],
      tier: economyBinTier(i),
    })
  }
  return rows
}

// ─── Economy tier (sparkline bar coloring) ──────────────────────────
//
// Lower-is-better metric. Uses the same color ladder shape as the
// wickets tiers but with reversed polarity (ochre at the LOW end =
// good economy; indigo at the HIGH end = bad economy).

/** Tier of a metric where lower is better, such as economy or runs conceded. */
export type LowerIsBetterTier = 'tight' | 'mid' | 'loose'

/**
 * Economy tier — < 7 tight, 7-9 mid, ≥ 9 loose.
 * @param rpo the economy, in runs per over
 * @returns the tier
 */
export function economyTier(rpo: number): LowerIsBetterTier {
  if (rpo < 7) return 'tight'
  if (rpo < 9) return 'mid'
  return 'loose'
}

/**
 * Runs-conceded tier — ≤ 25 tight, 25-40 mid, > 40 loose.
 * @param runs the runs conceded in one innings
 * @returns the tier
 */
export function runsConcededTier(runs: number): LowerIsBetterTier {
  if (runs <= 25) return 'tight'
  if (runs <= 40) return 'mid'
  return 'loose'
}

// ─── Runs conceded — continuous, width-5 bins ───────────────────────

/** One bar of the runs-conceded histogram. */
export interface RunsConcededBinRow {
  bin: number // the bin index, 0..12; 12 is the "60+" catch-all
  label: string  // "0-4", "5-9", ..., "55-59", "60+"
  count: number // the number of innings in this bin
  tier: LowerIsBetterTier // the tier for colour coding
}

/** Tier for a runs-conceded bin index (3-tier: tight / mid / loose).
 *  Bin width 5 starting at 0; thresholds at 25 and 40 runs. */
function runsConcededBinTier(idx: number): LowerIsBetterTier {
  if (idx <= 4) return 'tight'   // 0-24 runs
  if (idx <= 7) return 'mid'     // 25-39 runs
  return 'loose'                  // 40+ runs
}

/**
 * Width-5 bin. runs ≥ 60 → 12 (60+ catch).
 * @param runs the runs conceded in one innings
 * @returns the bin index, 0..12
 */
export function runsConcededBin(runs: number): number {
  if (runs >= 60) return 12
  if (runs < 0) return 0
  return Math.floor(runs / 5)
}

/**
 * Display label for a runs-conceded bin.
 * @param idx the bin index
 * @returns the label, such as "5-9", or "60+" for bin 12
 */
export function runsConcededLabel(idx: number): string {
  if (idx === 12) return '60+'
  const lo = idx * 5
  return `${lo}-${lo + 4}`
}

/**
 * Build the runs-conceded histogram rows, low to high.
 *
 * Always render through index 11 (covers [0, 60)) — 12 bins. Tail
 * extends only when an observation reaches 60+.
 */
export function buildRunsConcededHistogramRows(
  observations: { runs_conceded: number }[], // the innings, each with its runs conceded
): RunsConcededBinRow[] { // one row per rendered bin
  const counts = new Array(13).fill(0)
  let maxRuns = 0
  for (const o of observations) {
    const i = runsConcededBin(o.runs_conceded)
    counts[i] += 1
    if (o.runs_conceded > maxRuns) maxRuns = o.runs_conceded
  }
  const lastIdx = Math.max(11, runsConcededBin(maxRuns))
  const rows: RunsConcededBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: runsConcededLabel(i),
      count: counts[i],
      tier: runsConcededBinTier(i),
    })
  }
  return rows
}
