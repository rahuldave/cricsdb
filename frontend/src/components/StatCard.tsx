interface StatCardProps {
  label: string
  value: string | number | null | undefined
  subtitle?: string
}

export default function StatCard({ label, value, subtitle }: StatCardProps) {
  const display = value == null ? '-' : typeof value === 'number' ? value.toLocaleString() : value
  return (
    <div className="wisden-stat">
      <div className="wisden-stat-label">{label}</div>
      <div className="wisden-stat-value num">{display}</div>
      {subtitle && <div className="wisden-stat-sub">{subtitle}</div>}
    </div>
  )
}
