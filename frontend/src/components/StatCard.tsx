import type React from 'react'

interface StatCardProps {
  label: string
  /** Primary value rendered in the big serif bold slot. Pass a ReactNode
   *  (e.g. <PlayerLink compact />) to make the name a link while keeping
   *  the card's big-number visual weight. */
  value: string | number | React.ReactNode | null | undefined
  /** Secondary line below the value. Pass a ReactNode when the subtitle
   *  needs links (scope phrase, team links on highest_total, etc.). */
  subtitle?: string | React.ReactNode
}

export default function StatCard({ label, value, subtitle }: StatCardProps) {
  const display = value == null
    ? '-'
    : typeof value === 'number'
      ? value.toLocaleString()
      : value
  return (
    <div className="wisden-stat">
      <div className="wisden-stat-label">{label}</div>
      <div className="wisden-stat-value num">{display}</div>
      {subtitle != null && subtitle !== '' && (
        <div className="wisden-stat-sub">{subtitle}</div>
      )}
    </div>
  )
}
