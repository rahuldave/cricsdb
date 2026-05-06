/**
 * Per-innings wickets sparkline for the bowler Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §12.2.6.
 *
 * Discrete-value sparkline — each bar's height encodes the integer
 * wicket count (0..6+). Always visible across metric tabs; reads
 * `currentWindow.wickets.observations` regardless of which metric
 * the user has selected.
 */

import { useMemo } from 'react'
import type { BowlerInningsObservation } from '../../types'
import { WISDEN } from '../charts/palette'

interface Props {
  observations: BowlerInningsObservation[]
  /** Optional horizontal mean reference line (e.g. wickets.mean_per_innings). */
  referenceWickets?: number | null
  height?: number
}

export default function WicketsSparkline({
  observations, referenceWickets, height = 36,
}: Props) {
  const series = useMemo(
    () => observations.map(o => o.wickets),
    [observations],
  )

  if (series.length === 0) return null

  const VB_W = 100
  const max = Math.max(...series, 1)
  const barW = VB_W / series.length
  const barInset = Math.min(barW * 0.15, 0.4)

  const refY = (referenceWickets !== undefined && referenceWickets !== null
                && referenceWickets > 0 && referenceWickets <= max)
    ? height - (referenceWickets / max) * height
    : null

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${height}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height, display: 'block' }}
      aria-label="Per-innings wickets sparkline"
    >
      {refY !== null && (
        <line
          x1={0} x2={VB_W}
          y1={refY} y2={refY}
          stroke={WISDEN.ink}
          strokeWidth={0.5}
          opacity={0.85}
        />
      )}
      {series.map((w, i) => {
        const h = (w / max) * height
        // Color-tier bars by wicket level — quick read of "did the
        // bar make it to 3-fer territory".
        const color =
          w === 0 ? WISDEN.faint
          : w <= 2 ? WISDEN.indigo
          : w === 3 ? '#7A8E6A'
          : w === 4 ? WISDEN.ochre
          : '#9C6B17'
        return (
          <rect
            key={i}
            x={i * barW + barInset}
            y={height - h}
            width={Math.max(barW - 2 * barInset, 0.3)}
            height={h}
            fill={color}
            opacity={0.85}
          />
        )
      })}
    </svg>
  )
}
