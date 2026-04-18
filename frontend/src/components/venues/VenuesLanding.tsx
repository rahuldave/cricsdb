import { useMemo, useState } from 'react'
import type { FilterParams, VenuesLanding, VenueCountryGroup } from '../../types'
import { getVenuesLanding } from '../../api'
import { useFetch } from '../../hooks/useFetch'
import { useSetUrlParams } from '../../hooks/useUrlState'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'

interface Props {
  filters: FilterParams
  filterDeps: unknown[]
}

/**
 * Country-grouped venue directory. Top-3 countries by match count are
 * open by default; the rest collapse so a long tail (80+ associate
 * nations) doesn't swamp the page. Tile click opens the per-venue
 * dossier in-place via `?venue=<canonical>` — Venues.tsx switches
 * landing ↔ dossier on the same page.
 *
 * Inline **search** input does a client-side substring match on venue
 * name + city against the full 456-row landing payload (one-shot
 * fetch, no extra round-trip per keystroke). When the query is
 * non-empty, countries without any matching venue drop out and every
 * surviving country is force-expanded. The FilterBar's Venue typeahead
 * is NOT the right tool for this tab — it selects a single venue and
 * Venues.tsx now promotes that pick to the dossier URL. This search
 * is the tab-local analogue for "show me everything matching 'mumbai'".
 */
export default function VenuesLandingBoard({ filters, filterDeps }: Props) {
  const fetch = useFetch<VenuesLanding | null>(
    () => getVenuesLanding(filters),
    filterDeps,
  )
  const setUrlParams = useSetUrlParams()
  const [query, setQuery] = useState('')

  const filtered: VenueCountryGroup[] = useMemo(() => {
    if (!fetch.data) return []
    const q = query.trim().toLowerCase()
    if (!q) return fetch.data.by_country
    const out: VenueCountryGroup[] = []
    for (const g of fetch.data.by_country) {
      const venues = g.venues.filter(v =>
        v.venue.toLowerCase().includes(q)
        || (v.city ?? '').toLowerCase().includes(q),
      )
      if (venues.length === 0) continue
      const matches = venues.reduce((a, v) => a + v.matches, 0)
      out.push({ ...g, venues, matches })
    }
    return out
  }, [fetch.data, query])

  const defaultOpen = useMemo(() => {
    if (!fetch.data) return new Set<string>()
    return new Set(fetch.data.by_country.slice(0, 3).map(g => g.country))
  }, [fetch.data])

  if (fetch.loading && !fetch.data) return <Spinner label="Loading venues…" />
  if (fetch.error) {
    return (
      <ErrorBanner
        message={`Could not load venues: ${fetch.error}`}
        onRetry={fetch.refetch}
      />
    )
  }
  const data = fetch.data
  if (!data || data.by_country.length === 0) {
    return <div className="wisden-empty">No venues match the current filters.</div>
  }

  const pick = (venueName: string) => {
    // Opens the Phase-3 dossier via the `venue=` param. The ambient
    // filter_venue is intentionally NOT set — the dossier pins its
    // venue by URL param, and leaving filter_venue unset means
    // navigating away from /venues returns the user to a clean filter
    // scope rather than carrying this venue into every other tab.
    setUrlParams({ venue: venueName })
  }

  const hasQuery = query.trim().length > 0

  return (
    <div>
      <div className="wisden-tab-help" style={{ marginBottom: '0.75rem' }}>
        Pick a venue to open its dossier. Counts respect every filter
        at the top (gender, type, tournament, season). Type below to
        narrow to venues whose name or city matches — e.g. "mumbai"
        reveals Wankhede, Brabourne, DY Patil, … in one sweep.
      </div>
      <div style={{ marginBottom: '1rem', maxWidth: '28rem' }}>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by venue or city…"
          className="wisden-input"
          style={{ width: '100%' }}
          aria-label="Filter venues and cities"
        />
      </div>
      {hasQuery && filtered.length === 0 && (
        <div className="wisden-empty">
          No venues match "{query}".
        </div>
      )}
      <div className="flex flex-col gap-3">
        {filtered.map(group => (
          <details
            // Key changes when query flips between "" and non-empty so
            // <details open=…> re-renders its initial state (browsers
            // treat `open` as an initial prop after user-toggle).
            key={`${group.country}|${hasQuery ? 'q' : 'default'}`}
            open={hasQuery || defaultOpen.has(group.country)}
            className="wisden-collapse"
          >
            <summary>
              <span className="wisden-collapse-title">{group.country}</span>
              <span className="wisden-collapse-count num">{group.matches}</span>
            </summary>
            <div className="wisden-collapse-body">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1">
                {group.venues.map(v => (
                  <button
                    key={`${v.venue}|${v.city ?? ''}`}
                    onClick={() => pick(v.venue)}
                    className="comp-link"
                    style={{
                      background: 'none', border: 0, padding: '0.2rem 0',
                      cursor: 'pointer', textAlign: 'left', font: 'inherit',
                    }}
                  >
                    {v.venue}
                    {v.city && v.city !== v.venue && (
                      <span className="wisden-tile-faint" style={{ fontSize: '0.82em' }}>
                        {' · '}{v.city}
                      </span>
                    )}
                    {' '}
                    <span className="num" style={{ color: 'var(--ink-faint)', fontSize: '0.85em' }}>
                      ({v.matches})
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </details>
        ))}
      </div>
    </div>
  )
}
