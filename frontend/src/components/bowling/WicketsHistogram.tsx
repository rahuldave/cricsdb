/**
 * Histogram of a bowler's wickets per innings.
 *
 * Discrete-bar histogram of wickets per innings for the bowler
 * Distribution panel. Spec: internal_docs/spec-distribution-stats.md
 * §12.2.2.
 *
 * Bin scheme: integer wicket counts 0..5, plus a "6+" catch-all.
 * Always renders through bin 5 (the floor) so non-strike bowlers'
 * empty upper tail reads "not a wicket-taker" at a glance.
 *
 * Color tiering (WISDEN_WICKET_TIERS) ladders the rarity spectrum:
 * wicketless (0) / building (1-2) / strike (3+).
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN_WICKET_TIERS } from '../charts/palette'
import { buildWicketHistogramRows } from './distributionBins'
import type { BowlerWicketsBlock } from '../../types'

/** Props of `WicketsHistogram`. */
interface Props {
  block: BowlerWicketsBlock // the wickets block; its `observations` are binned
  title?: string // the chart title; none when absent
  height?: number // the chart height in pixels; 220 by default
}

const TIER_ORDER: (keyof typeof WISDEN_WICKET_TIERS)[] = [
  'wicketless', 'building', 'strike',
]
const COLOR_SCHEME = TIER_ORDER.map(t => WISDEN_WICKET_TIERS[t])

/** Show the wickets histogram: one bar for each count from 0 to 5, and a 6+ bar when an innings reached 6 or more. */
export default function WicketsHistogram({ block, title, height = 220 }: Props) {
  const rows = useMemo(
    () => buildWicketHistogramRows(block.observations),
    [block.observations],
  )
  if (rows.length === 0) return null
  return (
    <BarChart
      data={rows}
      categoryAccessor="label"
      valueAccessor="count"
      colorBy="tier"
      colorScheme={COLOR_SCHEME}
      title={title}
      categoryLabel="Wickets in innings"
      valueLabel="Innings"
      height={height}
    />
  )
}
