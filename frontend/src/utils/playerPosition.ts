/**
 * Helpers that derive a player's "typical batting position" from the
 * 10-bucket `position_distribution` already on /batters/{id}/summary.
 *
 * Bucket convention (api/innings_positions.py::derive_positions):
 *   bucket 1 = Opener (positions 1 + 2 merged)
 *   bucket 2 = #3
 *   bucket 3 = #4
 *   …
 *   bucket 10 = #11
 *
 * Used by:
 *   - PositionDistributionTab — vertical marker on the Position-mix
 *     chart (the player's typical bucket).
 *   - Batting.tsx inter-wicket tab — vertical marker on the
 *     Strike-Rate-by-Wickets-Down chart, in wickets-down units (a
 *     batter walks in at wickets_down = position - 1).
 */

import type { BattingPositionDistributionEntry } from '../types'

/** Mean BUCKET (1..10) of the player's batting position, weighted by
 *  innings in each bucket. Returns null when there are no innings. */
export function meanPositionBucket(
  positionDistribution: BattingPositionDistributionEntry[] | undefined | null,
): number | null {
  if (!positionDistribution || positionDistribution.length === 0) return null
  let totalInnings = 0
  let weightedSum = 0
  for (const e of positionDistribution) {
    const inn = e.innings ?? 0
    if (inn <= 0) continue
    totalInnings += inn
    weightedSum += inn * e.bucket
  }
  return totalInnings > 0 ? weightedSum / totalInnings : null
}

/** Mean wickets-down at which the player walks in, derived from the
 *  same bucket weights. Bucket 1 (Opener) maps to wd = 0.5 (positions
 *  1 + 2 merged, walking in at wd = 0 or wd = 1). Buckets 2..10
 *  (positions #3..#11) map to wd = bucket (so a #3 batter walks in at
 *  wd = 2). Returns null when there are no innings. */
export function meanWicketsDown(
  positionDistribution: BattingPositionDistributionEntry[] | undefined | null,
): number | null {
  if (!positionDistribution || positionDistribution.length === 0) return null
  let totalInnings = 0
  let weightedSum = 0
  for (const e of positionDistribution) {
    const inn = e.innings ?? 0
    if (inn <= 0) continue
    totalInnings += inn
    const wd = e.bucket === 1 ? 0.5 : e.bucket
    weightedSum += inn * wd
  }
  return totalInnings > 0 ? weightedSum / totalInnings : null
}
