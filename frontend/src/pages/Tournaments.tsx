import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import TournamentsLanding from '../components/tournaments/TournamentsLanding'
import TournamentDossier from '../components/tournaments/TournamentDossier'

/** Render mode for the /series route.
 *
 *  Three URL shapes drive the mode:
 *    - no params                              → landing
 *    - ?tournament=X (and/or filter_team+opp) → match-set dossier
 *    - ?filter_team=A&filter_opponent=B       → match-set dossier (rivalry)
 *  Legacy `?rivalry=A,B` URLs redirect to filter_team+filter_opponent.
 */
export default function Tournaments() {
  const [tournament] = useUrlParam('tournament')
  const [filterTeam] = useUrlParam('filter_team')
  const [filterOpp] = useUrlParam('filter_opponent')
  const [rivalry] = useUrlParam('rivalry')
  const [searchParams] = useSearchParams()
  const setUrlParams = useSetUrlParams()

  // Legacy redirect: ?rivalry=A,B → ?filter_team=A&filter_opponent=B&series_type=all
  useEffect(() => {
    if (!rivalry) return
    const [a, b] = rivalry.split(',', 2).map(s => s.trim())
    if (!a || !b) return
    const updates: Record<string, string> = {
      rivalry: '',
      filter_team: a,
      filter_opponent: b,
    }
    if (!searchParams.get('series_type')) updates.series_type = 'all'
    // URL-shape migration → replace so the back button returns to
    // wherever the user came from, not to the old `?rivalry=…` URL.
    setUrlParams(updates, { replace: true })
  }, [rivalry])

  const isDossier = !!(tournament || (filterTeam && filterOpp))
  useDocumentTitle(isDossier ? null : 'Series')

  if (isDossier) {
    return (
      <TournamentDossier
        tournament={tournament || null}
        filterTeam={filterTeam || null}
        filterOpponent={filterOpp || null}
      />
    )
  }

  return <TournamentsLanding />
}
