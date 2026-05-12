import type { ReactNode } from 'react'

export interface ChartHeaderProps {
  title?: ReactNode
  /** Optional second line under the title. Renders only when truthy and
   *  non-empty — empty string ("") collapses the line entirely, so callers
   *  can pass `abbreviateScope(filters)` and let an unfiltered scope hide
   *  the subtitle automatically. */
  subtitle?: ReactNode
}

export default function ChartHeader({ title, subtitle }: ChartHeaderProps) {
  if (!title && !subtitle) return null
  return (
    <>
      {title && <h3 className="wisden-chart-title">{title}</h3>}
      {subtitle && <div className="wisden-chart-subtitle">{subtitle}</div>}
    </>
  )
}
