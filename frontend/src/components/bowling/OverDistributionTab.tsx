/**
 * Bowling "By Over" tab — Mix histogram + stacked Performance vs cohort.
 *
 * Spec: internal_docs/spec-mix-and-performance-charts.md §1 + §2.2.
 * Mounts on /bowling?player=X. Reads per-bucket player + cohort values
 * directly from /bowlers/{id}/summary.over_distribution (single
 * payload — no extra fetch per spec §3.2).
 *
 * Layout (top → bottom):
 *   1. Mix histogram   — % player balls bowled per over.
 *   2. Performance — Economy bars + cohort ticks.
 *   3. Performance — Wickets / innings bars + cohort ticks.
 *
 * All three share the 20-over X axis; phase tint banded (sage 1-6 PP,
 * none 7-15 middle, ochre 16-20 death). Buckets where the player has
 * zero balls fade to 0.4 opacity but still render the cohort tick.
 */

import MixHistogram, { type MixEntry } from '../distribution-charts/MixHistogram'
import PerformanceVsCohort, { type PerfEntry } from '../distribution-charts/PerformanceVsCohort'
import { WISDEN_TIER_TINTS } from '../charts/palette'
import type { BowlingOverDistributionEntry } from '../../types'

interface Props {
  overDistribution: BowlingOverDistributionEntry[]
}

const bucketLabel = (over: number) => String(over)

// Bowling phase tints — match spec §1 (Chart A) palette + colors.md.
function bowlingPhaseTint(over: number): string | null {
  if (over >= 1 && over <= 6)   return WISDEN_TIER_TINTS.sage.bg    // powerplay
  if (over >= 16 && over <= 20) return WISDEN_TIER_TINTS.ochre.bg   // death
  return null                                                       // middle
}

function fmt2(v: number) { return v.toFixed(2) }
function fmt3(v: number) { return v.toFixed(3) }

export default function OverDistributionTab({ overDistribution }: Props) {
  if (!overDistribution || overDistribution.length === 0) return null

  const totalBalls = overDistribution.reduce((s, e) => s + (e.legal_balls || 0), 0)

  // Chart A — mix.
  const mixEntries: MixEntry[] = overDistribution.map(e => {
    const share = totalBalls > 0 ? e.legal_balls / totalBalls : 0
    return {
      bucket: e.over,
      share,
      raw: e.legal_balls,
      tooltip: `Over ${e.over}: ${e.legal_balls} balls (${(share * 100).toFixed(1)}%)`,
    }
  })

  // Chart B — economy panel.
  const econEntries: PerfEntry[] = overDistribution.map(e => {
    const econ = e.legal_balls > 0
      ? Math.round((e.runs_conceded * 6 / e.legal_balls) * 100) / 100
      : null
    return {
      bucket: e.over,
      playerValue: econ,
      cohortValue: e.cohort_economy,
      faded: e.legal_balls === 0,
      tooltip: econ != null && e.cohort_economy != null
        ? `Over ${e.over}: Econ ${econ.toFixed(2)} · cohort ${e.cohort_economy.toFixed(2)}`
        : `Over ${e.over}: no balls`,
    }
  })

  // Chart B — wickets-per-innings panel.
  const wpiEntries: PerfEntry[] = overDistribution.map(e => {
    const wpi = e.innings_bowled > 0
      ? Math.round((e.wickets / e.innings_bowled) * 1000) / 1000
      : null
    return {
      bucket: e.over,
      playerValue: wpi,
      cohortValue: e.cohort_wickets_per_innings,
      faded: e.legal_balls === 0,
      tooltip: wpi != null && e.cohort_wickets_per_innings != null
        ? `Over ${e.over}: ${e.wickets} wkts in ${e.innings_bowled} inn` +
          ` = ${wpi.toFixed(3)}/inn · cohort ${e.cohort_wickets_per_innings.toFixed(3)}/inn`
        : `Over ${e.over}: no innings touched`,
    }
  })

  return (
    <section
      className="wisden-over-distribution-tab"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}
    >
      <MixHistogram
        entries={mixEntries}
        bucketLabel={bucketLabel}
        phaseTint={bowlingPhaseTint}
        title="Over mix"
        subtitle="% of player's legal balls bowled per over (powerplay · middle · death)"
        height={70}
      />
      <PerformanceVsCohort
        entries={econEntries}
        bucketLabel={bucketLabel}
        phaseTint={bowlingPhaseTint}
        title="Economy by over"
        subtitle="player econ vs cohort (forest-green tick)"
        yLabel="runs / over"
        yFmt={fmt2}
        height={90}
      />
      <PerformanceVsCohort
        entries={wpiEntries}
        bucketLabel={bucketLabel}
        phaseTint={bowlingPhaseTint}
        title="Wickets / innings by over"
        subtitle="player wkts ÷ innings-touching vs cohort"
        yLabel="wkts / inn"
        yFmt={fmt3}
        height={90}
      />
    </section>
  )
}
