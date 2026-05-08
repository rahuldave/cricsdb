/**
 * Form-delta two-line summary for the team-fielding Distribution
 * panel. Spec: internal_docs/spec-distribution-stats.md §17.5.
 *
 * Sibling of TeamBattingFormDeltaLine + TeamBowlingFormDeltaLine.
 * Window-independent — does NOT redraw when the metric tab or window
 * toggle changes. Three metrics shown per window (catches.mean delta +
 * run_outs.mean delta + stumpings.mean delta).
 *
 * Color discipline (CLAUDE.md "Form deltas in oxblood — sign carries
 * direction"): every delta value renders in oxblood regardless of
 * sign. Self-anchoring layout: scope-baseline row above the delta
 * row.
 */

import type { TeamFieldingDistribution } from '../../types'
import { WISDEN } from '../charts/palette'

interface Props {
  dossier: TeamFieldingDistribution
}

const OXBLOOD = '#7A1F1F'

function fmtDelta(v: number | null | undefined, digits: number): string {
  if (v === null || v === undefined) return '—'
  if (v === 0) return '0'
  const sign = v > 0 ? '+' : '−'
  return `${sign}${Math.abs(v).toFixed(digits)}`
}

function fmtMean(v: number | null | undefined, digits: number): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(digits)
}

function Delta({ value, digits }: { value: number | null | undefined; digits: number }) {
  const text = fmtDelta(value, digits)
  const color = value === null || value === undefined ? WISDEN.faint : OXBLOOD
  return <span className="num" style={{ color, fontWeight: 600 }}>{text}</span>
}

type WindowKey = 'last_10' | 'last_60d' | 'last_6mo' | 'last_1yr'

export default function TeamFieldingFormDeltaLine({ dossier }: Props) {
  const lifetime = dossier.lifetime
  const delta = dossier.form.delta as unknown as Record<string, number | null>

  function WindowLine({ window, label }: { window: WindowKey; label: string }) {
    return (
      <span>
        {label}: c <Delta value={delta[`${window}_catches_mean_minus_lifetime`]} digits={2} />
        {' · '}ro <Delta value={delta[`${window}_run_outs_mean_minus_lifetime`]} digits={2} />
        {' · '}st <Delta value={delta[`${window}_stumpings_mean_minus_lifetime`]} digits={2} />
      </span>
    )
  }

  return (
    <div style={{
      fontFamily: 'var(--serif)',
      fontStyle: 'italic',
      fontSize: '0.82rem',
      color: 'var(--ink-faint)',
      marginTop: '0.4rem',
      lineHeight: 1.4,
    }}>
      <div>
        Scope baseline / innings · catches {fmtMean(lifetime.catches.mean_per_innings, 2)}
        {' · '}run-outs {fmtMean(lifetime.run_outs.mean_per_innings, 2)}
        {' · '}stumpings {fmtMean(lifetime.stumpings.mean_per_innings, 2)}
      </div>
      <div style={{
        display: 'flex', flexWrap: 'wrap',
        columnGap: '1.0rem', rowGap: '0.1rem',
        alignItems: 'baseline',
      }}>
        <span>Form (Δ vs baseline):</span>
        <WindowLine window="last_10"  label="last 10" />
        <WindowLine window="last_60d" label="last 60d" />
        <WindowLine window="last_6mo" label="last 6mo" />
        <WindowLine window="last_1yr" label="last 1y" />
      </div>
    </div>
  )
}
