/**
 * Form-delta one-line summary for the bowler Distribution panel.
 * Spec: internal_docs/spec-distribution-stats.md §12.2.7.
 *
 * Reads `dossier.form.delta`. Window-independent — does not redraw
 * when the metric tab or window toggle changes. Two metrics shown
 * per window (wickets-mean delta + economy-pool delta).
 *
 * Polarity flip: positive wickets delta = green (taking more);
 * positive economy delta = RED (going for more — bad for the
 * bowler). Documented in the inline legend.
 */

import type { BowlerDistribution } from '../../types'
import { WISDEN } from '../charts/palette'

interface Props {
  dossier: BowlerDistribution
}

function fmtDelta(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'insufficient'
  if (v === 0) return '0'
  const sign = v > 0 ? '+' : '−'
  const abs = Math.abs(v)
  return `${sign}${abs.toFixed(2)}`
}

function WicketsDelta({ value }: { value: number | null | undefined }) {
  const text = fmtDelta(value)
  let color: string = WISDEN.faint
  if (value !== null && value !== undefined && value !== 0) {
    color = value > 0 ? '#3F5A2F' : '#7A1F1F'
  }
  return <span className="num" style={{ color, fontWeight: 600 }}>{text}</span>
}

function EconomyDelta({ value }: { value: number | null | undefined }) {
  const text = fmtDelta(value)
  let color: string = WISDEN.faint
  if (value !== null && value !== undefined && value !== 0) {
    // Polarity flip — high economy is bad for the bowler.
    color = value > 0 ? '#7A1F1F' : '#3F5A2F'
  }
  return <span className="num" style={{ color, fontWeight: 600 }}>{text}</span>
}

export default function BowlerFormDeltaLine({ dossier }: Props) {
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
      <span>Form vs scope (wkts · econ):</span>
      <span>
        last 10: <WicketsDelta value={delta.last_10_wickets_mean_minus_lifetime} />
        {' · '}<EconomyDelta value={delta.last_10_economy_pool_minus_lifetime} />
      </span>
      <span>
        last 60d: <WicketsDelta value={delta.last_60d_wickets_mean_minus_lifetime} />
        {' · '}<EconomyDelta value={delta.last_60d_economy_pool_minus_lifetime} />
      </span>
      <span>
        last 6mo: <WicketsDelta value={delta.last_6mo_wickets_mean_minus_lifetime} />
        {' · '}<EconomyDelta value={delta.last_6mo_economy_pool_minus_lifetime} />
      </span>
      <span>
        last 1y: <WicketsDelta value={delta.last_1yr_wickets_mean_minus_lifetime} />
        {' · '}<EconomyDelta value={delta.last_1yr_economy_pool_minus_lifetime} />
      </span>
    </div>
  )
}
