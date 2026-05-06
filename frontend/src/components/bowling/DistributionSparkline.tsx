/**
 * Generic per-innings sparkline for the bowler Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §12.2.6.
 *
 * Renders one bar per qualifying spell, height = the metric value
 * (wickets / economy / runs conceded). Per-tab callers bind the
 * `valueAccessor` to the metric they care about; per-tab color
 * tiering is via `colorAccessor`.
 *
 * **Desktop interaction** (per spell ≥ 720px viewport):
 *  - Hover a bar → native title tooltip with date + key value.
 *  - Click a bar → navigate to /matches/:matchId.
 *
 * **Mobile interaction** (< 720px viewport):
 *  - None. Bars are rendered with `pointer-events: none` via CSS.
 *  - Sparkline is purely impressionistic; the season-tick axis
 *    below carries the date-context affordance.
 *
 * Why no mobile interaction: 2-150 bars across a 342px panel
 * width is anywhere from 26px (tappable) to 2px (impossible) per
 * bar. Inconsistent tap targets are worse than no tap targets;
 * users rely on the SeasonTickAxis + the tab pages for navigation.
 */

import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { BowlerInningsObservation } from '../../types'

type ColorAccessor = (obs: BowlerInningsObservation, value: number) => string

interface Props {
  observations: BowlerInningsObservation[]
  /** Per-bar metric value extractor — wickets / economy / runs_conceded. */
  valueAccessor: (obs: BowlerInningsObservation) => number
  /** Optional horizontal reference line (e.g. mean wkts, pool econ). */
  referenceValue?: number | null
  /** Per-bar color (defaults to faint slate). */
  colorAccessor?: ColorAccessor
  /** Per-bar tooltip text (date + key value). */
  tooltipAccessor: (obs: BowlerInningsObservation, value: number) => string
  height?: number
}

const DEFAULT_COLOR = '#3C5B7A'  // WISDEN.slate

export default function DistributionSparkline({
  observations,
  valueAccessor,
  referenceValue,
  colorAccessor,
  tooltipAccessor,
  height = 36,
}: Props) {
  const navigate = useNavigate()
  const series = useMemo(
    () => observations.map(o => valueAccessor(o)),
    [observations, valueAccessor],
  )

  if (series.length === 0) return null

  const VB_W = 100
  const max = Math.max(...series, 1)
  const barW = VB_W / series.length
  const barInset = Math.min(barW * 0.15, 0.4)

  const refY = (referenceValue !== undefined && referenceValue !== null
                && referenceValue > 0 && referenceValue <= max)
    ? height - (referenceValue / max) * height
    : null

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${height}`}
      preserveAspectRatio="none"
      className="wisden-dist-sparkline"
      style={{ width: '100%', height, display: 'block' }}
      aria-label="Per-innings distribution sparkline"
    >
      {refY !== null && (
        <line
          x1={0} x2={VB_W}
          y1={refY} y2={refY}
          stroke="#1A1714"
          strokeWidth={0.5}
          opacity={0.85}
        />
      )}
      {observations.map((o, i) => {
        const v = series[i]
        const h = (v / max) * height
        const fill = colorAccessor ? colorAccessor(o, v) : DEFAULT_COLOR
        return (
          <a
            key={i}
            href={`/matches/${o.match_id}`}
            onClick={(e) => {
              e.preventDefault()
              navigate(`/matches/${o.match_id}`)
            }}
          >
            <title>{tooltipAccessor(o, v)}</title>
            <rect
              x={i * barW + barInset}
              y={height - h}
              width={Math.max(barW - 2 * barInset, 0.3)}
              height={h}
              fill={fill}
              opacity={0.85}
            />
          </a>
        )
      })}
    </svg>
  )
}
