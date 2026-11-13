/**
 * A small card with a label, a big value and an optional subtitle, used in the rows of headline stats.
 */
import type React from 'react'

/** Props of `StatCard`. */
interface StatCardProps {
  label: string // the caption above the value
  /** Primary value rendered in the big serif bold slot. Pass a ReactNode
   *  (e.g. <PlayerLink compact />) to make the name a link while keeping
   *  the card's big-number visual weight. */
  value: string | number | React.ReactNode | null | undefined
  /** Optional std-dev across in-scope seasons, rendered inline as
   *  `value ± σ`. Pass a pre-formatted string (matching the value's
   *  precision) or a number that will use 2-decimal formatting. Null /
   *  undefined hides the σ entirely — used on volume + extremum tiles
   *  per spec-series-trend-charts.md §D4. */
  stdDev?: string | number | null
  /** Secondary line below the value. Pass a ReactNode when the subtitle
   *  needs links (scope phrase, team links on highest_total, etc.). */
  subtitle?: string | React.ReactNode
}

/** Show one headline stat: its label, its value (with ± σ when given), and a subtitle. Numbers get thousands separators. */
export default function StatCard({ label, value, stdDev, subtitle }: StatCardProps) {
  const display = value == null
    ? '-'
    : typeof value === 'number'
      ? value.toLocaleString()
      : value
  const stdText = stdDev == null
    ? null
    : typeof stdDev === 'number'
      ? stdDev.toFixed(2)
      : stdDev
  return (
    <div className="wisden-stat">
      <div className="wisden-stat-label">{label}</div>
      <div className="wisden-stat-value num">
        {display}
        {stdText != null && value != null && (
          <span className="wisden-stat-std">± {stdText}</span>
        )}
      </div>
      {subtitle != null && subtitle !== '' && (
        <div className="wisden-stat-sub">{subtitle}</div>
      )}
    </div>
  )
}
