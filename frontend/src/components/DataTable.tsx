/**
 * A sortable table with optional paging, row highlighting and row clicks.
 */
import { useState, useEffect, useRef } from 'react'

/** One column of a `DataTable`: the row field it shows, its heading, and how to format it. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface Column<T = any> {
  key: keyof T & string // the row field the column shows and sorts by
  label: string // the column heading
  sortable?: boolean // true lets a click on the heading sort by this column
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  format?: (value: any, row: T) => string | number // turns the cell value into text; without it the value shows as is, or "-" when null
}

/** Props of `DataTable`. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface DataTableProps<T = any> {
  columns: Column<T>[] // the columns, in order
  data: T[] // the rows
  /** Shows a "Showing a–b of n" line with Prev and Next buttons that call `onPage` with the new offset. */
  pagination?: { total: number; limit: number; offset: number; onPage: (offset: number) => void }
  /** Stable identity for a row — required to use highlightKey/onRowClick. */
  rowKey?: (row: T) => string
  /** When set, the row whose key matches gets a yellow highlight and scrolls into view. */
  highlightKey?: string | null
  /** Called when a row is clicked. Rows become hover-able when this is set. */
  onRowClick?: (row: T) => void
  /** Optional per-row class — for static row-state styling (e.g. mark Final rows
   *  in a knockouts mini-table). Receives the row, returns the class string or
   *  undefined to add nothing. Joined alongside is-highlighted / is-clickable. */
  rowClass?: (row: T) => string | undefined
}

/** Show rows in a table that sorts by a clicked column, and pages, highlights or reacts to clicks when asked. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function DataTable<T extends Record<string, any> = Record<string, any>>({
  columns, data, pagination, rowKey, highlightKey, onRowClick, rowClass,
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
              rowClass ? (rowClass(row) || '') : '',
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
