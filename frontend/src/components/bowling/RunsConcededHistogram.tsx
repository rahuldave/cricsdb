/**
 * Continuous-bin runs-conceded (absolute) histogram. Spec
 * §12.2.4. Bin width 5 runs across [0, 60+]. Single neutral
 * palette like the economy histogram.
 */

import { useMemo } from 'react'
import BarChart from '../charts/BarChart'
import { WISDEN } from '../charts/palette'
import { buildRunsConcededHistogramRows } from './distributionBins'
import type { BowlerInningsObservation } from '../../types'

interface Props {
  observations: BowlerInningsObservation[]
  title?: string
  height?: number
}

const COLOR_SCHEME = [WISDEN.slate]

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
      colorScheme={COLOR_SCHEME}
      title={title}
      categoryLabel="Runs conceded"
      valueLabel="Innings"
      height={height}
    />
  )
}
