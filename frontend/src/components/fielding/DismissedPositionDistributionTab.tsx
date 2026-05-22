/**
 * Fielding "By Dismissed Position" tab — Mix histogram +
 * single-panel Performance vs cohort (Catches per match).
 *
 * Spec: internal_docs/spec-mix-and-performance-charts.md §1 + §2.3.
 * Mounts on /fielding?player=X. Reads per-bucket player + cohort
 * values directly from /fielders/{id}/summary
 * .dismissal_position_distribution (single payload — no extra
 * fetch per spec §3.3).
 *
 * Layout (top → bottom):
 *   1. Mix histogram — % of player's total dismissals credited at
 *      each dismissed-batter position.
 *   2. Performance — Catches per match bars + cohort ticks. Player
 *      rate = bucket_catches / player_matches (same dimension as
 *      the cohort tick).
 *
 * Bucket axis: 10 (1=Opener merged from positions 1+2, 2..10 = #3..#11)
 * — the bucket represents the BATTING POSITION OF THE DISMISSED
 * BATTER, not the fielder's batting position.
 *
 * Cohort partition is keeper-binary, automatic from the player's
 * `is_keeper` flag on the summary response. Keepers get a different
 * cohort baseline from outfielders — keeper cohort catches/match is
 * ~2× outfielder cohort at most buckets (DB-verified for IPL scope).
 */

import MixHistogram, { type MixEntry } from '../distribution-charts/MixHistogram'
import PerformanceVsCohort, { type PerfEntry } from '../distribution-charts/PerformanceVsCohort'
import { WISDEN_TIER_TINTS } from '../charts/palette'
import type { FieldingDismissalPositionEntry } from '../../types'

interface Props {
  dismissalPositionDistribution: FieldingDismissalPositionEntry[]
  /** is_keeper flag from /fielders/{id}/summary. Drives the cohort
   *  legend wording ("keeper cohort" vs "outfielder cohort"). */
  isKeeper: 0 | 1
  /** Player's match count at scope from summary.matches.value. The
   *  per-bucket catches/match rate divides each bucket's catches by
   *  this same denominator — same dimension as cohort tick. */
  playerMatches: number
}

function bucketLabel(bucket: number): string {
  if (bucket === 1) return 'Open'
  return `#${bucket + 1}`
}

// Same banding as batting (per spec §1) — top-order vs lower-order
// batting positions. The fielder's CREDIT distribution will
// typically tilt toward top-order for keepers (slip-cluster
// catches of openers/#3) and middle/lower for outfielders.
function dismissedPositionPhaseTint(bucket: number): string | null {
  if (bucket >= 1 && bucket <= 3)  return WISDEN_TIER_TINTS.sage.bg
  if (bucket >= 7 && bucket <= 10) return WISDEN_TIER_TINTS.indigo.bg
  return null
}

function fmt3(v: number) { return v.toFixed(3) }

export default function DismissedPositionDistributionTab({
  dismissalPositionDistribution, isKeeper, playerMatches,
}: Props) {
  if (!dismissalPositionDistribution || dismissalPositionDistribution.length === 0) {
    return null
  }

  const totalDismissals = dismissalPositionDistribution.reduce(
    (s, e) => s + (e.dismissals || 0), 0,
  )

  // Chart A — dismissal-position mix.
  const mixEntries: MixEntry[] = dismissalPositionDistribution.map(e => {
    const share = totalDismissals > 0 ? e.dismissals / totalDismissals : 0
    return {
      bucket: e.bucket,
      share,
      raw: e.dismissals,
      tooltip: `${bucketLabel(e.bucket)}: `
        + `${e.catches} catches + ${e.run_outs} run-outs`
        + (e.stumpings > 0 ? ` + ${e.stumpings} stumpings` : '')
        + ` = ${e.dismissals} dismissals (${(share * 100).toFixed(1)}%)`,
    }
  })

  // Chart B — catches/match by bucket. Player rate = catches /
  // total matches at scope (same denominator across all buckets,
  // matching the cohort dimension exactly). Sum across buckets =
  // overall catches/match (algebraic identity).
  const perfEntries: PerfEntry[] = dismissalPositionDistribution.map(e => {
    const playerCm = playerMatches > 0
      ? Math.round((e.catches / playerMatches) * 10000) / 10000
      : null
    return {
      bucket: e.bucket,
      playerValue: playerCm,
      cohortValue: e.cohort_catches_per_match,
      faded: e.dismissals === 0,
      tooltip: playerCm != null && e.cohort_catches_per_match != null
        ? `${bucketLabel(e.bucket)}: `
          + `player ${e.catches} catches in ${playerMatches} matches = ${playerCm.toFixed(3)}/match · `
          + `cohort ${e.cohort_catches_per_match.toFixed(3)}/match`
        : `${bucketLabel(e.bucket)}: no dismissals`,
    }
  })

  const cohortLabel = isKeeper ? 'keepers' : 'outfielders'
  const cohortExplainer = `Green tick = average catches per match against batters at this position across every ${cohortLabel.slice(0, -1)} in the FilterBar scope.`

  return (
    <section
      className="wisden-dismissed-position-distribution-tab"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}
    >
      <MixHistogram
        entries={mixEntries}
        bucketLabel={bucketLabel}
        phaseTint={dismissedPositionPhaseTint}
        title="Dismissed-batter position mix"
        subtitle="% of player's dismissals credited at each batting position (top · middle · lower)"
        height={70}
      />
      <PerformanceVsCohort
        entries={perfEntries}
        bucketLabel={bucketLabel}
        phaseTint={dismissedPositionPhaseTint}
        title="Catches per match by dismissed-batter position"
        yLabel="catches / match"
        yFmt={fmt3}
        cohortExplainer={cohortExplainer}
        height={110}
      />
    </section>
  )
}
