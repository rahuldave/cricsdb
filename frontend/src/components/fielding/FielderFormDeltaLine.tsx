/**
 * Form-delta one-line summary for the fielder Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §14.2.6.
 *
 * Reads `dossier.form.delta`. Window-independent — does not redraw
 * when the metric tab or window toggle changes. Up to three deltas
 * per window: catches, run-outs, stumpings (when applicable).
 *
 * Color discipline (revised 2026-05-07): form deltas render in
 * **oxblood** regardless of sign. Form is a rolling concept across
 * the codebase visually associated with oxblood (rolling-mean
 * overlay on sparklines uses #7A1F1F). Sign carries direction (+/−);
 * color asserts "this is form, vs scope baseline." No green/red
 * polarity — that conflates "above baseline" with "good," which
 * isn't what a fielder distribution dossier is asserting.
 *
 * Layout (revised 2026-05-07): two lines instead of one. The first
 * line shows the absolute scope-lifetime mean per match for each
 * metric so the deltas on the second line are self-anchoring —
 * a reader doesn't have to remember/derive the baseline.
 */

import type { FielderDistribution } from '../../types'
import { WISDEN } from '../charts/palette'

interface Props {
  dossier: FielderDistribution
}

const OXBLOOD = '#7A1F1F'

function fmtDelta(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  if (v === 0) return '0'
  const sign = v > 0 ? '+' : '−'
  const abs = Math.abs(v)
  return `${sign}${abs.toFixed(2)}`
}

function fmtMean(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(2)
}

function Delta({ value }: { value: number | null | undefined }) {
  const text = fmtDelta(value)
  const color = value === null || value === undefined ? WISDEN.faint : OXBLOOD
  return <span className="num" style={{ color, fontWeight: 600 }}>{text}</span>
}

export default function FielderFormDeltaLine({ dossier }: Props) {
  const { delta } = dossier.form
  const lifetime = dossier.lifetime
  const isKeeper = lifetime.stumpings !== null

  function WindowLine({ window, label }: { window: string; label: string }) {
    return (
      <span>
        {label}: cat <Delta value={delta[`${window}_catches_mean_minus_lifetime`]} />
        {' · '}ro <Delta value={delta[`${window}_run_outs_mean_minus_lifetime`]} />
        {isKeeper && <>
          {' · '}st <Delta value={delta[`${window}_stumpings_mean_minus_lifetime`]} />
        </>}
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
        Scope baseline / match · cat {fmtMean(lifetime.catches.mean_per_match)}
        {' · '}ro {fmtMean(lifetime.run_outs.mean_per_match)}
        {isKeeper && <> · st {fmtMean(lifetime.stumpings?.mean_per_match)}</>}
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
