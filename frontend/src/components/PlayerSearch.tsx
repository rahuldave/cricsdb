import { useState, useEffect, useRef } from 'react'
import { searchPlayers } from '../api'
import type { PlayerSearchResult } from '../types'

interface PlayerSearchProps {
  /** Omit for role-agnostic search (the /players tab). When set, the
   *  server narrows results to people with ≥N innings in that role. */
  role?: 'batter' | 'bowler' | 'fielder'
  onSelect: (player: PlayerSearchResult) => void
  placeholder?: string
  /** Canonical display value — usually the URL-derived picked-player
   *  name. The input shows this when the user isn't actively typing.
   *  Omit for pickers where the input should reset after each pick
   *  (e.g. AddComparePicker). */
  value?: string
}

export default function PlayerSearch({ role, onSelect, placeholder, value }: PlayerSearchProps) {
  // Transient typing buffer. `null` = not editing; the input falls
  // through to `value` (the source of truth in the parent). Non-null
  // means the user is mid-keystroke — we show what they've typed and
  // feed it to the dropdown fetch. Resetting to `null` on pick (and on
  // parent unmount / URL back-nav via changing `value`) avoids the
  // stale-input class of bugs.
  const [typing, setTyping] = useState<string | null>(null)
  const [results, setResults] = useState<PlayerSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)

  const displayValue = typing ?? value ?? ''

  useEffect(() => {
    if (typing === null || typing.length < 2) {
      setResults([]); setOpen(false); setError(null); return
    }
    setLoading(true)
    setError(null)
    clearTimeout(timerRef.current)
    // `cancelled` guards setState after unmount OR after the effect
    // re-runs (e.g. user kept typing). Without it, an in-flight fetch
    // from a prior query could resolve into this component after it's
    // been unmounted or after the query has moved on.
    let cancelled = false
    timerRef.current = setTimeout(async () => {
      try {
        const data = await searchPlayers(typing, role)
        if (cancelled) return
        setResults(data.players)
        setOpen(true)
      } catch (err) {
        if (cancelled) return
        setResults([])
        setOpen(true)
        setError(err instanceof Error ? err.message : 'Search failed')
      }
      if (!cancelled) setLoading(false)
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(timerRef.current)
    }
  }, [typing, role])

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
        value={displayValue}
        onChange={e => setTyping(e.target.value)}
        placeholder={placeholder || (role ? `Search ${role}s…` : 'Search players…')}
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
                onSelect(p)
                setTyping(null)
                setOpen(false)
              }}
            >
              <span className="wisden-playersearch-name">{p.name}</span>
              <span className="wisden-playersearch-meta num">{p.innings} inn</span>
            </li>
          ))}
        </ul>
      )}
      {open && results.length === 0 && !loading && typing && typing.length >= 2 && !error && (
        <div className="wisden-playersearch-empty">No players found</div>
      )}
      {open && error && !loading && (
        <div className="wisden-playersearch-error">Search failed: {error}</div>
      )}
    </div>
  )
}
