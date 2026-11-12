/**
 * Histogram of a bowler's economy per innings, coloured tight, mid and loose.
 *
 * Continuous-bin economy (RPO) histogram. Spec
 * §12.2.3 (revised 2026-05-06 — added 3-tier coloring matching
 * the sparkline below: tight (<7) / mid (7-9) / loose (≥9)).
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN_LOWER_TIERS } from '../charts/palette'
import { buildEconomyHistogramRows } from './distributionBins'
import type { BowlerEconomyBlock } from '../../types'

/** Props of `EconomyHistogram`. */
interface Props {
  block: BowlerEconomyBlock // the economy block; its `per_innings` values are binned
  title?: string // the chart title; none when absent
  height?: number // the chart height in pixels; 220 by default
}

const TIER_ORDER: (keyof typeof WISDEN_LOWER_TIERS)[] = ['tight', 'mid', 'loose']
const COLOR_SCHEME = TIER_ORDER.map(t => WISDEN_LOWER_TIERS[t])

/** Show the economy histogram in width-1 RPO bins; nothing when there are no rows. */
export default function EconomyHistogram({ block, title, height = 220 }: Props) {
  const rows = useMemo(
    () => buildEconomyHistogramRows(block.per_innings),
    [block.per_innings],
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
      categoryLabel="RPO in innings"
      valueLabel="Innings"
      height={height}
    />
  )
}
