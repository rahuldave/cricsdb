/**
 * Batting "By Position" tab — Mix histogram + single-panel
 * Performance vs cohort (Strike Rate).
 *
 * Spec: internal_docs/spec-mix-and-performance-charts.md §1 + §2.1.
 * Mounts on /batting?player=X. Reads per-bucket player + cohort
 * values directly from /batters/{id}/summary.position_distribution
 * (single payload — no extra fetch per spec §3.1).
 *
 * Layout (top → bottom):
 *   1. Mix histogram   — % player innings batted per position bucket.
 *   2. Performance     — Strike Rate bars + cohort ticks.
 *   3. Performance     — Batting Average bars + cohort ticks.
 *
 * Bucket axis: 10 (1=Opener merged from positions 1+2, 2..10 = #3..#11)
 * per `api/innings_positions.py::derive_positions`. Phase tint banded
 * (sage 1-3 top-order, none 4-6 middle, indigo 7-10 lower).
 */

import MixHistogram, { type MixEntry } from '../distribution-charts/MixHistogram'
import PerformanceVsCohort, { type PerfEntry } from '../distribution-charts/PerformanceVsCohort'
import { WISDEN_TIER_TINTS } from '../charts/palette'
import type { BattingPositionDistributionEntry } from '../../types'

interface Props {
  positionDistribution: BattingPositionDistributionEntry[]
}

// Bucket 1 = Opener (positions 1+2 merged per derive_positions);
// bucket b (2..10) = position b+1.
function bucketLabel(bucket: number): string {
  if (bucket === 1) return 'Open'
  return `#${bucket + 1}`
}

// Batting phase tints — sage top-order (1-3), none middle (4-6),
// indigo lower (7-10). Per spec §1 + colors.md.
function battingPhaseTint(bucket: number): string | null {
  if (bucket >= 1 && bucket <= 3)  return WISDEN_TIER_TINTS.sage.bg
  if (bucket >= 7 && bucket <= 10) return WISDEN_TIER_TINTS.indigo.bg
  return null
}

function fmt2(v: number) { return v.toFixed(2) }

export default function PositionDistributionTab({ positionDistribution }: Props) {
  if (!positionDistribution || positionDistribution.length === 0) return null

  const totalInnings = positionDistribution.reduce((s, e) => s + (e.innings || 0), 0)

  // Chart A — mix.
  const mixEntries: MixEntry[] = positionDistribution.map(e => {
    const share = totalInnings > 0 ? e.innings / totalInnings : 0
    return {
      bucket: e.bucket,
      share,
      raw: e.innings,
      tooltip: `${bucketLabel(e.bucket)}: ${e.innings} innings (${(share * 100).toFixed(1)}%)`,
    }
  })

  // Chart B — strike rate panel (single-metric per spec §2.1).
  const srEntries: PerfEntry[] = positionDistribution.map(e => {
    const sr = e.legal_balls > 0
      ? Math.round((e.runs * 100 / e.legal_balls) * 100) / 100
      : null
    return {
      bucket: e.bucket,
      playerValue: sr,
      cohortValue: e.cohort_strike_rate,
      faded: e.innings === 0,
      tooltip: sr != null && e.cohort_strike_rate != null
        ? `${bucketLabel(e.bucket)}: SR ${sr.toFixed(2)} · cohort ${e.cohort_strike_rate.toFixed(2)}`
        : `${bucketLabel(e.bucket)}: no innings`,
    }
  })

  // Chart C — batting average panel. avg = runs/dismissals at the
  // bucket; null on buckets the player has never been dismissed at
  // (e.g. opener slot for a tail-ender who's been not-out every time).
  const avgEntries: PerfEntry[] = positionDistribution.map(e => {
    const avg = e.dismissals > 0
      ? Math.round((e.runs / e.dismissals) * 100) / 100
      : null
    return {
      bucket: e.bucket,
      playerValue: avg,
      cohortValue: e.cohort_average,
      faded: e.innings === 0,
      tooltip: avg != null && e.cohort_average != null
        ? `${bucketLabel(e.bucket)}: Avg ${avg.toFixed(2)} · cohort ${e.cohort_average.toFixed(2)}`
        : `${bucketLabel(e.bucket)}: no innings`,
    }
  })

  return (
    <section
      className="wisden-position-distribution-tab"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}
    >
      <MixHistogram
        entries={mixEntries}
        bucketLabel={bucketLabel}
        phaseTint={battingPhaseTint}
        title="Position mix"
        subtitle="% of player's innings batted at each position (top-order · middle · lower)"
        height={70}
      />
      <PerformanceVsCohort
        entries={srEntries}
        bucketLabel={bucketLabel}
        phaseTint={battingPhaseTint}
        title="Strike rate by position"
        yLabel="runs / 100 balls"
        yFmt={fmt2}
        cohortExplainer="Green tick = average strike rate at this batting position across every batter in the FilterBar scope."
        height={110}
      />
      <PerformanceVsCohort
        entries={avgEntries}
        bucketLabel={bucketLabel}
        phaseTint={battingPhaseTint}
        title="Batting average by position"
        yLabel="runs / dismissal"
        yFmt={fmt2}
        cohortExplainer="Green tick = average batting average (runs / dismissals) at this batting position across every batter in the FilterBar scope."
        height={110}
      />
    </section>
  )
}
