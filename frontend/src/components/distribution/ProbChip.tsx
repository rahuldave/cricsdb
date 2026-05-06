/**
 * Shared probability chip — renders a backend ProbRecord
 * `{ value, num, denom, ci_low, ci_high }` with Wilson 95% CI.
 *
 * Used by both the bowler Distribution panel (spec §12) and the
 * upcoming batter retrofit (spec §13). One source of truth so
 * the two panels can't drift on small-n styling, hover format,
 * or null handling.
 *
 * Visual contract:
 *  - Value rendered as `XX%` (rounded to 0 dp).
 *  - Below sample-size floor (`denom < 10` by default), the chip
 *    fades to lower opacity to signal small-n caution; the value
 *    stays visible.
 *  - `null` value (denom == 0) renders as `—`, not `0%`.
 *  - Native `title` tooltip on hover/long-press: `[ci_low%-ci_high%]
 *    (n=denom)` — readable on every platform without bespoke
 *    tooltip libraries.
 *  - Polarity controls the fill + text color:
 *    - positive → sage (good outcome — high P)
 *    - negative → muted oxblood (bad outcome — high P)
 *    - neutral  → faint slate (no good/bad framing — conditionals)
 *
 * Spec: internal_docs/spec-distribution-stats.md §11.3 (helper),
 * §12.2.5 (visual contract).
 */

import type { ProbRecord } from '../../types'

export type ProbPolarity = 'positive' | 'negative' | 'neutral'

interface Props {
  label: string
  record: ProbRecord
  polarity: ProbPolarity
  /** Sample-size floor below which the chip fades. Default 10. */
  smallNFloor?: number
}

function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

function tooltipFor(record: ProbRecord): string {
  if (record.denom <= 0) return 'n=0 (no qualifying innings)'
  const lo = fmtPct(record.ci_low, 1)
  const hi = fmtPct(record.ci_high, 1)
  return `95% CI [${lo}–${hi}], n=${record.denom}`
}

export default function ProbChip({ label, record, polarity, smallNFloor = 10 }: Props) {
  const bg =
    polarity === 'positive' ? 'rgba(122, 142, 106, 0.14)'
    : polarity === 'negative' ? 'rgba(160, 59, 59, 0.12)'
    : 'rgba(60, 91, 122, 0.10)'
  const fg =
    polarity === 'positive' ? '#3F5A2F'
    : polarity === 'negative' ? '#7A1F1F'
    : '#3C5B7A'

  const isNull = record.value === null || record.denom <= 0
  const lowN = !isNull && record.denom < smallNFloor

  return (
    <span
      title={tooltipFor(record)}
      style={{
        display: 'inline-flex', alignItems: 'baseline', gap: '0.35rem',
        padding: '0.18rem 0.55rem', borderRadius: '999px',
        background: bg, color: fg,
        fontSize: '0.72rem',
        fontFamily: 'var(--serif)', fontStyle: 'italic',
        opacity: lowN ? 0.55 : 1,
        cursor: 'help',
      }}
    >
      <span>{label}</span>
      <span className="num" style={{
        fontStyle: 'normal', fontWeight: 600, fontSize: '0.82rem',
      }}>{fmtPct(record.value)}</span>
    </span>
  )
}
