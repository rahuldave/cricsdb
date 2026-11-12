/**
 * The type-ahead box that finds a team by name within the current filters.
 */
import { useState, useEffect, useRef } from 'react'
import { getTeams } from '../api'
import { useFilters } from '../hooks/useFilters'
import type { TeamInfo } from '../types'

/** Props of `TeamSearch`. */
interface TeamSearchProps {
  onSelect: (teamName: string) => void // called with the name of the team the user picks
  placeholder?: string // the input's placeholder; defaults to "Search team…"
  /** Canonical value — the URL-derived team name. Input shows this
   *  when the user isn't actively typing. Changes from the parent
   *  (e.g. back-nav clearing the URL) propagate naturally. */
  value?: string
}

/** Search teams as the user types (from two letters, after 250 ms) and show up to 12 matches in a dropdown. */
export default function TeamSearch({
  onSelect, placeholder, value,
}: TeamSearchProps) {
  const filters = useFilters()
  // Transient typing buffer — see PlayerSearch for the full rationale.
  const [typing, setTyping] = useState<string | null>(null)
  const [results, setResults] = useState<TeamInfo[]>([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const displayValue = typing ?? value ?? ''

  useEffect(() => {
    if (typing === null || typing.length < 2) {
      setResults([]); setOpen(false); return
    }
    // cancelled flag protects against stale-fetch setState after
    // unmount or rapid re-typing — same rationale as PlayerSearch.
    let cancelled = false
    const t = setTimeout(() => {
      getTeams({ ...filters, q: typing })
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
  }, [typing, filters.gender, filters.team_type])

  useEffect(() => {
    const click = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', click)
    return () => document.removeEventListener('mousedown', click)
  }, [])

  const pick = (name: string) => {
    onSelect(name)
    setTyping(null)
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="wisden-playersearch">
      <input
        type="text"
        className="wisden-playersearch-input"
        placeholder={placeholder ?? 'Search team…'}
        value={displayValue}
        onChange={e => setTyping(e.target.value)}
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
