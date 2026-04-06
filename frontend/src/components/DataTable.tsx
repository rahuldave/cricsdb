import { useState, useEffect, useRef } from 'react'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface Column<T = any> {
  key: keyof T & string
  label: string
  sortable?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  format?: (value: any, row: T) => string | number
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface DataTableProps<T = any> {
  columns: Column<T>[]
  data: T[]
  pagination?: { total: number; limit: number; offset: number; onPage: (offset: number) => void }
  /** Stable identity for a row — required to use highlightKey/onRowClick. */
  rowKey?: (row: T) => string
  /** When set, the row whose key matches gets a yellow highlight and scrolls into view. */
  highlightKey?: string | null
  /** Called when a row is clicked. Rows become hover-able when this is set. */
  onRowClick?: (row: T) => void
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function DataTable<T extends Record<string, any> = Record<string, any>>({
  columns, data, pagination, rowKey, highlightKey, onRowClick,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortAsc, setSortAsc] = useState(true)
  const highlightedRowRef = useRef<HTMLTableRowElement | null>(null)

  useEffect(() => {
    if (highlightKey && highlightedRowRef.current) {
      highlightedRowRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [highlightKey])

  const handleSort = (key: string) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(true) }
  }

  const sorted = sortKey
    ? [...data].sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey]
        const cmp = av == null ? 1 : bv == null ? -1 : av < bv ? -1 : av > bv ? 1 : 0
        return sortAsc ? cmp : -cmp
      })
    : data

  return (
    <div className="overflow-x-auto">
      <table className="wisden-table">
        <thead>
          <tr>
            {columns.map(col => (
              <th
                key={col.key}
                className={col.sortable ? 'is-sortable' : undefined}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
              >
                {col.label}
                {sortKey === col.key && (sortAsc ? ' \u25B2' : ' \u25BC')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => {
            const key = rowKey ? rowKey(row) : null
            const isHighlighted = !!(key && highlightKey && key === highlightKey)
            const cls = [
              isHighlighted ? 'is-highlighted' : '',
              onRowClick ? 'is-clickable' : '',
            ].filter(Boolean).join(' ')
            return (
              <tr
                key={key ?? i}
                ref={isHighlighted ? highlightedRowRef : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cls || undefined}
              >
                {columns.map(col => (
                  <td key={col.key}>
                    {col.format ? col.format(row[col.key], row) : String(row[col.key] ?? '-')}
                  </td>
                ))}
              </tr>
            )
          })}
          {sorted.length === 0 && (
            <tr><td colSpan={columns.length} className="wisden-table-empty">No data</td></tr>
          )}
        </tbody>
      </table>
      {pagination && (
        <div className="wisden-pagination">
          <span>Showing <span className="num">{pagination.offset + 1}</span>–<span className="num">{Math.min(pagination.offset + pagination.limit, pagination.total)}</span> of <span className="num">{pagination.total}</span></span>
          <div className="wisden-pagination-buttons">
            <button disabled={pagination.offset === 0} onClick={() => pagination.onPage(Math.max(0, pagination.offset - pagination.limit))}>← Prev</button>
            <button disabled={pagination.offset + pagination.limit >= pagination.total} onClick={() => pagination.onPage(pagination.offset + pagination.limit)}>Next →</button>
          </div>
        </div>
      )}
    </div>
  )
}
