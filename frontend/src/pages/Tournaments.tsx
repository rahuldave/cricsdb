import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import TournamentDossier from '../components/tournaments/TournamentDossier'

/** /series — match-set dossier at every scope.
 *
 *  TournamentDossier is the single entry point. It handles three subjects:
 *    - tournament-set                          → single-tournament dossier
 *    - rivalry pair set                        → rivalry dossier
 *    - neither (broad scope, e.g. men's club)  → above-tournament "tier"
 *      dossier driven purely by FilterBar narrowings
 *
 *  Editions is the only tab gated on isSingleTournament; every other tab
 *  works at any scope. The Overview tab adds Champions / Top teams /
 *  TournamentsLanding-as-section when tournament=null.
 *
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
    setUrlParams(updates, { replace: true })
  }, [rivalry])

  return (
    <TournamentDossier
      tournament={tournament || null}
      filterTeam={filterTeam || null}
      filterOpponent={filterOpp || null}
    />
  )
}
