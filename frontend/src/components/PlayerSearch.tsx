import { useState, useEffect, useRef } from 'react'
import { searchPlayers } from '../api'
import type { PlayerSearchResult } from '../types'

interface PlayerSearchProps {
  role: 'batter' | 'bowler'
  onSelect: (player: PlayerSearchResult) => void
  placeholder?: string
}

export default function PlayerSearch({ role, onSelect, placeholder }: PlayerSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlayerSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)
  // After a user picks a result we set the input value to the picked
  // name. The query effect would otherwise re-fetch and re-open the
  // dropdown 300ms later. This ref names the query value whose next
  // effect run should be skipped — when the user types something else
  // the ref no longer matches and search resumes normally.
  const suppressedQuery = useRef<string | null>(null)

  useEffect(() => {
    if (suppressedQuery.current === query) {
      suppressedQuery.current = null
      return
    }
    if (query.length < 2) {
      setResults([]); setOpen(false); setError(null); return
    }
    setLoading(true)
    setError(null)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      try {
        const data = await searchPlayers(query, role)
        setResults(data.players)
        setOpen(true)
      } catch (err) {
        setResults([])
        setOpen(true)
        setError(err instanceof Error ? err.message : 'Search failed')
      }
      setLoading(false)
    }, 300)
    return () => clearTimeout(timerRef.current)
  }, [query, role])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={containerRef} className="wisden-playersearch">
      <input
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder={placeholder || `Search ${role}s…`}
        className="wisden-playersearch-input"
      />
      {loading && <div className="wisden-playersearch-loading">…</div>}
      {open && results.length > 0 && (
        <ul className="wisden-playersearch-list">
          {results.map(p => (
            <li
              key={p.id}
              onClick={() => {
                clearTimeout(timerRef.current)
                suppressedQuery.current = p.name
                onSelect(p)
                setQuery(p.name)
                setOpen(false)
              }}
            >
              <span className="wisden-playersearch-name">{p.name}</span>
              <span className="wisden-playersearch-meta num">{p.innings} inn</span>
            </li>
          ))}
        </ul>
      )}
      {open && results.length === 0 && !loading && query.length >= 2 && !error && (
        <div className="wisden-playersearch-empty">No players found</div>
      )}
      {open && error && !loading && (
        <div className="wisden-playersearch-error">Search failed: {error}</div>
      )}
    </div>
  )
}
