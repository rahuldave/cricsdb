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
  // Gate the search effect on "has the user actually typed?". On page
  // load with initialValue set (e.g. ?team1=Australia), query equals
  // the pre-fill and we don't want to fire a search for it — that
  // would open the dropdown on a reload with a single matching row.
  // Flipping this ref only in the input's onChange handler means a
  // pick (which also calls setQuery programmatically) doesn't count
  // as user input either. More robust than suppressing a specific
  // query string: survives StrictMode double-invoke of useEffect.
  const userTyped = useRef(false)

  useEffect(() => {
    if (!userTyped.current) return
    if (query.length < 2) { setResults([]); setOpen(false); return }
    // cancelled flag protects against stale-fetch setState after
    // unmount or rapid re-typing — same rationale as PlayerSearch.
    let cancelled = false
    const t = setTimeout(() => {
      getTeams({ ...filters, q: query })
        .then(d => {
          if (cancelled) return
          setResults(d.teams.slice(0, 12))
          setOpen(true)
        })
        .catch(() => {})
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [query, filters.gender, filters.team_type])

  useEffect(() => {
    const click = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', click)
    return () => document.removeEventListener('mousedown', click)
  }, [])

  const pick = (name: string) => {
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
        onChange={e => { userTyped.current = true; setQuery(e.target.value) }}
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
