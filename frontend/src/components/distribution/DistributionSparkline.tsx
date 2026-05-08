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
 * Two reference lines per spec §12.2.6 — green scope average
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
  /** Optional per-bar opacity override (defaults to BAR_OPACITY).
   *  Used to make the indigo/blue tiers (failure / wicketless /
   *  slow) fully opaque since they wash out worst at 0.8. */
  opacity?: number
}

interface Props {
  points: SparklinePoint[]
  /** Player reference line — scope average mean. Solid black, thicker. */
  playerReferenceValue?: number | null
  /** Global reference line — gender-tiered league centre. Gray, thicker. */
  globalReferenceValue?: number | null
  /** League reference line — same-scope league average (the
   *  comparable team-of-its-class number under the active filter
   *  scope). Forest green, 1.5px. Distinct from `globalReferenceValue`
   *  which spans ALL T20 cricket at gender grain; this one respects
   *  every active filter except the team narrowing. Wired from team
   *  panels via the existing /summary endpoint's `scope_avg` envelope. */
  leagueReferenceValue?: number | null
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
const LEAGUE_REF_COLOR = '#3F7A4D'  // WISDEN.forest — same-scope league average
const ROLLING_MEAN_COLOR = '#7A1F1F'  // WISDEN.oxblood — reserved for rolling-mean overlay

// Tunable visual weights — picked 2026-05-06 from a 4-combo
// browser-agent A/B (Kohli + Bumrah, screenshots in /tmp/combo-*).
// Bar 0.8 keeps tier colors clearly distinguishable without
// drowning the lines; player line at 2px stands out as the
// "this player" anchor; global line at 1.5px is subtler context;
// rolling overlay at 1.2px is visible without overpowering.
const BAR_OPACITY = 0.8
const PLAYER_LINE_WIDTH = 2.0
const GLOBAL_LINE_WIDTH = 1.5
const LEAGUE_LINE_WIDTH = 1.5
const ROLLING_LINE_WIDTH = 1.2
// Below-baseline stub zone — every bar extends 4px below the
// baseline so value=0 bars (ducks / wicketless spells) remain
// visible as a 4px-tall colored strip and stay clickable for
// match navigation. Per user feedback 2026-05-06.
const STUB_HEIGHT = 4

export default function DistributionSparkline({
  points,
  playerReferenceValue,
  globalReferenceValue,
  leagueReferenceValue,
  rollingWindow,
  height = 36,
}: Props) {
  const navigate = useNavigate()

  if (points.length === 0) return null

  const VB_W = 100
  const dataMax = Math.max(...points.map(p => p.value), 1)
  // Y-axis max bumped to keep all three reference lines on-chart even
  // when data is far below them. See spec §12.2.6.
  const max = Math.max(
    dataMax,
    globalReferenceValue ?? 0,
    playerReferenceValue ?? 0,
    leagueReferenceValue ?? 0,
  )
  const barW = VB_W / points.length
  const barInset = Math.min(barW * 0.15, 0.4)

  // Two zones: value-bar zone above the baseline (size = height -
  // STUB_HEIGHT), stub zone below (size = STUB_HEIGHT). Reference
  // lines + rolling mean live in the value zone only.
  const baselineY = height - STUB_HEIGHT
  const valueZone = baselineY  // size of the value-bar zone

  const yFor = (v: number | null | undefined): number | null => {
    if (v === undefined || v === null || v <= 0 || v > max) return null
    return baselineY - (v / max) * valueZone
  }
  const playerY = yFor(playerReferenceValue)
  const globalY = yFor(globalReferenceValue)
  const leagueY = yFor(leagueReferenceValue)

  // Rolling mean overlay — anchor each point at the END of its window.
  const rollingPolyline: string | null = (() => {
    if (!rollingWindow || points.length < rollingWindow) return null
    const xs: string[] = []
    for (let i = rollingWindow - 1; i < points.length; i += 1) {
      let sum = 0
      for (let j = i - rollingWindow + 1; j <= i; j += 1) sum += points[j].value
      const mean = sum / rollingWindow
      const x = (i + 0.5) * barW
      const y = baselineY - (mean / max) * valueZone
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
      {/* Reference lines drawn back-to-front (gray global → forest
          league → black player) so the most-specific anchor (this
          team's scope mean) draws on top of the broader contexts. */}
      {globalY !== null && (
        <line
          x1={0} x2={VB_W}
          y1={globalY} y2={globalY}
          stroke={GLOBAL_REF_COLOR}
          strokeWidth={GLOBAL_LINE_WIDTH}
          opacity={0.85}
          data-ref="global"
        />
      )}
      {leagueY !== null && (
        <line
          x1={0} x2={VB_W}
          y1={leagueY} y2={leagueY}
          stroke={LEAGUE_REF_COLOR}
          strokeWidth={LEAGUE_LINE_WIDTH}
          opacity={0.9}
          data-ref="league"
        />
      )}
      {playerY !== null && (
        <line
          x1={0} x2={VB_W}
          y1={playerY} y2={playerY}
          stroke={PLAYER_REF_COLOR}
          strokeWidth={PLAYER_LINE_WIDTH}
          opacity={0.95}
          data-ref="player"
        />
      )}
      {points.map((p, i) => {
        const value_h = (p.value / max) * valueZone
        // Single rect spans value-bar (above baseline) + stub
        // (below baseline). For value=0 only the stub renders;
        // for value>0 the rect is value_h + STUB_HEIGHT tall.
        const fill = p.color ?? DEFAULT_COLOR
        const opacity = p.opacity ?? BAR_OPACITY
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
              y={baselineY - value_h}
              width={Math.max(barW - 2 * barInset, 0.3)}
              height={value_h + STUB_HEIGHT}
              fill={fill}
              opacity={opacity}
            />
          </a>
        )
      })}
      {/* baseline rule — separates value-bar zone from stub zone */}
      <line
        x1={0} x2={VB_W}
        y1={baselineY} y2={baselineY}
        stroke="#1A1714"
        strokeWidth={0.3}
        opacity={0.35}
      />
      {rollingPolyline && (
        <polyline
          fill="none"
          stroke={ROLLING_MEAN_COLOR}
          strokeWidth={ROLLING_LINE_WIDTH}
          opacity={0.9}
          points={rollingPolyline}
          data-ref="rolling"
        />
      )}
    </svg>
  )
}
