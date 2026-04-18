import { useEffect } from 'react'
import { useFilters } from '../components/FilterBar'
import VenuesLandingBoard from '../components/venues/VenuesLanding'
import VenueDossier from '../components/venues/VenueDossier'
import { ScopeContext } from '../components/scopeLinks'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'

/**
 * /venues — country-grouped directory (landing) OR per-venue dossier.
 *
 * Mode flip is driven by the `?venue=` query param:
 *   /venues                       → VenuesLandingBoard
 *   /venues?venue=<canonical>     → VenueDossier
 *
 * Elsewhere in the app the FilterBar's VenueSearch typeahead sets
 * `filter_venue` — an ambient filter that narrows every other tab's
 * stats. On this tab that behavior would be redundant (the landing
 * strips filter_venue self-referentially, and we have a dedicated
 * dossier URL), so an effect below promotes any incoming
 * `filter_venue` to `?venue=` and clears the ambient — turning the
 * FilterBar pick into a shortcut that opens the dossier, matching
 * what a landing-tile click does.
 */
export default function Venues() {
  const filters = useFilters()
  const [venue] = useUrlParam('venue', '')
  const setUrlParams = useSetUrlParams()
  useDocumentTitle(venue || 'Venues')

  useEffect(() => {
    if (filters.filter_venue) {
      setUrlParams(
        { venue: filters.filter_venue, filter_venue: '' },
        { replace: true },
      )
    }
  }, [filters.filter_venue, setUrlParams])

  const filterDeps = [
    filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_team, filters.filter_opponent,
  ]

  if (venue) {
    // Promote the `venue=X` path identity → filter_venue pinning so
    // every PlayerLink / TeamLink inside the dossier carries "at <venue>"
    // through its letter links.
    return (
      <div className="wisden-page">
        <ScopeContext.Provider value={{ filter_venue: venue }}>
          <VenueDossier venue={venue} />
        </ScopeContext.Provider>
      </div>
    )
  }

  return (
    <div className="wisden-page">
      <h1 className="wisden-page-title">Venues</h1>
      <VenuesLandingBoard filters={filters} filterDeps={filterDeps} />
    </div>
  )
}
