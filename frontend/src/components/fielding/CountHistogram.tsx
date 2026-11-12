/**
 * A three-bar histogram of a fielder's catches, run-outs or stumpings per match.
 *
 * Discrete-bar histogram of catches / run-outs / stumpings per match
 * for the fielder Distribution panel. Spec:
 * internal_docs/spec-distribution-stats.md §14.2.3.
 *
 * Three fixed bars: 0 / 1 / ≥2. Linear y-axis. Tier colors INDIGO /
 * SAGE / OCHRE per the §10.3 3-tier palette.
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN } from '../charts/palette'
import { buildCountHistogramRows } from './distributionBins'
import type { FielderObservation } from '../../types'

/** Props of `CountHistogram`. */
interface Props {
  observations: FielderObservation[] // the fielder's matches, one row each
  metricKey: 'catches' | 'run_outs' | 'stumpings' // the count to bin
  metricLabel: string  // "Catches" / "Run-outs" / "Stumpings"
  height?: number // the chart height in pixels, 220 by default
}

const TIER_ORDER: ('zero' | 'one' | 'multi')[] = ['zero', 'one', 'multi']
const COLOR_SCHEME = [
  '#7090A8',     // indigo — zero bar (poor outcome for the player)
  '#7A8E6A',     // sage — one (typical)
  WISDEN.ochre,  // ochre — multi (hot / impactful)
]
void TIER_ORDER  // documented for callers; unused at runtime

/** Show how many matches had 0, 1, or 2 or more of the chosen fielding count. */
export default function CountHistogram({
  observations, metricKey, metricLabel, height = 220,
}: Props) {
  const rows = useMemo(
    () => buildCountHistogramRows(observations as unknown as { [k: string]: number }[], metricKey),
    [observations, metricKey],
  )
  if (rows.length === 0) return null
  return (
    <BarChart
      data={rows}
      categoryAccessor="label"
      valueAccessor="count"
      colorBy="tier"
      colorScheme={COLOR_SCHEME}
      categoryLabel={`${metricLabel} per match`}
      valueLabel="Matches"
      height={height}
    />
  )
}
