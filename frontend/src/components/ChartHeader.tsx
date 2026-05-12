import type { CSSProperties, ReactNode } from 'react'
import { abbreviateScope } from './scopeLinks'
import { useFilters } from '../hooks/useFilters'

export interface ChartHeaderProps {
  title?: ReactNode
  /** Optional subtitle. Renders only when truthy and non-empty — empty
   *  string ("") collapses the line entirely, so callers can pass
   *  `abbreviateScope(filters)` and let an unfiltered scope hide the
   *  subtitle automatically. */
  subtitle?: ReactNode
  /** Extra className appended to the subtitle element. e.g. "num" for
   *  tabular numerals on a score line. */
  subtitleClassName?: string
  /** 'chart' (default) — bold h3 title with subtitle on its own line below.
   *  'section'         — italic label on the left, right-aligned subtitle
   *                       on the same flex row, followed by a rule hr.
   *                       Matches the per-team grid headers on
   *                       MatchScorecard. */
  variant?: 'chart' | 'section'
}

export default function ChartHeader({
  title,
  subtitle,
  subtitleClassName,
  variant = 'chart',
}: ChartHeaderProps) {
  if (!title && !subtitle) return null
  const subClass = (base: string) =>
    subtitleClassName ? `${base} ${subtitleClassName}` : base

  if (variant === 'section') {
    return (
      <>
        <div className="section-head">
          {title && <span className="section-label">{title}</span>}
          {subtitle && <span className={subClass('wisden-chart-sub')}>{subtitle}</span>}
        </div>
        <div className="rule" />
      </>
    )
  }

  return (
    <>
      {title && <h3 className="wisden-chart-title">{title}</h3>}
      {subtitle && <div className={subClass('wisden-chart-subtitle')}>{subtitle}</div>}
    </>
  )
}

export interface SectionHeaderProps {
  title: ReactNode
  /** Optional subtitle. If omitted, auto-resolves to abbreviateScope(filters)
   *  — the filter-state reminder line. Pass "" to suppress; pass a string or
   *  ReactNode to override. */
  subtitle?: ReactNode
  /** Forwarded to the underlying h3 — used by callers that override the
   *  default margin (e.g. landing pages with marginTop tweaks). */
  style?: CSSProperties
}

/**
 * Section-level heading — the centered serif-bold h3 used to label a block
 * (table, chart, sub-group) inside a scope-driven page. Single source for the
 * wisden-section-title pattern, with an optional faint italic subtitle line
 * below that auto-fills from the active FilterBar scope unless overridden.
 *
 * Auto-subtitle uses the same opt-out shape as the chart HOC wrappers:
 *   subtitle === undefined  →  abbreviateScope(useFilters())  (auto)
 *   subtitle === ""         →  suppressed
 *   subtitle === any other  →  used verbatim
 */
export function SectionHeader({ title, subtitle, style }: SectionHeaderProps) {
  const filters = useFilters()
  const effectiveSubtitle = subtitle ?? abbreviateScope(filters)
  return (
    <>
      <h3 className="wisden-section-title" style={style}>{title}</h3>
      {effectiveSubtitle && (
        <div className="wisden-section-sub">{effectiveSubtitle}</div>
      )}
    </>
  )
}
