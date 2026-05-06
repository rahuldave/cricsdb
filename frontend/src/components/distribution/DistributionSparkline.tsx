/**
 * Generic per-innings sparkline. Spec
 * internal_docs/spec-distribution-stats.md §12.2.6 (originally
 * shipped on the bowler panel; lifted here so the batter panel
 * shares the same primitive).
 *
 * Caller supplies a `points[]` list — each point carries the
 * value (bar height), the date (sparkline x-position is implicit
 * from order; date is for the tick axis), the match_id (for
 * desktop click-through), the tooltip text, and an optional
 * per-bar color override. Component knows nothing about
 * Bowler vs Batter observation shapes.
 *
 * Two reference lines per spec §12.2.6 — green scope baseline
 * (where this player usually sits) + black gender-global
 * (where any player at this tier usually sits).
 *
 * Mobile: bar <a> elements get `pointer-events: none` via the
 * `.wisden-dist-sparkline a { pointer-events: none }` rule
 * inside `@media (max-width: 720px)` in index.css.
 */

import { useNavigate } from 'react-router-dom'

export interface SparklinePoint {
  /** ISO date YYYY-MM-DD (used by the SeasonTickAxis sibling). */
  date: string | null
  /** Numeric match identifier — drives the click-to-match href. */
  matchId: number | string
  /** Bar height value — runs / wickets / SR / RPO depending on tab. */
  value: number
  /** Native title tooltip text (date + key value). */
  tooltip: string
  /** Optional per-bar color override (defaults to faint slate). */
  color?: string
}

interface Props {
  points: SparklinePoint[]
  /** Player reference line — scope-baseline mean. Solid black, thicker. */
  playerReferenceValue?: number | null
  /** Global reference line — gender-tiered league centre. Gray, thicker. */
  globalReferenceValue?: number | null
  /** Rolling-N mean overlay (oxbow). Skipped when points.length < N.
   *  Use only on the widest window where smoothing is meaningful. */
  rollingWindow?: number
  height?: number
}

const DEFAULT_COLOR = '#3C5B7A'  // WISDEN.slate
// Reference-line palette revised 2026-05-06: green clashed with the
// histogram fifty/threefer sage tier; red is reserved for the
// rolling-mean overlay (oxbow). Black + gray are unambiguous.
const PLAYER_REF_COLOR = '#1A1714'  // WISDEN.ink — solid black for the player anchor
const GLOBAL_REF_COLOR = '#8A7D70'  // WISDEN.faint — gray-sand for the league anchor
const ROLLING_MEAN_COLOR = '#7A1F1F'  // WISDEN.oxblood — reserved for rolling-mean overlay

export default function DistributionSparkline({
  points,
  playerReferenceValue,
  globalReferenceValue,
  rollingWindow,
  height = 36,
}: Props) {
  const navigate = useNavigate()

  if (points.length === 0) return null

  const VB_W = 100
  const dataMax = Math.max(...points.map(p => p.value), 1)
  // Y-axis max bumped to keep both reference lines on-chart even
  // when data is far below them. See spec §12.2.6.
  const max = Math.max(
    dataMax,
    globalReferenceValue ?? 0,
    playerReferenceValue ?? 0,
  )
  const barW = VB_W / points.length
  const barInset = Math.min(barW * 0.15, 0.4)

  const yFor = (v: number | null | undefined): number | null => {
    if (v === undefined || v === null || v <= 0 || v > max) return null
    return height - (v / max) * height
  }
  const playerY = yFor(playerReferenceValue)
  const globalY = yFor(globalReferenceValue)

  // Rolling mean overlay — anchor each point at the END of its window.
  const rollingPolyline: string | null = (() => {
    if (!rollingWindow || points.length < rollingWindow) return null
    const xs: string[] = []
    for (let i = rollingWindow - 1; i < points.length; i += 1) {
      let sum = 0
      for (let j = i - rollingWindow + 1; j <= i; j += 1) sum += points[j].value
      const mean = sum / rollingWindow
      const x = (i + 0.5) * barW
      const y = height - (mean / max) * height
      xs.push(`${x},${y}`)
    }
    return xs.join(' ')
  })()

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${height}`}
      preserveAspectRatio="none"
      className="wisden-dist-sparkline"
      style={{ width: '100%', height, display: 'block' }}
      aria-label="Per-innings distribution sparkline"
    >
      {/* Global line (gray) FIRST so the player line draws on top
          when they overlap. */}
      {globalY !== null && (
        <line
          x1={0} x2={VB_W}
          y1={globalY} y2={globalY}
          stroke={GLOBAL_REF_COLOR}
          strokeWidth={0.9}
          opacity={0.85}
          data-ref="global"
        />
      )}
      {playerY !== null && (
        <line
          x1={0} x2={VB_W}
          y1={playerY} y2={playerY}
          stroke={PLAYER_REF_COLOR}
          strokeWidth={1.0}
          opacity={0.95}
          data-ref="player"
        />
      )}
      {points.map((p, i) => {
        const h = (p.value / max) * height
        const fill = p.color ?? DEFAULT_COLOR
        return (
          <a
            key={i}
            href={`/matches/${p.matchId}`}
            onClick={(e) => {
              e.preventDefault()
              navigate(`/matches/${p.matchId}`)
            }}
          >
            <title>{p.tooltip}</title>
            <rect
              x={i * barW + barInset}
              y={height - h}
              width={Math.max(barW - 2 * barInset, 0.3)}
              height={h}
              fill={fill}
              opacity={0.95}
            />
          </a>
        )
      })}
      {rollingPolyline && (
        <polyline
          fill="none"
          stroke={ROLLING_MEAN_COLOR}
          strokeWidth={0.7}
          opacity={0.9}
          points={rollingPolyline}
          data-ref="rolling"
        />
      )}
    </svg>
  )
}
