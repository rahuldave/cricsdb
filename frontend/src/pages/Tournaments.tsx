import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import TournamentDossier from '../components/tournaments/TournamentDossier'
import TierDossier from '../components/tournaments/TierDossier'

/** /series — single URL for every match-set scope.
 *
 *  Three render shapes:
 *    - ?tournament=X (and/or filter_team+opp) → TournamentDossier
 *      (single-tournament or rivalry, existing /series/summary path).
 *    - ?filter_team=A&filter_opponent=B       → TournamentDossier (rivalry).
 *    - neither set                             → TierDossier — above-
 *      tournament "men's club cricket" / "women's international" etc.
 *      dossier driven purely by FilterBar narrowings, using the lean
 *      /league/* composite endpoints.
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

  const isTournamentMode = !!(tournament || (filterTeam && filterOpp))
  useDocumentTitle(isTournamentMode ? null : 'Series')

  if (isTournamentMode) {
    return (
      <TournamentDossier
        tournament={tournament || null}
        filterTeam={filterTeam || null}
        filterOpponent={filterOpp || null}
      />
    )
  }
  return <TierDossier />
}
