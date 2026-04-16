import { useSetUrlParams } from '../hooks/useUrlState'
import type { FilterParams } from '../types'

/**
 * Pill shown under the player-page title when filter_team / filter_opponent
 * are active. Without it, a cold-clicked context link (`/fielding?player=X
 * &filter_team=Mumbai+Indians`) renders smaller-than-career numbers with no
 * on-page explanation of why.
 *
 * `clear` removes just the lens params, leaves player / gender / tournament /
 * season alone so the page stays anchored on the same player.
 */
export default function ScopeIndicator({ filters }: { filters: FilterParams }) {
  const setUrlParams = useSetUrlParams()
  const { filter_team, filter_opponent } = filters
  if (!filter_team && !filter_opponent) return null

  let prose: string
  if (filter_team && filter_opponent) {
    prose = `Scoped to ${filter_team} vs ${filter_opponent}`
  } else if (filter_team) {
    prose = `Scoped to matches at ${filter_team}`
  } else {
    prose = `Scoped to matches vs ${filter_opponent}`
  }

  return (
    <div className="wisden-scope">
      <span className="wisden-scope-text">{prose}</span>
      <button
        type="button"
        className="wisden-scope-clear"
        onClick={() => setUrlParams({ filter_team: '', filter_opponent: '' })}
        aria-label="Clear scope"
      >
        clear
      </button>
    </div>
  )
}
