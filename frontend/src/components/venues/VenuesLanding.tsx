import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FilterParams, VenuesLanding } from '../../types'
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
 * nations) doesn't swamp the page. Tile click sets filter_venue and
 * navigates to /matches — the Phase 2 default drilldown. Phase 3 will
 * swap this for a per-venue dossier at /venues?venue=X.
 */
export default function VenuesLandingBoard({ filters, filterDeps }: Props) {
  const fetch = useFetch<VenuesLanding | null>(
    () => getVenuesLanding(filters),
    filterDeps,
  )
  const navigate = useNavigate()
  const setUrlParams = useSetUrlParams()

  const openCountries = useMemo(() => {
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
    // Atomic: set filter_venue, then navigate. Navigate carries the URL
    // params along so the match list inherits the scope.
    setUrlParams({ filter_venue: venueName })
    navigate(`/matches?${new URLSearchParams({ filter_venue: venueName }).toString()}`)
  }

  return (
    <div>
      <div className="wisden-tab-help" style={{ marginBottom: '1rem' }}>
        Pick a venue below, or search via the Venue box in the filter bar.
        Match counts respect every filter at the top — change gender,
        type, tournament, or season to narrow. Clicking a venue opens
        its match list.
      </div>
      <div className="flex flex-col gap-3">
        {data.by_country.map(group => (
          <details
            key={group.country}
            open={openCountries.has(group.country)}
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
