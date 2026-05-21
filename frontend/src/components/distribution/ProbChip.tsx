/**
 * Shared probability chip — renders a backend ProbRecord
 * `{ value, num, denom, ci_low, ci_high }` with Wilson 95% CI, and
 * (PT5 of spec-prob-baselines.md) an Option C cohort-baseline caption
 * below the pill when the record carries `scope_avg / delta_pct /
 * direction / sample_size`.
 *
 * Used by both the bowler and batter Distribution panels + the
 * fielder chips row. One source of truth so the consumers can't
 * drift on small-n styling, hover format, or null handling.
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
 *  - **Tint matches the histogram + sparkline tier color for the
 *    same outcome** (revised 2026-05-06). Caller picks the tier
 *    its threshold falls in and passes the matching `tint` from
 *    `WISDEN_TIER_TINTS`. This is what makes a P(≥3) chip color-
 *    match the wickets histogram bar at value 3.
 *  - **Cohort baseline caption (PT5 of spec-prob-baselines.md)**
 *    renders below the pill when `record.scope_avg` is defined and
 *    `record.direction` is set. Form: `vs XX% ↑+YY%` in oxblood
 *    when the player trails the cohort (per `direction` polarity)
 *    or forest-green when ahead. `direction = null` (descriptive
 *    chips like fielding P(=1)) renders no caption. Null scope_avg
 *    on a known-cohort chip (below-sample) renders "vs — (below
 *    sample)" in muted italic.
 *
 * Spec: internal_docs/spec-distribution-stats.md §11.3 (helper),
 * §12.2.5 (visual contract); internal_docs/spec-prob-baselines.md
 * §5 Option C (caption + polarity).
 */

import type { ProbRecord } from '../../types'

// Per CLAUDE.md "Accent strokes" — oxblood for under-cohort,
// forest-green for over-cohort. Matches the inline MetricDelta
// rendering elsewhere in the codebase.
const COLOR_GOOD = '#3F7A4D'
const COLOR_BAD = '#7A1F1F'

interface Props {
  label: string
  record: ProbRecord
  /** {bg, fg} pair from WISDEN_TIER_TINTS — pick the tier the
   *  chip's threshold falls in via `tintForTierColor(tierColor)`. */
  tint: { bg: string; fg: string }
  /** Sample-size floor below which the chip fades. Default 10. */
  smallNFloor?: number
}

function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

function fmtPctSmart(v: number | null | undefined): string {
  // Cohort scope_avg is often a small probability (e.g. 0.012 →
  // "1%" loses meaning). When the value is < 5%, show 1 decimal so
  // P(≥100) cohort=1.2% reads as "1.2%" not "1%".
  if (v === null || v === undefined) return '—'
  const pct = v * 100
  if (pct < 5) return `${pct.toFixed(1)}%`
  return `${pct.toFixed(0)}%`
}

function fmtDelta(delta_pct: number): string {
  // delta_pct is signed; magnitude formatted to 0 dp + sign character.
  const mag = Math.abs(delta_pct).toFixed(0)
  if (delta_pct > 0) return `+${mag}%`
  if (delta_pct < 0) return `−${mag}%`
  return '0%'
}

function tooltipFor(record: ProbRecord): string {
  if (record.denom <= 0) return 'n=0 (no qualifying innings)'
  const lo = fmtPct(record.ci_low, 1)
  const hi = fmtPct(record.ci_high, 1)
  const base = `95% CI [${lo}–${hi}], n=${record.denom}`
  if (
    record.scope_avg !== null && record.scope_avg !== undefined &&
    record.sample_size
  ) {
    return `${base} · cohort ${fmtPctSmart(record.scope_avg)} (n=${record.sample_size})`
  }
  return base
}

/**
 * Whether the player's delta is "good" given the chip's polarity.
 * higher_better + positive → green ↑; lower_better + negative → green ↓.
 */
function deltaPolarity(
  delta_pct: number,
  direction: 'higher_better' | 'lower_better',
): 'good' | 'bad' | 'neutral' {
  if (delta_pct === 0) return 'neutral'
  const positive = delta_pct > 0
  if (direction === 'higher_better') return positive ? 'good' : 'bad'
  return positive ? 'bad' : 'good'
}

function arrowFor(delta_pct: number): string {
  if (delta_pct > 0) return '↑'
  if (delta_pct < 0) return '↓'
  return ''
}

function captionFor(record: ProbRecord): React.ReactNode | null {
  // Only render captions for chips whose backend has actually wired
  // the cohort fields. Bowler/batter/fielder distribution chips do;
  // team / compare-grid chips don't (deferred to follow-up spec).
  // Detect by checking direction — a wired-and-directional chip has
  // 'higher_better' | 'lower_better'. direction === null is wired-
  // and-descriptive (e.g. fielding P(=1)) — no caption.
  const dir = record.direction
  if (dir === undefined) return null  // not wired
  if (dir === null) return null       // descriptive — no orientation

  // Below-sample (cohort cliff): scope_avg is null but direction is
  // set. Render "vs — (below sample)" in muted italic.
  if (record.scope_avg === null || record.scope_avg === undefined) {
    return (
      <span
        style={{
          fontFamily: 'var(--serif)', fontStyle: 'italic',
          fontSize: '0.65rem', color: 'var(--ink-faint)',
          marginTop: '0.1rem', textAlign: 'center', display: 'block',
        }}
      >
        vs — (below sample)
      </span>
    )
  }

  // delta_pct may be null when scope_avg is 0 (e.g. rare-event cohort
  // with no occurrences) — fall back to "vs X%" without arrow/delta.
  const dp = record.delta_pct
  // No "vs cohort" prefix here — the parent chip-row renders a single
  // leading "vs cohort" label so the term doesn't repeat per chip.
  // Per spec-prob-baselines.md PT5.F follow-up (2026-05-21 user fb).
  const baseText = `${fmtPctSmart(record.scope_avg)}`
  if (dp === null || dp === undefined) {
    return (
      <span
        className="prob-chip-caption"
        style={{
          fontFamily: 'var(--serif)', fontStyle: 'italic',
          fontSize: '0.7rem', color: 'var(--ink-faint)',
          marginTop: '0.1rem', textAlign: 'center', display: 'block',
        }}
      >
        {baseText}
      </span>
    )
  }

  const polarity = deltaPolarity(dp, dir)
  const deltaColor = polarity === 'good' ? COLOR_GOOD
    : polarity === 'bad' ? COLOR_BAD
    : 'var(--ink-faint)'

  // "vs XX%" stays in the codebase's regular comparison-text style
  // (muted italic) so it reads as an anchor, not a verdict. Only the
  // "↑+YY%" delta carries the polarity color — that's the actionable
  // signal. Matches the convention used elsewhere (MetricDelta etc.).
  return (
    <span
      className="prob-chip-caption"
      style={{
        fontFamily: 'var(--serif)', fontStyle: 'italic',
        fontSize: '0.7rem', color: 'var(--ink-faint)',
        marginTop: '0.1rem', textAlign: 'center', display: 'block',
        whiteSpace: 'nowrap',
      }}
    >
      {baseText}{' '}
      <span style={{ color: deltaColor }}>
        {arrowFor(dp)}{fmtDelta(dp)}
      </span>
    </span>
  )
}

export default function ProbChip({ label, record, tint, smallNFloor = 10 }: Props) {
  const isNull = record.value === null || record.denom <= 0
  const lowN = !isNull && record.denom < smallNFloor
  const caption = captionFor(record)

  // When the caption renders, wrap the pill + caption in a flex-column
  // so the caption sits centered under the pill. When no caption (e.g.
  // chip not wired with cohort fields), the pill renders unchanged —
  // preserves the pre-PT5 layout for team / compare-grid chips.
  const pill = (
    <span
      title={tooltipFor(record)}
      style={{
        display: 'inline-flex', alignItems: 'baseline', gap: '0.35rem',
        padding: '0.18rem 0.55rem', borderRadius: '999px',
        background: tint.bg, color: tint.fg,
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

  if (caption === null) return pill

  return (
    <span style={{
      display: 'inline-flex', flexDirection: 'column',
      alignItems: 'center', verticalAlign: 'top',
    }}>
      {pill}
      {caption}
    </span>
  )
}
