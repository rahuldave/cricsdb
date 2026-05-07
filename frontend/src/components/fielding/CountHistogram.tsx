/**
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

interface Props {
  observations: FielderObservation[]
  metricKey: 'catches' | 'run_outs' | 'stumpings'
  metricLabel: string  // "Catches" / "Run-outs" / "Stumpings"
  height?: number
}

const TIER_ORDER: ('zero' | 'one' | 'multi')[] = ['zero', 'one', 'multi']
const COLOR_SCHEME = [
  '#7090A8',     // indigo — zero bar (poor outcome for the player)
  '#7A8E6A',     // sage — one (typical)
  WISDEN.ochre,  // ochre — multi (hot / impactful)
]
void TIER_ORDER  // documented for callers; unused at runtime

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
