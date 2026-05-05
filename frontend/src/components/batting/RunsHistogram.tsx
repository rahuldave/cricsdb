/**
 * Per-innings runs histogram for the batter Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §9.2.2.
 *
 * Wraps the existing semiotic-backed BarChart with the width-10
 * bin scheme + tier coloring. Pure presentational — caller passes
 * the active-window dossier; the chart reflects exactly that
 * window's `runs.observations`.
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN_RUN_TIERS } from '../charts/palette'
import { buildHistogramRows } from './distributionBins'
import type { DistributionDossier } from '../../types'

interface Props {
  dossier: DistributionDossier
  title?: string
  height?: number
}

// Tier colorScheme order matches the order tier strings appear when
// scanned left-to-right across the rows (low bins first → failure
// → building → fifty → century → rare). Semiotic resolves colorBy
// strings to colorScheme indices in encounter order, so listing each
// tier's color in this fixed sequence keeps the assignment stable
// regardless of which tiers happen to be present in the rendered
// rows.
const TIER_ORDER: (keyof typeof WISDEN_RUN_TIERS)[] = [
  'failure', 'building', 'fifty', 'century', 'rare',
]
const COLOR_SCHEME = TIER_ORDER.map(t => WISDEN_RUN_TIERS[t])

export default function RunsHistogram({ dossier, title, height = 220 }: Props) {
  const rows = useMemo(
    () => buildHistogramRows(dossier.runs.observations),
    [dossier.runs.observations],
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
      categoryLabel="Runs in innings"
      valueLabel="Innings"
      height={height}
    />
  )
}
