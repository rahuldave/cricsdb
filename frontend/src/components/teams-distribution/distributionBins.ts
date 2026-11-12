/**
 * Bins and colour tiers for the team batting, bowling and fielding histograms and sparklines.
 *
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
 *
 * The bowling and fielding sections below add the same helpers for
 * wickets, runs conceded, economy, catches, run-outs and stumpings.
 * @packageDocumentation
 */

// ─── Runs — width-10 bins, threshold at 100 / 200 ──────────────────

/** Tier of a team-runs bin: low (under 100), mid (100-199) or high (200 and over). */
export type TeamRunsBinTier = 'low' | 'mid' | 'high'

/** One bar of the team Runs histogram. */
export interface TeamRunsBinRow {
  /** Bin index (0..25). 25 = the [250+] catch-all. */
  bin: number
  label: string // the bar's label, as "120-129" or "250+"
  count: number // the number of innings in the bin
  tier: TeamRunsBinTier // the colour tier of the bin
}

/**
 * Return the width-10 bin of an innings total.
 * @param runs the innings total
 * @returns the bin index, 0 to 25; negative runs give 0 and 250 or more give 25
 */
export function teamRunsBin(runs: number): number {
  if (runs >= 250) return 25
  if (runs < 0) return 0
  return Math.floor(runs / 10)
}

/**
 * Return the label of a team-runs bin.
 * @param idx the bin index, 0 to 25
 * @returns the label, as "120-129", or "250+" for bin 25
 */
export function teamRunsLabel(idx: number): string {
  if (idx === 25) return '250+'
  return `${idx * 10}-${idx * 10 + 9}`
}

/**
 * Tier from bin index — low (<100) / mid (100-199) / high (≥200).
 * @param idx the bin index, 0 to 25
 * @returns the tier of the bin
 */
export function teamRunsBinTier(idx: number): TeamRunsBinTier {
  if (idx < 10) return 'low'
  if (idx < 20) return 'mid'
  return 'high'
}

/** Tier from raw runs value — used for sparkline bar coloring so
 *  the sparkline tier matches the histogram tier at the same value.
 * @param runs the innings total
 * @returns low under 100, mid under 200, high otherwise
 */
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
  observations: { runs: number }[], // one entry per innings, with the team's total
): TeamRunsBinRow[] { // one row per bin from 0 to at least 19 (0-199), in bin order
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

/** Tier of a run-rate bin: low (under 7 RPO), mid (7-9) or high (9 and over, good for the batting team). */
export type TeamRRBinTier = 'low' | 'mid' | 'high'

/** One bar of the team Run Rate histogram. */
export interface TeamRRBinRow {
  bin: number // the bin index, 0 to 10
  label: string // the bar's label, as "<4", "7-8" or "13+"
  count: number // the number of innings in the bin
  tier: TeamRRBinTier // the colour tier of the bin
}

/**
 * Bin index. Identical to bowler economyBin: <4 → 0, ≥13 → 10.
 * @param rr the innings run rate, in runs per over
 * @returns the bin index, 0 to 10
 */
export function teamRRBin(rr: number): number {
  if (rr < 4) return 0
  if (rr >= 13) return 10
  return Math.floor(rr - 3)
}

/**
 * Return the label of a run-rate bin.
 * @param idx the bin index, 0 to 10
 * @returns the label, as "<4" for bin 0, "13+" for bin 10, or "7-8"
 */
export function teamRRLabel(idx: number): string {
  if (idx === 0) return '<4'
  if (idx === 10) return '13+'
  const lo = idx + 3
  return `${lo}-${lo + 1}`
}

/** Tier from bin index — low (≤7 RPO, slow) / mid (7-9) / high (≥9,
 *  explosive). FLIPPED polarity from bowler economy: high RR is good
 *  for the batter.
 * @param idx the bin index, 0 to 10
 * @returns the tier of the bin
 */
export function teamRRBinTier(idx: number): TeamRRBinTier {
  if (idx <= 3) return 'low'   // bins covering RPO < 7
  if (idx <= 5) return 'mid'   // 7-9 RPO
  return 'high'                 // ≥ 9 RPO (good for batter)
}

/**
 * Tier from raw RR — used for sparkline bar coloring.
 * @param rr the innings run rate, in runs per over
 * @returns low under 7, mid under 9, high otherwise
 */
export function teamRRTier(rr: number): TeamRRBinTier {
  if (rr < 7) return 'low'
  if (rr < 9) return 'mid'
  return 'high'
}

/** Count innings into run-rate bins; always render bins 0..9 so charts compare across teams, and add bin 10 only when needed. */
export function buildTeamRunRateHistogramRows(
  perInnings: number[], // the run rate of each innings, in runs per over
): TeamRRBinRow[] { // one row per bin from 0 to at least 9, in bin order
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

/** Tier of a wickets bar: low (3 or fewer), mid (4-6) or high (7 or more). */
export type TeamWicketsBinTier = 'low' | 'mid' | 'high'

/** One bar of the team-bowling Wickets histogram. */
export interface TeamWicketsBinRow {
  bin: number  // 0..10
  label: string // the wicket count as text
  count: number // the number of innings with this many wickets
  tier: TeamWicketsBinTier // the colour tier of the bar
}

/** Tier from raw wicket count — ≤3 = poor (INDIGO), 4-6 = typical
 *  (SAGE), ≥7 = strong (OCHRE) per spec §17.2.
 * @param w the wickets taken in an innings
 * @returns the tier of the count
 */
export function teamWicketsTier(w: number): TeamWicketsBinTier {
  if (w <= 3) return 'low'
  if (w <= 6) return 'mid'
  return 'high'
}

/** Count innings by wickets taken, into 11 bars from 0 to 10; counts outside that range go to the nearest end. */
export function buildTeamWicketsHistogramRows(
  observations: { wickets: number }[], // one entry per innings bowled, with the wickets taken
): TeamWicketsBinRow[] { // 11 rows, for 0 to 10 wickets
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

/** Tier of a runs-conceded bin: low (under 100), mid (100-199) or high (200 and over); the panel colours low as good. */
export type TeamRunsConcededBinTier = 'low' | 'mid' | 'high'

/** One bar of the team-bowling Runs Conceded histogram. */
export interface TeamRunsConcededBinRow {
  bin: number // the bin index, 0 to 25, as in `teamRunsBin`
  label: string // the bar's label, as "120-129" or "250+"
  count: number // the number of innings in the bin
  tier: TeamRunsConcededBinTier // the tier of the bin
}

/** Tier from raw runs-conceded value. Naming convention preserved
 *  (low/mid/high describe the BIN, not the outcome) — the panel's
 *  TIER_TO_COLOR map flips: <100 → ochre, 100-199 → sage, ≥200 → indigo.
 * @param runs the runs conceded in an innings
 * @returns low under 100, mid under 200, high otherwise
 */
export function teamRunsConcededTier(runs: number): TeamRunsConcededBinTier {
  if (runs < 100) return 'low'
  if (runs < 200) return 'mid'
  return 'high'
}

/** Count innings into width-10 runs-conceded bins; always render bins 0..19 (0-199), and more only when needed. */
export function buildTeamRunsConcededHistogramRows(
  observations: { runs_conceded: number }[], // one entry per innings bowled, with the runs conceded
): TeamRunsConcededBinRow[] { // one row per bin from 0 to at least 19, in bin order
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

/** Tier of an economy bin: low (under 7 RPO), mid (7-9) or high (9 and over); the panel colours low as good. */
export type TeamConcedeRPOBinTier = 'low' | 'mid' | 'high'

/** One bar of the team-bowling Economy histogram. */
export interface TeamConcedeRPOBinRow {
  bin: number // the bin index, 0 to 10, as in `teamRRBin`
  label: string // the bar's label, as "<4", "7-8" or "13+"
  count: number // the number of innings in the bin
  tier: TeamConcedeRPOBinTier // the tier of the bin
}

/** Tier names preserve direction (low=lowest bin index = lowest RPO).
 *  Color flip lives in the panel's TIER_TO_COLOR for this tab.
 * @param rpo the runs conceded per over in an innings
 * @returns low under 7, mid under 9, high otherwise
 */
export function teamConcedeRPOTier(rpo: number): TeamConcedeRPOBinTier {
  if (rpo < 7) return 'low'
  if (rpo < 9) return 'mid'
  return 'high'
}

/** Count innings into economy bins; always render bins 0..9 so charts compare across teams, and add bin 10 only when needed. */
export function buildTeamConcedeRPOHistogramRows(
  perInnings: number[], // the runs conceded per over in each innings
): TeamConcedeRPOBinRow[] { // one row per bin from 0 to at least 9, in bin order
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

// ─── Team Fielding — Catches (0..7 floor), Run-outs / Stumpings (0/1/≥2) ──
//
// Per spec §17.5: team-grain catches use a wider 0..7 histogram (since
// teams catch 3-5 per innings typically); run-outs and stumpings keep
// the player-fielder 3-bar partition.

/** Tier of a team fielding bar (catches, run-outs or stumpings): low, mid or high, where high is good. */
export type TeamFieldingTier = 'low' | 'mid' | 'high'

/** One bar of the team Catches histogram. */
export interface TeamCatchesBinRow {
  bin: number // the catch count, 0 to 10
  label: string // the catch count as text
  count: number // the number of innings with this many catches
  tier: TeamFieldingTier // the colour tier of the bar
}

/** Catches tier per spec §17.2 — 0 INDIGO (none caught) /
 *  1-4 SAGE (typical) / ≥5 OCHRE (sharp fielding).
 * @param c the catches in an innings
 * @returns low for 0, mid for 1 to 4, high for 5 or more
 */
export function teamCatchesTier(c: number): TeamFieldingTier {
  if (c === 0) return 'low'
  if (c <= 4) return 'mid'
  return 'high'
}

/** Count innings by catches taken; always render bars 0..7, and extend to the largest count when an innings has 8 or more. */
export function buildTeamCatchesHistogramRows(
  observations: { catches: number }[], // one entry per innings fielded, with the catches taken
): TeamCatchesBinRow[] { // one row per catch count from 0 to at least 7
  const counts = new Array(11).fill(0)
  let maxC = 0
  for (const o of observations) {
    const i = Math.max(0, Math.min(10, o.catches))
    counts[i] += 1
    if (o.catches > maxC) maxC = o.catches
  }
  // Always render bins 0..7 so charts compare across teams; extend
  // tail when an observation reaches 8+.
  const lastIdx = Math.max(7, maxC)
  const rows: TeamCatchesBinRow[] = []
  for (let i = 0; i <= lastIdx; i += 1) {
    rows.push({
      bin: i,
      label: String(i),
      count: counts[i],
      tier: teamCatchesTier(i),
    })
  }
  return rows
}

// Run-outs + Stumpings — 3-bar partition (0 / 1 / ≥2). Same shape as
// player-fielder; tier mapping per spec §17.2:
//   Run-outs: 0 INDIGO / 1 SAGE / ≥2 OCHRE
//   Stumpings: 0 INDIGO / 1 SAGE / ≥2 OCHRE

/** One bar of a three-bar Run-outs or Stumpings histogram. */
export interface TeamCount3BinRow {
  bin: number       // 0, 1, 2 (the ≥2 bucket sits at bin index 2)
  label: string // "0", "1" or "≥2"
  count: number // the number of innings in the bar
  tier: TeamFieldingTier // the colour tier of the bar
}

/**
 * Return the tier of a three-bar count bin.
 * @param idx the bin index: 0, 1, or 2 for two or more
 * @returns low for 0, mid for 1, high otherwise
 */
export function teamCount3Tier(idx: number): TeamFieldingTier {
  if (idx === 0) return 'low'
  if (idx === 1) return 'mid'
  return 'high'
}

/** Count innings into three bars, 0, 1 and 2 or more, for run-outs or stumpings. */
export function buildTeamCount3HistogramRows(
  observations: { value: number }[], // one entry per innings fielded, with the run-outs or stumpings
): TeamCount3BinRow[] { // three rows, for 0, 1 and 2 or more
  const counts = [0, 0, 0]
  for (const o of observations) {
    const i = o.value === 0 ? 0 : o.value === 1 ? 1 : 2
    counts[i] += 1
  }
  return [
    { bin: 0, label: '0',  count: counts[0], tier: 'low'  },
    { bin: 1, label: '1',  count: counts[1], tier: 'mid'  },
    { bin: 2, label: '≥2', count: counts[2], tier: 'high' },
  ]
}
