/**
 * Form-delta two-line summary for the team-batting Distribution
 * panel. Spec: internal_docs/spec-distribution-stats.md §17.3.
 *
 * Reads `dossier.form.delta`. Window-independent — does not redraw
 * when the metric tab or window toggle changes. Two metrics shown
 * per window (runs.mean delta + run_rate.pool delta).
 *
 * Color discipline (CLAUDE.md "Form deltas in oxblood — sign carries
 * direction"): every delta value renders in oxblood regardless of
 * sign. The +/− sign carries direction; the color asserts "this is
 * form, vs scope baseline." No green/red polarity.
 *
 * Layout: scope-baseline row above the delta row so each delta is
 * self-anchoring — a reader doesn't have to remember/derive the
 * baseline. Rule: CLAUDE.md "Delta lines need the baseline visible
 * (two-line layout)".
 */

import type { TeamBattingDistribution } from '../../types'
import { WISDEN } from '../charts/palette'

interface Props {
  dossier: TeamBattingDistribution
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

export default function TeamBattingFormDeltaLine({ dossier }: Props) {
  const lifetime = dossier.lifetime
  // The strict TeamBattingDistribution type lists every key explicitly
  // for autocomplete; here we look up by template-string so the four
  // windows fit one render helper. Cast is safe — every field exists.
  const delta = dossier.form.delta as unknown as Record<string, number | null>

  function WindowLine({ window, label }: { window: WindowKey; label: string }) {
    return (
      <span>
        {label}: runs <Delta value={delta[`${window}_runs_mean_minus_lifetime`]} digits={1} />
        {' · '}RR <Delta value={delta[`${window}_run_rate_pool_minus_lifetime`]} digits={2} />
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
        Scope baseline / innings · runs {fmtMean(lifetime.runs.mean_per_innings, 1)}
        {' · '}RR {fmtMean(lifetime.run_rate.pool, 2)}
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
