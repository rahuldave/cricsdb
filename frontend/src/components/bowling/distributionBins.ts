/**
 * Pure helpers for the bowler Distribution panel histograms. Spec:
 * internal_docs/spec-distribution-stats.md §12.2.2 / §12.2.3 / §12.2.4.
 *
 * Three different bin schemes — discrete wickets, continuous economy
 * (per-over rate), continuous runs-conceded — each with its own
 * "always-show-through" floor that makes a non-strike bowler's empty
 * upper-tail recognizable at a glance.
 */

// ─── Wickets — discrete integer bars ────────────────────────────────

export type WicketBinTier = 'wicketless' | 'building' | 'strike'

export interface WicketBinRow {
  bin: number          // 0..6, 6 means "6+" catch-all
  label: string        // "0", "1", ..., "5", "6+"
  count: number
  tier: WicketBinTier
}

/**
 * Discrete wicket bin. 0..5 are exact integer values; 6 is the
 * "6+ wickets" catch-all (rare in T20; one bowler has hit 7 in our
 * dataset, none have hit 8).
 */
export function wicketBin(w: number): number {
  if (w >= 6) return 6
  if (w < 0) return 0
  return w
}

export function wicketLabel(idx: number): string {
  if (idx === 6) return '6+'
  return String(idx)
}

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
  observations: { wickets: number }[],
): WicketBinRow[] {
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

export interface EconomyBinRow {
  /** Bin index 0..N. Bin i covers [3+i, 4+i) RPO. */
  bin: number
  label: string  // "<4", "4-5", ..., "12-13", "13+"
  count: number
  tier: LowerIsBetterTier
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
 */
export function economyBin(rpo: number): number {
  if (rpo < 4) return 0
  if (rpo >= 13) return 10
  return Math.floor(rpo - 3)
}

export function economyLabel(idx: number): string {
  if (idx === 0) return '<4'
  if (idx === 10) return '13+'
  const lo = idx + 3
  return `${lo}-${lo + 1}`
}

/**
 * Always-render-through floor at index 9 (covers [3, 13)) so every
 * bowler's chart spans the same x-axis — comparable across players.
 */
export function buildEconomyHistogramRows(
  perInnings: number[],
): EconomyBinRow[] {
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
// wickets tiers but with reversed polarity (sage at the LOW end =
// good economy; ochre/gold at the HIGH end = bad economy).

export type LowerIsBetterTier = 'tight' | 'mid' | 'loose'

/** Economy tier — < 7 tight, 7-9 mid, ≥ 9 loose. */
export function economyTier(rpo: number): LowerIsBetterTier {
  if (rpo < 7) return 'tight'
  if (rpo < 9) return 'mid'
  return 'loose'
}

/** Runs-conceded tier — ≤ 25 tight, 25-40 mid, > 40 loose. */
export function runsConcededTier(runs: number): LowerIsBetterTier {
  if (runs <= 25) return 'tight'
  if (runs <= 40) return 'mid'
  return 'loose'
}

// ─── Runs conceded — continuous, width-5 bins ───────────────────────

export interface RunsConcededBinRow {
  bin: number
  label: string  // "0-4", "5-9", ..., "55-59", "60+"
  count: number
  tier: LowerIsBetterTier
}

/** Tier for a runs-conceded bin index (3-tier: tight / mid / loose).
 *  Bin width 5 starting at 0; thresholds at 25 and 40 runs. */
function runsConcededBinTier(idx: number): LowerIsBetterTier {
  if (idx <= 4) return 'tight'   // 0-24 runs
  if (idx <= 7) return 'mid'     // 25-39 runs
  return 'loose'                  // 40+ runs
}

/** Width-5 bin. runs ≥ 60 → 12 (60+ catch). */
export function runsConcededBin(runs: number): number {
  if (runs >= 60) return 12
  if (runs < 0) return 0
  return Math.floor(runs / 5)
}

export function runsConcededLabel(idx: number): string {
  if (idx === 12) return '60+'
  const lo = idx * 5
  return `${lo}-${lo + 4}`
}

/**
 * Always render through index 11 (covers [0, 60)) — 12 bins. Tail
 * extends only when an observation reaches 60+.
 */
export function buildRunsConcededHistogramRows(
  observations: { runs_conceded: number }[],
): RunsConcededBinRow[] {
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
