interface StatCardProps {
  label: string
  value: string | number | null | undefined
  subtitle?: string
}

export default function StatCard({ label, value, subtitle }: StatCardProps) {
  const display = value == null ? '-' : typeof value === 'number' ? value.toLocaleString() : value
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 text-center shadow-sm">
      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</div>
      <div className="mt-1 text-2xl font-bold text-gray-900">{display}</div>
      {subtitle && <div className="mt-0.5 text-xs text-gray-400">{subtitle}</div>}
    </div>
  )
}
