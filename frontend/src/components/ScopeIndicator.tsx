import { useSetUrlParams } from '../hooks/useUrlState'
import type { FilterParams } from '../types'

/**
 * Pill shown under the player-page title when filter_team / filter_opponent
 * are active. Without it, a cold-clicked context link (`/fielding?player=X
 * &filter_team=Mumbai+Indians`) renders smaller-than-career numbers with no
 * on-page explanation of why.
 *
 * `clear` strips every narrowing filter down to the player's bare career
 * view (player + gender only). If the user wants the previous narrowed
 * view back, the back button walks the filter history — that's what CLEAR
 * means: "give me the full career, I'll navigate back if I want the scope
 * again." Previously clear removed only filter_team/filter_opponent and
 * left any tournament/season/team_type the user had applied on top still
 * active, which read as half a reset.
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
        onClick={() => setUrlParams({
          filter_team: '',
          filter_opponent: '',
          tournament: '',
          team_type: '',
          season_from: '',
          season_to: '',
        })}
        aria-label="Clear scope and return to full career"
      >
        clear
      </button>
    </div>
  )
}
