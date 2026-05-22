/**
 * Nice-numbers y-axis helper for the distribution-charts components.
 *
 * Replaces the previous (max / mid / 0) tick scheme that produced
 * awkward labels like "143.96 / 71.98 / 0.00" — user flagged
 * 2026-05-22: "who makes tick marks at weird sizes and 2 decimal
 * places?". Picks step from {1, 2, 5} × 10^k so labels always read
 * as round human numbers (50 / 100 / 150, 5 / 10 / 15, 0.2 / 0.4 /
 * 0.6, etc.) regardless of which player/scope is loaded.
 *
 * Reference: Heckbert's "Nice Numbers for Graph Labels" (Graphics
 * Gems, 1990) — the canonical algorithm every charting library
 * cites. Adapted for the per-chart `rawMax → ticks + niceMax`
 * contract this codebase needs.
 */

function niceNum(value: number, round: boolean): number {
  if (value <= 0) return 1
  const exp = Math.floor(Math.log10(value))
  const f = value / Math.pow(10, exp)
  let nf: number
  if (round) {
    if (f < 1.5) nf = 1
    else if (f < 3) nf = 2
    else if (f < 7) nf = 5
    else nf = 10
  } else {
    if (f <= 1) nf = 1
    else if (f <= 2) nf = 2
    else if (f <= 5) nf = 5
    else nf = 10
  }
  return nf * Math.pow(10, exp)
}

/**
 * Compute a nice tick array + niceMax for a y-axis given the raw
 * max data value. Always returns 3-4 ticks including 0; the niceMax
 * is the smallest "nice" value ≥ rawMax (so bars never overflow).
 *
 * `niceMax` replaces the rawMax in the chart's y-scaling: bar
 * heights become `value / niceMax × chartHeight` (instead of `value
 * / rawMax × chartHeight`), which gives the chart a small amount
 * of headroom above the tallest bar.
 */
export interface NiceAxis {
  /** Tick values in DESC order (max first, 0 last) — matches the
   *  top-to-bottom visual render. */
  ticks: number[]
  /** Use for y-scaling instead of rawMax. */
  niceMax: number
  /** Distance between consecutive ticks. */
  step: number
}

/** Bump a step (X × 10^k where X ∈ {1, 2, 5}) to the next nice step:
 *  1 → 2, 2 → 5, 5 → 10 (= 1 × 10^(k+1)). Used when the initial step
 *  would produce > 4 intervals (5+ ticks). */
function nextNiceUp(step: number): number {
  const exp = Math.floor(Math.log10(step))
  const f = Math.round(step / Math.pow(10, exp))
  if (f === 1) return 2 * Math.pow(10, exp)
  if (f === 2) return 5 * Math.pow(10, exp)
  return 10 * Math.pow(10, exp)
}

export function niceYAxis(rawMax: number): NiceAxis {
  if (rawMax <= 0) return { ticks: [0], niceMax: 1, step: 1 }
  // Three intervals → up to 4 ticks. Per user feedback we want
  // "lesser ticks ok" — 3-4 reads as clean without crowding. The
  // raw Heckbert step (rawMax/3) sometimes lands just under f=1.5
  // and yields 5+ intervals when ceil(rawMax/step) exceeds 4 (e.g.
  // rawMax=0.4427 → step=0.1 → 5 intervals). Bump to the next nice
  // step until intervals ≤ 4.
  let step = niceNum(rawMax / 3, true)
  let intervals = Math.ceil(rawMax / step)
  while (intervals > 4) {
    step = nextNiceUp(step)
    intervals = Math.ceil(rawMax / step)
  }
  const niceMax = intervals * step
  const ticks: number[] = []
  for (let v = 0; v <= niceMax + step * 0.0001; v += step) {
    // De-jitter floating-point drift on a running sum.
    ticks.push(Math.round(v / step) * step)
  }
  return { ticks: ticks.reverse(), niceMax, step }
}
