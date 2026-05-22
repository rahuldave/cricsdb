/**
 * Mix histogram — "where does this player operate?"
 *
 * Spec: internal_docs/spec-mix-and-performance-charts.md §1 (Chart A)
 * + §4.1. One bar per bucket; bar height = the player's share of the
 * discipline-specific unit at that bucket (% of career-in-scope).
 * Phase tint banded as background.
 *
 * Generic across batting (10 position buckets) / bowling (20 over
 * buckets) / fielding (10 dismissed-position buckets) — caller
 * supplies the bucket axis via `entries` + `bucketLabel`.
 */

import { niceYAxis } from './niceAxis'

export interface MixEntry {
  bucket: number
  share: number          // 0-1, sums to 1 across entries (or less if cohort has gaps)
  raw: number            // underlying count for the hover tooltip
  tooltip: string        // native title attribute text
}

interface Props {
  entries: MixEntry[]
  bucketLabel: (bucket: number) => string
  /** Per-bucket background tint colour (or null to skip). Used to band
   *  powerplay / middle / death (bowling) or top-order / middle /
   *  lower (batting + fielding). */
  phaseTint?: (bucket: number) => string | null
  /** Caption rendered above the chart (e.g. "Over mix"). */
  title?: string
  /** Italic caption under the title — typically the unit hint. */
  subtitle?: string
  height?: number
}

const BAR_COLOR = '#3C5B7A'  // WISDEN.slate
const BAR_OPACITY = 0.8
const VB_W = 100

export default function MixHistogram({
  entries, bucketLabel, phaseTint,
  title, subtitle, height = 80,
}: Props) {
  if (entries.length === 0) return null

  const rawMax = Math.max(...entries.map(e => e.share), 0.0001)
  const barW = VB_W / entries.length
  const barInset = Math.min(barW * 0.15, 0.4)
  // Nice y-axis: round step (5%/10%/20% etc.) instead of rawMax/2.
  // User-flagged 2026-05-22 — see niceAxis.ts header.
  const { ticks: yTicks, niceMax } = niceYAxis(rawMax)
  const fmtPct = (v: number) => `${Math.round(v * 100)}%`

  return (
    <div className="wisden-mix-histogram" style={{ width: '100%' }}>
      {(title || subtitle) && (
        <div style={{ marginBottom: 4 }}>
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
      )}
      {/* Layout: small left column for y-axis labels + SVG chart
          stretching to fill. The labels live outside the SVG because
          preserveAspectRatio="none" would distort text inside. */}
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 4 }}>
        <div style={{
          position: 'relative', width: 28, height,
          fontFamily: 'var(--serif)', fontSize: '0.6rem',
          color: 'var(--ink-faint)', flexShrink: 0,
        }}>
          {yTicks.map((v, i) => {
            const y = (v / niceMax) * height
            return (
              <div key={`yt-${i}`} style={{
                position: 'absolute',
                right: 2,
                top: height - y,
                transform: 'translateY(-50%)',
                lineHeight: 1,
                whiteSpace: 'nowrap',
              }}>{fmtPct(v)}</div>
            )
          })}
        </div>
        <svg
          viewBox={`0 0 ${VB_W} ${height}`}
          preserveAspectRatio="none"
          style={{ width: '100%', height, display: 'block', flex: 1 }}
          aria-label={title ?? 'Mix histogram'}
        >
          {/* Phase tint backgrounds — one rect per bucket spanning full
              height when phaseTint returns a colour. */}
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
          {/* Y-axis gridlines — faint horizontal rules at each tick. */}
          {yTicks.map((v, i) => {
            if (v === 0) return null
            const y = height - (v / niceMax) * height
            return (
              <line key={`gl-${i}`}
                x1={0} x2={VB_W} y1={y} y2={y}
                stroke="#1A1714" strokeWidth={0.2} opacity={0.18}
                strokeDasharray="0.6 0.6" />
            )
          })}
          {/* Share bars */}
          {entries.map((e, i) => {
            const value_h = (e.share / niceMax) * height
            return (
              <g key={i}>
                <title>{e.tooltip}</title>
                <rect
                  x={i * barW + barInset}
                  y={height - value_h}
                  width={Math.max(barW - 2 * barInset, 0.3)}
                  height={value_h}
                  fill={BAR_COLOR}
                  opacity={BAR_OPACITY}
                />
              </g>
            )
          })}
          {/* baseline */}
          <line x1={0} x2={VB_W} y1={height} y2={height}
                stroke="#1A1714" strokeWidth={0.3} opacity={0.35} />
        </svg>
      </div>
      {/* Bucket tick labels — kept outside the SVG so font sizing
          doesn't get viewBox-distorted by preserveAspectRatio="none".
          Padded left by the y-axis label column width + gap. */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${entries.length}, 1fr)`,
        marginTop: 2,
        marginLeft: 32,
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
    </div>
  )
}
