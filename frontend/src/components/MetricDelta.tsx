import type { MetricEnvelope } from '../types'

/** Inline scope-avg subtitle + directional delta chip.
 *
 *  Visual (with `withScopeAvg`):
 *    vs <label> 28.7   ↑ +47.7%
 *
 *  - The "vs <label> <scope_avg>" portion renders whenever
 *    `withScopeAvg && scope_avg != null` (so count metrics that
 *    carry a cohort baseline but no delta still show the baseline).
 *  - The delta chip renders whenever `delta_pct != null` —
 *    coloured by `direction` (green when aligned, red when not,
 *    neutral grey when direction is null or delta is exactly 0).
 *  - Returns null when neither piece can render.
 *
 *  Used by team-side Compare grids (default label='avg') and by
 *  player-side baseline rendering on /players /batting /bowling /
 *  fielding (callers pass label='cohort' per the unified terminology
 *  from spec-prob-baselines §11 / 1a425ae). */
export default function MetricDelta({
  env, withScopeAvg = false, fmt = 1, label = 'avg', scopeAvgTooltip,
}: {
  env: MetricEnvelope | null | undefined
  /** When true, render "vs <label> <scope_avg>" as a small prefix
   *  before the chip. Useful for StatCard subtitles where horizontal
   *  space is generous; off for inline compare cells where the chip
   *  alone keeps rows compact. */
  withScopeAvg?: boolean
  /** Decimal places when rendering scope_avg in the subtitle. */
  fmt?: number
  /** Override the cohort-baseline label. Team-side leaves the default
   *  'avg'; player pages pass 'cohort' to reflect the position-mix
   *  / over-mix / keeper-binary weighted cohort (unified terminology
   *  per spec-prob-baselines §11 / commit 1a425ae). */
  label?: string
  /** Optional tooltip on the "vs <label> N" portion — caller passes
   *  the cohort-mix phrasing per spec §3.4 (e.g. "Position-mix
   *  baseline — Opener (54% of innings); 287 players in cohort"). */
  scopeAvgTooltip?: string
}) {
  if (!env) return null
  const hasScopeAvg = withScopeAvg && env.scope_avg != null
  const hasDelta = env.delta_pct != null
  if (!hasScopeAvg && !hasDelta) return null

  const d = env.delta_pct ?? 0
  const aligned = env.direction != null && (
    (env.direction === 'higher_better' && d > 0) ||
    (env.direction === 'lower_better' && d < 0)
  )
  // Non-directional metric (counts, toss/inning marginals on the
  // Splits Mosaic): render the delta in neutral gray.
  const color =
    env.direction == null || d === 0
      ? 'rgb(120,120,120)'
      : aligned ? 'rgb(36,128,68)' : 'rgb(170,52,52)'
  const arrow = d > 0 ? '↑' : d < 0 ? '↓' : '·'
  const sign = d > 0 ? '+' : ''
  const tip = hasDelta
    ? (env.direction == null
        ? `${env.value} vs ${label} ${env.scope_avg} — ${sign}${d.toFixed(1)}%`
        : `${env.value} vs ${label} ${env.scope_avg} — ${sign}${d.toFixed(1)}% ${aligned ? '(better)' : '(worse)'}`)
    : undefined
  const scopeAvgText = env.scope_avg != null
    ? typeof env.scope_avg === 'number'
      ? env.scope_avg.toFixed(fmt)
      : env.scope_avg
    : '-'
  // Each part stays on its own logical line (no internal wrapping)
  // but the two parts can stack on narrow screens. The container
  // doesn't pin whiteSpace=nowrap on the outer, so when card width
  // can't fit both "vs cohort 29.50" + "↑ +35.7%" inline, the chip
  // flows to a second line — keeping the three-tier read clean at
  // mobile width.
  // flex wrap so the scope-avg span and delta chip can stack on
  // narrow cards (mobile width) without forcing the parent grid
  // track wider than its 1fr allotment. Each child stays whitespace-
  // nowrap internally; only the BETWEEN-pieces break opportunity
  // applies.
  return (
    <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: '0.4rem' }}>
      {hasScopeAvg && (
        <span
          title={scopeAvgTooltip}
          style={{
            opacity: 0.65,
            whiteSpace: 'nowrap',
            cursor: scopeAvgTooltip ? 'help' : undefined,
          }}
        >
          vs {label} <span className="num">{scopeAvgText}</span>
        </span>
      )}
      {hasDelta && (
        <span
          title={tip}
          style={{ color, fontWeight: 500, whiteSpace: 'nowrap' }}
        >
          {arrow} {sign}{d.toFixed(1)}%
        </span>
      )}
    </span>
  )
}
