/**
 * Tiny per-innings runs sparkline for the batter Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §9.2.4 + §9.8.
 *
 * Custom inline-SVG (no semiotic) — bars at evenly-spaced x positions
 * for each observation, plus an optional rolling-N mean line overlay
 * (lifetime window only, n ≥ N). Pure presentational; window-driven
 * by the caller passing the right observations slice.
 */

import { useMemo } from 'react'
import type { InningsObservation } from '../../types'
import { WISDEN } from '../charts/palette'

interface Props {
  observations: InningsObservation[]
  /** Optional rolling-mean window. Skipped when observations.length < window. */
  rollingWindow?: number
  height?: number
}

export default function RunsSparkline({
  observations, rollingWindow, height = 36,
}: Props) {
  const series = useMemo(() => observations.map(o => o.runs), [observations])
  const rollingLine = useMemo(() => {
    if (!rollingWindow || series.length < rollingWindow) return null
    const out: number[] = []
    for (let i = rollingWindow - 1; i < series.length; i += 1) {
      let sum = 0
      for (let j = i - rollingWindow + 1; j <= i; j += 1) sum += series[j]
      out.push(sum / rollingWindow)
    }
    return out
  }, [series, rollingWindow])

  if (series.length === 0) return null

  // Plot in a 100×height viewBox so the SVG scales to its container
  // via preserveAspectRatio='none'. Bar width auto from series length.
  const VB_W = 100
  const max = Math.max(...series, 1)
  const barW = VB_W / series.length
  // Inset a hair so adjacent bars don't visually merge at small width.
  const barInset = Math.min(barW * 0.15, 0.4)

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${height}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height, display: 'block' }}
      aria-label="Per-innings runs sparkline"
    >
      {series.map((r, i) => {
        const h = (r / max) * height
        return (
          <rect
            key={i}
            x={i * barW + barInset}
            y={height - h}
            width={Math.max(barW - 2 * barInset, 0.3)}
            height={h}
            fill={WISDEN.slate}
            opacity={0.55}
          />
        )
      })}
      {rollingLine && rollingWindow && (
        <polyline
          fill="none"
          stroke={WISDEN.oxblood}
          strokeWidth={0.6}
          points={rollingLine.map((v, idx) => {
            // Anchor the rolling point at the END of its window (i = rollingWindow - 1 + idx).
            const i = rollingWindow - 1 + idx
            const x = (i + 0.5) * barW
            const y = height - (v / max) * height
            return `${x},${y}`
          }).join(' ')}
        />
      )}
    </svg>
  )
}
