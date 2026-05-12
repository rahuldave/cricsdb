import type { ReactNode } from 'react'

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
