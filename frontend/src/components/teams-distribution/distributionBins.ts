/**
 * Team-batting distribution bin / tier helpers. Spec:
 * internal_docs/spec-distribution-stats.md §17.3.
 *
 * Two histograms — Runs (width-10 bins, like batter v1 but with
 * team-grain thresholds at 100 and 200 runs) and Run Rate (width-1
 * RPO bins, identical bin scheme to bowler economy but with FLIPPED
 * polarity — high RR is good for the batter).
 *
 * Sparkline-bar tier helpers (`teamRunsTier`, `teamRRTier`) take
 * raw values; the histogram-row builders bin first then tier the
 * bin index. Both arrive at the same 3-tier coloring at the
 * 100/200-run and 7/9-RPO boundaries.
 */

// ─── Runs — width-10 bins, threshold at 100 / 200 ──────────────────

export type TeamRunsBinTier = 'low' | 'mid' | 'high'

export interface TeamRunsBinRow {
  /** Bin index (0..25). 25 = the [250+] catch-all. */
  bin: number
  label: string
  count: number
  tier: TeamRunsBinTier
}

export function teamRunsBin(runs: number): number {
  if (runs >= 250) return 25
  if (runs < 0) return 0
  return Math.floor(runs / 10)
}

export function teamRunsLabel(idx: number): string {
  if (idx === 25) return '250+'
  return `${idx * 10}-${idx * 10 + 9}`
}

/** Tier from bin index — low (<100) / mid (100-199) / high (≥200). */
export function teamRunsBinTier(idx: number): TeamRunsBinTier {
  if (idx < 10) return 'low'
  if (idx < 20) return 'mid'
  return 'high'
}

/** Tier from raw runs value — used for sparkline bar coloring so
 *  the sparkline tier matches the histogram tier at the same value. */
export function teamRunsTier(runs: number): TeamRunsBinTier {
  if (runs < 100) return 'low'
  if (runs < 200) return 'mid'
  return 'high'
}

/**
 * Always render bins 0..19 ([0,199]) so every team's chart spans
 * the same x-axis floor — comparable across teams. Tail extends
 * only when an observation reaches 200+.
 */
export function buildTeamRunsHistogramRows(
  observations: { runs: number }[],
): TeamRunsBinRow[] {
  const counts = new Array(26).fill(0)
  let maxRuns = -1
  for (const o of observations) {
    const i = teamRunsBin(o.runs)
    counts[i] += 1
    if (o.runs > maxRuns) maxRuns = o.runs
  }
  const lastIdx = Math.max(19, maxRuns >= 0 ? teamRunsBin(maxRuns) : 19)
  const rows: TeamRunsBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: teamRunsLabel(i),
      count: counts[i],
      tier: teamRunsBinTier(i),
    })
  }
  return rows
}

// ─── Run Rate — width-1 RPO bins, FLIPPED polarity ─────────────────

export type TeamRRBinTier = 'low' | 'mid' | 'high'

export interface TeamRRBinRow {
  bin: number
  label: string
  count: number
  tier: TeamRRBinTier
}

/** Bin index. Identical to bowler economyBin: <4 → 0, ≥13 → 10. */
export function teamRRBin(rr: number): number {
  if (rr < 4) return 0
  if (rr >= 13) return 10
  return Math.floor(rr - 3)
}

export function teamRRLabel(idx: number): string {
  if (idx === 0) return '<4'
  if (idx === 10) return '13+'
  const lo = idx + 3
  return `${lo}-${lo + 1}`
}

/** Tier from bin index — low (≤7 RPO, slow) / mid (7-9) / high (≥9,
 *  explosive). FLIPPED polarity from bowler economy: high RR is good
 *  for the batter. */
export function teamRRBinTier(idx: number): TeamRRBinTier {
  if (idx <= 3) return 'low'   // bins covering RPO < 7
  if (idx <= 5) return 'mid'   // 7-9 RPO
  return 'high'                 // ≥ 9 RPO (good for batter)
}

/** Tier from raw RR — used for sparkline bar coloring. */
export function teamRRTier(rr: number): TeamRRBinTier {
  if (rr < 7) return 'low'
  if (rr < 9) return 'mid'
  return 'high'
}

export function buildTeamRunRateHistogramRows(
  perInnings: number[],
): TeamRRBinRow[] {
  const counts = new Array(11).fill(0)
  let maxRR = 0
  for (const e of perInnings) {
    const i = teamRRBin(e)
    counts[i] += 1
    if (e > maxRR) maxRR = e
  }
  const lastIdx = Math.max(9, teamRRBin(maxRR))
  const rows: TeamRRBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: teamRRLabel(i),
      count: counts[i],
      tier: teamRRBinTier(i),
    })
  }
  return rows
}

// ─── Team-bowling Wickets — discrete bars 0..10 ─────────────────────
//
// Always renders the full 11-bar [0..10] range so every team's chart
// is comparable, even when the active scope tops out at 6 wickets.

export type TeamWicketsBinTier = 'low' | 'mid' | 'high'

export interface TeamWicketsBinRow {
  bin: number  // 0..10
  label: string
  count: number
  tier: TeamWicketsBinTier
}

/** Tier from raw wicket count — ≤3 = poor (INDIGO), 4-6 = typical
 *  (SAGE), ≥7 = strong (OCHRE) per spec §17.2. */
export function teamWicketsTier(w: number): TeamWicketsBinTier {
  if (w <= 3) return 'low'
  if (w <= 6) return 'mid'
  return 'high'
}

export function buildTeamWicketsHistogramRows(
  observations: { wickets: number }[],
): TeamWicketsBinRow[] {
  const counts = new Array(11).fill(0)
  for (const o of observations) {
    const i = Math.max(0, Math.min(10, o.wickets))
    counts[i] += 1
  }
  const rows: TeamWicketsBinRow[] = []
  for (let i = 0; i <= 10; i += 1) {
    rows.push({
      bin: i,
      label: String(i),
      count: counts[i],
      tier: teamWicketsTier(i),
    })
  }
  return rows
}

// ─── Team-bowling Runs Conceded — width-10, FLIPPED polarity ───────
//
// Bin scheme is identical to team-batting Runs (width-10 bars 0..250+);
// tier polarity is INVERTED — low conceded = ochre (good for bowler),
// high conceded = indigo (poor for bowler). Spec §17.2 + §17.4.

export type TeamRunsConcededBinTier = 'low' | 'mid' | 'high'

export interface TeamRunsConcededBinRow {
  bin: number
  label: string
  count: number
  tier: TeamRunsConcededBinTier
}

/** Tier from raw runs-conceded value. Naming convention preserved
 *  (low/mid/high describe the BIN, not the outcome) — the panel's
 *  TIER_TO_COLOR map flips: <100 → ochre, 100-199 → sage, ≥200 → indigo. */
export function teamRunsConcededTier(runs: number): TeamRunsConcededBinTier {
  if (runs < 100) return 'low'
  if (runs < 200) return 'mid'
  return 'high'
}

export function buildTeamRunsConcededHistogramRows(
  observations: { runs_conceded: number }[],
): TeamRunsConcededBinRow[] {
  // Reuse team-batting binner — same width-10 bins, same labels.
  const counts = new Array(26).fill(0)
  let maxRuns = -1
  for (const o of observations) {
    const i = teamRunsBin(o.runs_conceded)
    counts[i] += 1
    if (o.runs_conceded > maxRuns) maxRuns = o.runs_conceded
  }
  const lastIdx = Math.max(19, maxRuns >= 0 ? teamRunsBin(maxRuns) : 19)
  const rows: TeamRunsConcededBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: teamRunsLabel(i),
      count: counts[i],
      tier: teamRunsConcededTier(i * 10),
    })
  }
  return rows
}

// ─── Team-bowling Economy — width-1 RPO, normal bowler polarity ────
//
// Same bin scheme as team-batting RR, but tier polarity matches
// bowler-economy convention: ≤7 RPO = OCHRE (tight), 7-9 = SAGE
// (typical), ≥9 = INDIGO (loose). Spec §17.4.

export type TeamConcedeRPOBinTier = 'low' | 'mid' | 'high'

export interface TeamConcedeRPOBinRow {
  bin: number
  label: string
  count: number
  tier: TeamConcedeRPOBinTier
}

/** Tier names preserve direction (low=lowest bin index = lowest RPO).
 *  Color flip lives in the panel's TIER_TO_COLOR for this tab. */
export function teamConcedeRPOTier(rpo: number): TeamConcedeRPOBinTier {
  if (rpo < 7) return 'low'
  if (rpo < 9) return 'mid'
  return 'high'
}

export function buildTeamConcedeRPOHistogramRows(
  perInnings: number[],
): TeamConcedeRPOBinRow[] {
  const counts = new Array(11).fill(0)
  let maxRR = 0
  for (const e of perInnings) {
    const i = teamRRBin(e)
    counts[i] += 1
    if (e > maxRR) maxRR = e
  }
  const lastIdx = Math.max(9, teamRRBin(maxRR))
  const rows: TeamConcedeRPOBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    // Bin index maps back to a representative RPO at lo of the bucket
    // (idx 0 = <4, idx 1 = 4-5 → tier from rpo=4, etc.).
    const repRpo = i === 0 ? 3 : i + 3
    rows.push({
      bin: i,
      label: teamRRLabel(i),
      count: counts[i],
      tier: teamConcedeRPOTier(repRpo),
    })
  }
  return rows
}
