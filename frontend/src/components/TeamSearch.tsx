import { useState, useEffect, useRef } from 'react'
import { getTeams } from '../api'
import { useFilters } from './FilterBar'
import type { TeamInfo } from '../types'

interface TeamSearchProps {
  onSelect: (teamName: string) => void
  placeholder?: string
  initialValue?: string
}

export default function TeamSearch({
  onSelect, placeholder, initialValue = '',
}: TeamSearchProps) {
  const filters = useFilters()
  const [query, setQuery] = useState(initialValue)
  const [results, setResults] = useState<TeamInfo[]>([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const suppressedQuery = useRef<string | null>(null)

  useEffect(() => {
    if (suppressedQuery.current === query) {
      suppressedQuery.current = null
      return
    }
    if (query.length < 2) { setResults([]); setOpen(false); return }
    const t = setTimeout(() => {
      getTeams({ ...filters, q: query })
        .then(d => { setResults(d.teams.slice(0, 12)); setOpen(true) })
        .catch(() => {})
    }, 250)
    return () => clearTimeout(t)
  }, [query, filters.gender, filters.team_type])

  useEffect(() => {
    const click = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', click)
    return () => document.removeEventListener('mousedown', click)
  }, [])

  const pick = (name: string) => {
    suppressedQuery.current = name
    setQuery(name)
    setOpen(false)
    onSelect(name)
  }

  return (
    <div ref={containerRef} className="wisden-playersearch">
      <input
        type="text"
        className="wisden-playersearch-input"
        placeholder={placeholder ?? 'Search team…'}
        value={query}
        onChange={e => setQuery(e.target.value)}
        onFocus={() => { if (results.length > 0) setOpen(true) }}
      />
      {open && results.length > 0 && (
        <ul className="wisden-playersearch-list">
          {results.map(t => (
            <li key={t.name} onMouseDown={() => pick(t.name)}>
              <span className="wisden-playersearch-name">{t.name}</span>
              <span className="wisden-playersearch-meta">
                {t.matches} {t.matches === 1 ? 'match' : 'matches'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
