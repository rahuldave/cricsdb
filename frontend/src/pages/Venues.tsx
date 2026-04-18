import { useFilters } from '../components/FilterBar'
import VenuesLandingBoard from '../components/venues/VenuesLanding'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

/**
 * /venues — country-grouped venue directory (Phase 2).
 *
 * There is no per-venue dossier yet (Phase 3 decision). The FilterBar's
 * VenueSearch typeahead is the way to set filter_venue and narrow
 * other tabs to a specific ground; this page answers "what grounds
 * exist?" as a flat country-grouped tile grid. Clicking a tile
 * navigates to /matches?filter_venue=X — the bare list of matches
 * played there.
 */
export default function Venues() {
  const filters = useFilters()
  useDocumentTitle('Venues')

  const filterDeps = [
    filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_team, filters.filter_opponent,
  ]

  return (
    <div className="wisden-page">
      <h1 className="wisden-page-title">Venues</h1>
      <VenuesLandingBoard filters={filters} filterDeps={filterDeps} />
    </div>
  )
}
