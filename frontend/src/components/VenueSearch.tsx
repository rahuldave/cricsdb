import { useState, useEffect, useRef } from 'react'
import { getVenues } from '../api'
import { useFilters } from '../hooks/useFilters'
import type { VenueInfo } from '../types'

interface VenueSearchProps {
  /** Called when the user picks a venue. Parent writes the canonical
   *  name into the URL (filter_venue=...). */
  onSelect: (venueName: string) => void
  /** Called when the user clears the active venue. Parent removes
   *  filter_venue from the URL. */
  onClear: () => void
  /** The current URL-derived filter_venue, or empty. When set, the
   *  component renders a compact chip with a "× Clear venue" button
   *  instead of the typeahead input. */
  value?: string
  placeholder?: string
}

/**
 * Typeahead venue picker for the FilterBar. Mirrors TeamSearch.tsx
 * structurally (debounced typing buffer, cancellable fetches, click-
 * outside close, transient state) — see that file's comments for the
 * rationale behind each piece.
 *
 * When a venue is already selected (value is non-empty), the component
 * flips to a "chip + clear" mode: shows the canonical name and a
 * dedicated clear button. Users always know a venue filter is active
 * and can one-click remove it on any tab.
 */
export default function VenueSearch({
  onSelect, onClear, value, placeholder,
}: VenueSearchProps) {
  const filters = useFilters()
  const [typing, setTyping] = useState<string | null>(null)
  const [results, setResults] = useState<VenueInfo[]>([])
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (typing === null || typing.length < 2) {
      setResults([]); setOpen(false); return
    }
    let cancelled = false
    const t = setTimeout(() => {
      getVenues({ ...filters, q: typing })
        .then(d => {
          if (cancelled) return
          setResults(d.venues.slice(0, 12))
          setOpen(true)
        })
        .catch(() => {})
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [typing, filters.gender, filters.team_type, filters.tournament,
      filters.season_from, filters.season_to,
      filters.filter_team, filters.filter_opponent])

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

  // Chip mode — a venue is already selected.
  if (value) {
    return (
      <div className="wisden-venue-chip" title={`Venue: ${value}`}>
        <span className="wisden-venue-chip-label">Venue:</span>
        <span className="wisden-venue-chip-name">{value}</span>
        <button
          type="button"
          className="wisden-venue-chip-clear"
          onClick={onClear}
          aria-label="Clear venue filter"
        >
          × Clear venue
        </button>
      </div>
    )
  }

  // Search mode.
  return (
    <div ref={containerRef} className="wisden-playersearch wisden-venue-search">
      <input
        type="text"
        className="wisden-playersearch-input"
        placeholder={placeholder ?? 'Search venue…'}
        value={typing ?? ''}
        onChange={e => setTyping(e.target.value)}
        onFocus={() => { if (results.length > 0) setOpen(true) }}
      />
      {open && results.length > 0 && (
        <ul className="wisden-playersearch-list">
          {results.map(v => (
            <li key={`${v.venue}|${v.city ?? ''}`} onMouseDown={() => pick(v.venue)}>
              <span className="wisden-playersearch-name">{v.venue}</span>
              <span className="wisden-playersearch-meta">
                {v.city ? `${v.city} · ` : ''}{v.matches} {v.matches === 1 ? 'match' : 'matches'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
