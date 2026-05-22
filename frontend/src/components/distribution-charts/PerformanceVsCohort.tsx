/**
 * Performance vs cohort — "how does this player perform there?"
 *
 * Spec: internal_docs/spec-mix-and-performance-charts.md §1 (Chart B)
 * + §4.2. Same X-axis as MixHistogram; player per-bucket rate as a
 * bar, cohort rate as a forest-green tick at the matching X position
 * (matches the colors.md reference-line convention).
 *
 * Buckets where the player's mix is exactly zero render at 50%
 * opacity (cohort tick still drawn — reader can see what the
 * comparison would be IF the player operated there).
 *
 * No min-N threshold gating per spec §1.
 */

const COHORT_COLOR = '#3F7A4D'  // WISDEN.forest — reference-line convention
const PLAYER_COLOR = '#3C5B7A'  // WISDEN.slate
const PLAYER_OPACITY_ACTIVE = 0.8
const PLAYER_OPACITY_FADED  = 0.4
const VB_W = 100
const TICK_HEIGHT_PX = 1.0
const TICK_OVERHANG_FRAC = 0.10  // 10% of bar width on each side

export interface PerfEntry {
  bucket: number
  playerValue: number | null
  cohortValue: number | null
  /** True when the player has zero mix here (cohort still drawn). */
  faded: boolean
  /** Optional native title tooltip — caller composes per-bucket. */
  tooltip?: string
}

interface Props {
  entries: PerfEntry[]
  bucketLabel: (bucket: number) => string
  phaseTint?: (bucket: number) => string | null
  title?: string
  subtitle?: string
  /** Y-axis caption rendered as a small italic note above-left. */
  yLabel?: string
  /** Format tick value labels (e.g. (v)=>v.toFixed(1)). Used for
   *  the legend-anchor display only — the chart itself doesn't draw
   *  numeric y-ticks because the goal is comparison shape, not
   *  precise read-off. */
  yFmt?: (v: number) => string
  height?: number
}

export default function PerformanceVsCohort({
  entries, bucketLabel, phaseTint,
  title, subtitle, yLabel, yFmt,
  height = 80,
}: Props) {
  if (entries.length === 0) return null

  const allValues: number[] = []
  for (const e of entries) {
    if (e.playerValue != null) allValues.push(e.playerValue)
    if (e.cohortValue != null) allValues.push(e.cohortValue)
  }
  const max = Math.max(...allValues, 0.0001)

  const barW = VB_W / entries.length
  const barInset = Math.min(barW * 0.15, 0.4)
  const tickW = barW + 2 * barW * TICK_OVERHANG_FRAC

  return (
    <div className="wisden-perf-cohort" style={{ width: '100%' }}>
      {(title || subtitle || yLabel) && (
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'baseline', marginBottom: 4,
        }}>
          <div>
            {title && (
              <div style={{
                fontFamily: 'var(--serif)',
                fontSize: '0.85rem',
                color: 'var(--ink)',
              }}>{title}</div>
            )}
            {subtitle && (
              <div style={{
                fontFamily: 'var(--serif)',
                fontStyle: 'italic',
                fontSize: '0.7rem',
                color: 'var(--ink-faint)',
              }}>{subtitle}</div>
            )}
          </div>
          {yLabel && (
            <div style={{
              fontFamily: 'var(--serif)',
              fontStyle: 'italic',
              fontSize: '0.7rem',
              color: 'var(--ink-faint)',
            }}>{yLabel}</div>
          )}
        </div>
      )}
      <svg
        viewBox={`0 0 ${VB_W} ${height}`}
        preserveAspectRatio="none"
        style={{ width: '100%', height, display: 'block' }}
        aria-label={title ?? 'Performance vs cohort'}
      >
        {phaseTint && entries.map((e, i) => {
          const fill = phaseTint(e.bucket)
          if (!fill) return null
          return (
            <rect
              key={`tint-${i}`}
              x={i * barW} y={0}
              width={barW} height={height}
              fill={fill}
              opacity={0.55}
            />
          )
        })}
        {entries.map((e, i) => {
          const op = e.faded ? PLAYER_OPACITY_FADED : PLAYER_OPACITY_ACTIVE
          const v = e.playerValue
          if (v == null || v <= 0) return null
          const value_h = (v / max) * height
          return (
            <g key={`bar-${i}`}>
              {e.tooltip && <title>{e.tooltip}</title>}
              <rect
                x={i * barW + barInset}
                y={height - value_h}
                width={Math.max(barW - 2 * barInset, 0.3)}
                height={value_h}
                fill={PLAYER_COLOR}
                opacity={op}
              />
            </g>
          )
        })}
        {/* Cohort ticks last so they paint on top of the bars. */}
        {entries.map((e, i) => {
          const cv = e.cohortValue
          if (cv == null) return null
          const cy = height - (cv / max) * height
          const cx = i * barW + (barW - tickW) / 2
          return (
            <rect
              key={`tick-${i}`}
              x={cx}
              y={cy - TICK_HEIGHT_PX / 2}
              width={tickW}
              height={TICK_HEIGHT_PX}
              fill={COHORT_COLOR}
              opacity={0.95}
            />
          )
        })}
        {/* baseline */}
        <line x1={0} x2={VB_W} y1={height} y2={height}
              stroke="#1A1714" strokeWidth={0.3} opacity={0.35} />
      </svg>
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${entries.length}, 1fr)`,
        marginTop: 2,
        fontFamily: 'var(--serif)',
        fontSize: '0.6rem',
        color: 'var(--ink-faint)',
        textAlign: 'center',
        lineHeight: 1,
      }}>
        {entries.map((e) => (
          <div key={`lbl-${e.bucket}`}>{bucketLabel(e.bucket)}</div>
        ))}
      </div>
      {/* Inline legend — minimal: player swatch + cohort tick swatch. */}
      <div style={{
        display: 'flex', gap: '0.85rem',
        marginTop: 6,
        fontFamily: 'var(--serif)',
        fontSize: '0.7rem',
        color: 'var(--ink-faint)',
        alignItems: 'center',
      }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <span aria-hidden="true" style={{
            display: 'inline-block', width: 10, height: 8,
            background: PLAYER_COLOR, opacity: PLAYER_OPACITY_ACTIVE,
          }} />
          player
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <span aria-hidden="true" style={{
            display: 'inline-block', width: 14, height: 2,
            background: COHORT_COLOR,
          }} />
          cohort at scope
          {yFmt && entries.some(e => e.cohortValue != null) && (() => {
            const present = entries.filter(e => e.cohortValue != null)
            if (present.length === 0) return null
            const lo = Math.min(...present.map(e => e.cohortValue as number))
            const hi = Math.max(...present.map(e => e.cohortValue as number))
            return (
              <span style={{ marginLeft: '0.3rem', fontStyle: 'italic' }}>
                ({yFmt(lo)}–{yFmt(hi)})
              </span>
            )
          })()}
        </span>
      </div>
    </div>
  )
}
