/**
 * DevTossFilter — unlisted dev/test surface for the TossFilter control.
 *
 * Not linked anywhere in the nav. It exists so the spec §6.1 "throwaway
 * surface" test (tests/integration/toss_filter.sh) can render the toss
 * control, click its pills, and reconcile the counts against SQL — while
 * the control's real mount surface stays TBD (built now, mounted later
 * per spec-player-baseline-aux-fallback.md, decision D2).
 *
 * Reads ?player= + the usual FilterBar params, fetches the player's
 * result-counts (which now carries toss_won / toss_lost), and feeds them
 * to TossFilter. No styling beyond the shared widget; this is plumbing.
 */
import { useFilters } from '../hooks/useFilters'
import { useFilterDeps } from '../hooks/useFilterDeps'
import { useUrlParam } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { getPlayerResultCounts } from '../api'
import TossFilter from '../components/TossFilter'

export default function DevTossFilter() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const filterDeps = [playerId, ...useFilterDeps()]
  const fetchState = useFetch<{
    matches: number; toss_won: number; toss_lost: number
  } | null>(
    () => (playerId ? getPlayerResultCounts(playerId, filters) : Promise.resolve(null)),
    filterDeps,
  )
  const c = fetchState.data
  return (
    <div className="max-w-6xl mx-auto">
      <h2 style={{ fontFamily: 'var(--serif)', margin: '1rem 0' }}>
        Dev · TossFilter test surface
      </h2>
      <p style={{ color: 'var(--ink-faint)', marginBottom: '1rem' }}>
        Unlisted. Pass <code>?player=&lt;id&gt;&amp;gender=male</code>. Counts come
        from <code>/players/{'{id}'}/result-counts</code>.
      </p>
      {c && <TossFilter matches={c.matches} won={c.toss_won} lost={c.toss_lost} />}
    </div>
  )
}
