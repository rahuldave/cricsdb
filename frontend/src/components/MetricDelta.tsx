import type { MetricEnvelope } from '../types'

/** Tiny chip: "↑ +6.2% vs league" / "↓ -3.1% vs league" — color-
 *  coded by direction so the reader doesn't have to remember which
 *  way is "good" for each metric (econ lower-better, RR higher-
 *  better, etc.). Used inline next to compare-grid stat values
 *  AND as a StatCard subtitle on single-team tabs.
 *
 *  Returns null when the envelope is missing, delta is null, or
 *  direction is null (counts) — callers don't need to gate. */
export default function MetricDelta({
  env, withScopeAvg = false, fmt = 1,
}: {
  env: MetricEnvelope | null | undefined
  /** When true, render "(<value> vs <scope_avg>)" as a small prefix
   *  before the chip. Useful for StatCard subtitles where horizontal
   *  space is generous; off for inline compare cells where the chip
   *  alone keeps rows compact. */
  withScopeAvg?: boolean
  /** Decimal places when rendering scope_avg in the subtitle. */
  fmt?: number
}) {
  if (!env || env.delta_pct == null || env.direction == null) return null
  const d = env.delta_pct
  const aligned =
    (env.direction === 'higher_better' && d > 0) ||
    (env.direction === 'lower_better' && d < 0)
  const color = d === 0
    ? 'rgb(120,120,120)'
    : aligned ? 'rgb(36,128,68)' : 'rgb(170,52,52)'
  const arrow = d > 0 ? '↑' : d < 0 ? '↓' : '·'
  const sign = d > 0 ? '+' : ''
  const tip = `${env.value} vs scope avg ${env.scope_avg} — ${sign}${d.toFixed(1)}% ${aligned ? '(better)' : '(worse)'}`
  const scopeAvgText = env.scope_avg != null
    ? typeof env.scope_avg === 'number'
      ? env.scope_avg.toFixed(fmt)
      : env.scope_avg
    : '-'
  return (
    <span title={tip} style={{ whiteSpace: 'nowrap' }}>
      {withScopeAvg && (
        <span style={{ opacity: 0.65, marginRight: '0.4rem' }}>
          vs avg <span className="num">{scopeAvgText}</span>
        </span>
      )}
      <span style={{ color, fontWeight: 500 }}>
        {arrow} {sign}{d.toFixed(1)}%
      </span>
    </span>
  )
}
