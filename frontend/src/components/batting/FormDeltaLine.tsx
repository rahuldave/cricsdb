/**
 * Form-delta one-line summary for the batter Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §9.2.5.
 *
 * Reads `dossier.form.delta` directly. Both windows always shown
 * (window-independent — toggling the panel's display window does
 * NOT redraw this line). Color the delta numbers by sign.
 */

import type { BatterDistribution } from '../../types'
import { WISDEN } from '../charts/palette'

interface Props {
  dossier: BatterDistribution
}

function signed(v: number | null | undefined): { text: string; color: string } {
  if (v === null || v === undefined) {
    return { text: 'insufficient', color: WISDEN.faint }
  }
  if (v === 0) return { text: '0', color: WISDEN.faint }
  const sign = v > 0 ? '+' : '−'
  const abs = Math.abs(v)
  // 1dp for means, 0dp for medians (medians are integer in cricket).
  const text = `${sign}${abs.toFixed(Number.isInteger(abs) ? 0 : 1)}`
  const color = v > 0 ? '#3F5A2F' : '#7A1F1F'
  return { text, color }
}

function Delta({ value }: { value: number | null | undefined }) {
  const { text, color } = signed(value)
  return (
    <span className="num" style={{ color, fontWeight: 600 }}>{text}</span>
  )
}

export default function FormDeltaLine({ dossier }: Props) {
  const { delta } = dossier.form
  return (
    <div style={{
      fontFamily: 'var(--serif)',
      fontStyle: 'italic',
      fontSize: '0.82rem',
      color: 'var(--ink-faint)',
      marginTop: '0.4rem',
      lineHeight: 1.4,
      display: 'flex',
      flexWrap: 'wrap',
      columnGap: '1.0rem',
      rowGap: '0.1rem',
      alignItems: 'baseline',
    }}>
      <span>Form vs scope (mean · median):</span>
      <span>
        last 10: <Delta value={delta.last_10_mean_minus_lifetime} />
        {' · '}<Delta value={delta.last_10_median_minus_lifetime} />
      </span>
      <span>
        last 60d: <Delta value={delta.last_60d_mean_minus_lifetime} />
        {' · '}<Delta value={delta.last_60d_median_minus_lifetime} />
      </span>
      <span>
        last 6mo: <Delta value={delta.last_6mo_mean_minus_lifetime} />
        {' · '}<Delta value={delta.last_6mo_median_minus_lifetime} />
      </span>
      <span>
        last 1y: <Delta value={delta.last_1yr_mean_minus_lifetime} />
        {' · '}<Delta value={delta.last_1yr_median_minus_lifetime} />
      </span>
    </div>
  )
}
