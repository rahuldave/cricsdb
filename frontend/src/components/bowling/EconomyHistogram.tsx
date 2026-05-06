/**
 * Continuous-bin economy (RPO) histogram. Spec
 * §12.2.3.
 *
 * Bin width 1 RPO across [3, 13+]. Single neutral palette (no
 * tiering) — economy is continuous; the milestone chips below
 * carry the threshold readings.
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN } from '../charts/palette'
import { buildEconomyHistogramRows } from './distributionBins'
import type { BowlerEconomyBlock } from '../../types'

interface Props {
  block: BowlerEconomyBlock
  title?: string
  height?: number
}

const COLOR_SCHEME = [WISDEN.indigo]

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
      colorScheme={COLOR_SCHEME}
      title={title}
      categoryLabel="RPO in innings"
      valueLabel="Innings"
      height={height}
    />
  )
}
