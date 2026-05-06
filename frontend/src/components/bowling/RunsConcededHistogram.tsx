/**
 * Continuous-bin runs-conceded (absolute) histogram. Spec
 * §12.2.4 (revised 2026-05-06 — added 3-tier coloring: tight (≤25)
 * / mid (25-40) / loose (>40)).
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN_LOWER_TIERS } from '../charts/palette'
import { buildRunsConcededHistogramRows } from './distributionBins'
import type { BowlerInningsObservation } from '../../types'

interface Props {
  observations: BowlerInningsObservation[]
  title?: string
  height?: number
}

const TIER_ORDER: (keyof typeof WISDEN_LOWER_TIERS)[] = ['tight', 'mid', 'loose']
const COLOR_SCHEME = TIER_ORDER.map(t => WISDEN_LOWER_TIERS[t])

export default function RunsConcededHistogram({ observations, title, height = 220 }: Props) {
  const rows = useMemo(
    () => buildRunsConcededHistogramRows(observations),
    [observations],
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
      categoryLabel="Runs conceded"
      valueLabel="Innings"
      height={height}
    />
  )
}
