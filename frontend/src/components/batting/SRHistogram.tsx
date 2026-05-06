/**
 * Per-innings strike-rate histogram. Spec
 * internal_docs/spec-distribution-stats.md §9 (SR-tab extension
 * 2026-05-06).
 *
 * Bin width 25 SR across [0, 200+]. 3-tier coloring matching the
 * sparkline below: slow (<100) / mid (100-149) / explosive (≥150).
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN_SR_TIERS } from '../charts/palette'
import { buildSRHistogramRows } from './distributionBins'
import type { InningsObservation } from '../../types'

interface Props {
  observations: InningsObservation[]
  title?: string
  height?: number
}

const TIER_ORDER: (keyof typeof WISDEN_SR_TIERS)[] = ['slow', 'mid', 'explosive']
const COLOR_SCHEME = TIER_ORDER.map(t => WISDEN_SR_TIERS[t])

export default function SRHistogram({ observations, title, height = 220 }: Props) {
  const rows = useMemo(
    () => buildSRHistogramRows(observations),
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
      categoryLabel="Strike rate in innings"
      valueLabel="Innings"
      height={height}
    />
  )
}
