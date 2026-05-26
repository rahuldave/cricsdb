/**
 * PlayerOpponentFilter — the player-page "Versus" widget.
 *
 * A typeahead/dropdown over the teams THIS player has actually faced
 * (from /players/{id}/opponents). Picking one sets `filter_opponent`,
 * scoping the whole page to "this player vs that team" — e.g. Kohli vs
 * Australia, or Ashwin vs RCB across every franchise he's played for.
 * It's the first opponent-only entry point on a player (the rivalry
 * pair sets the team too); see internal_docs/audit-aux-params.md §D.
 *
 * The opponent menu is bounded and small (~tens of teams), so it's
 * fetched once at scope and filtered client-side as the user types —
 * unlike the FilterBar VenueSearch/TeamSearch which hit the server per
 * keystroke. When `filter_team` is pinned the menu shrinks server-side
 * to the opponents faced during that spell (Kohli@RCB → IPL only).
 *
 * Two modes, mirroring VenueSearch:
 *   - no opponent selected → "Versus [ vs any team ▾ ]" typeahead;
 *   - opponent selected     → "Versus [ <opp> × Clear ]" chip.
 * Renders nothing until a player has faced ≥ 1 opponent at scope.
 *
 * Caveat (known, tracked in audit §E): the player's OWN numbers narrow
 * by filter_opponent, but the "typical player" comparison baseline does
 * not yet — that's the precomputed-cohort live-fallback fix.
 */

import { useState, useEffect, useRef } from 'react'
import { useFetch } from '../../hooks/useFetch'
import { useFilterDeps } from '../../hooks/useFilterDeps'
import { useSetUrlParams } from '../../hooks/useUrlState'
import { getPlayerOpponents } from '../../api'
import type { FilterParams, PlayerOpponentTotals } from '../../types'

interface Props {
  playerId: string
  filters: FilterParams
}

export default function PlayerOpponentFilter({ playerId, filters }: Props) {
  const setUrlParams = useSetUrlParams()
  const filterDeps = [playerId, ...useFilterDeps()]
  const fetchState = useFetch<{ opponents: PlayerOpponentTotals[] } | null>(
    () => getPlayerOpponents(playerId, filters),
    filterDeps,
  )
  const opponents = fetchState.data?.opponents ?? []

  const [typing, setTyping] = useState('')
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Click-outside closes the dropdown — same pattern as VenueSearch.
  useEffect(() => {
    const click = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', click)
    return () => document.removeEventListener('mousedown', click)
  }, [])

  const current = filters.filter_opponent ?? ''

  const pick = (name: string) => {
    setUrlParams({ filter_opponent: name })
    setTyping('')
    setOpen(false)
  }
  const clear = () => setUrlParams({ filter_opponent: '' })

  // Nothing to offer (no player faced, loading first paint) and no
  // active selection → render nothing rather than an empty control.
  if (!current && opponents.length === 0) return null

  // Chip mode — an opponent is already selected.
  if (current) {
    return (
      <div className="wisden-vsteam">
        <span className="wisden-filter-label">Versus</span>
        <div className="wisden-venue-chip" title={`Versus: ${current}`}>
          <span className="wisden-venue-chip-name">{current}</span>
          <button
            type="button"
            className="wisden-venue-chip-clear"
            onClick={clear}
            aria-label="Clear opponent filter"
          >
            × Clear
          </button>
        </div>
      </div>
    )
  }

  // Typeahead mode — filter the bounded menu client-side.
  const q = typing.trim().toLowerCase()
  const shown = (q ? opponents.filter(o => o.opponent.toLowerCase().includes(q)) : opponents)

  return (
    <div className="wisden-vsteam" ref={containerRef}>
      <span className="wisden-filter-label">Versus</span>
      <div className="wisden-playersearch wisden-vsteam-search">
        <input
          type="text"
          className="wisden-playersearch-input"
          placeholder="vs any team…"
          value={typing}
          onChange={e => { setTyping(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
        />
        {open && shown.length > 0 && (
          <ul className="wisden-playersearch-list">
            {shown.map(o => (
              <li key={o.opponent} onMouseDown={() => pick(o.opponent)}>
                <span className="wisden-playersearch-name">{o.opponent}</span>
                <span className="wisden-playersearch-meta">
                  {o.matches} {o.matches === 1 ? 'match' : 'matches'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
