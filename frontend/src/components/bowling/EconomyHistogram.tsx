/**
 * Continuous-bin economy (RPO) histogram. Spec
 * §12.2.3 (revised 2026-05-06 — added 3-tier coloring matching
 * the sparkline below: tight (<7) / mid (7-9) / loose (≥9)).
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN_LOWER_TIERS } from '../charts/palette'
import { buildEconomyHistogramRows } from './distributionBins'
import type { BowlerEconomyBlock } from '../../types'

interface Props {
  block: BowlerEconomyBlock
  title?: string
  height?: number
}

const TIER_ORDER: (keyof typeof WISDEN_LOWER_TIERS)[] = ['tight', 'mid', 'loose']
const COLOR_SCHEME = TIER_ORDER.map(t => WISDEN_LOWER_TIERS[t])

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
