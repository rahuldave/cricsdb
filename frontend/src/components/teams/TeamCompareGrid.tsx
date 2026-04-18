import { Link } from 'react-router-dom'
import FlagBadge from '../FlagBadge'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import ScopeIndicator from '../ScopeIndicator'
import TeamSummaryRow from './TeamSummaryRow'
import {
  teamDisciplineHasData, teamMatchesInScope, carryTeamFilters,
  type TeamDiscipline,
} from './teamUtils'
import { useFetch, type FetchState } from '../../hooks/useFetch'
import { useSetUrlParams } from '../../hooks/useUrlState'
import { getTeamProfile } from '../../api'
import type { TeamProfile, FilterParams } from '../../types'

interface Props {
  /** [primary, ...compareTeams] length 2 or 3. Single-column (length
   *  1) is also supported — used on the Compare tab before the user
   *  has added any compare. */
  teams: string[]
  filters: FilterParams
}

const DISCIPLINES: TeamDiscipline[] = [
  'results', 'batting', 'bowling', 'fielding', 'partnerships',
]

export default function TeamCompareGrid({ teams, filters }: Props) {
  const setUrlParams = useSetUrlParams()

  const filterDeps = [
    filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_venue,
  ]

  // Fixed-arity slots so React sees the same number of useFetch calls
  // across renders. Empty slots resolve to null and are skipped at
  // render time. Mirrors PlayerCompareGrid.
  const t0 = teams[0] ?? ''
  const t1 = teams[1] ?? ''
  const t2 = teams[2] ?? ''
  const f0 = useFetch<TeamProfile | null>(
    () => t0 ? getTeamProfile(t0, filters) : Promise.resolve(null),
    [t0, ...filterDeps],
  )
  const f1 = useFetch<TeamProfile | null>(
    () => t1 ? getTeamProfile(t1, filters) : Promise.resolve(null),
    [t1, ...filterDeps],
  )
  const f2 = useFetch<TeamProfile | null>(
    () => t2 ? getTeamProfile(t2, filters) : Promise.resolve(null),
    [t2, ...filterDeps],
  )
  const fetches: FetchState<TeamProfile | null>[] =
    [f0, f1, f2].slice(0, teams.length)

  const anyLoading = fetches.some(f => f.loading && !f.data)
  const firstError = fetches.find(f => f.error)

  const removeAt = (idx: number) => {
    if (idx === 0) {
      // Removing primary clears compare AND drops the tab param so the
      // landing doesn't render under a stale `tab=Compare` URL residue.
      setUrlParams({ team: '', compare: '', tab: '' })
      return
    }
    const compares = teams.slice(1).filter((_, i) => i + 1 !== idx)
    setUrlParams({ compare: compares.join(',') })
  }

  // Which disciplines have ANY column with data in scope — drives
  // row visibility. Columns lacking that discipline render a dim
  // placeholder so every row stays vertically aligned across columns.
  const anyHasData: Record<TeamDiscipline, boolean> = {
    results: false, batting: false, bowling: false, fielding: false, partnerships: false,
  }
  for (const f of fetches) {
    if (!f.data) continue
    for (const d of DISCIPLINES) {
      if (teamDisciplineHasData(d, f.data)) anyHasData[d] = true
    }
  }

  return (
    <div>
      <ScopeIndicator filters={filters} />

      <div
        className="wisden-compare-columns"
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${teams.length}, minmax(0, 1fr))`,
          gap: '1.5rem',
          alignItems: 'start',
        }}
      >
        {teams.map((name, idx) => (
          <CompareColumn
            key={name}
            team={name}
            fetch={fetches[idx]}
            isPrimary={idx === 0}
            onRemove={() => removeAt(idx)}
            anyHasData={anyHasData}
            filters={filters}
          />
        ))}
      </div>

      {anyLoading && !fetches.every(f => f.data) && (
        <Spinner label="Loading teams…" />
      )}
      {firstError && !anyLoading && (
        <ErrorBanner
          message={`Could not load one of the teams: ${firstError.error}`}
          onRetry={firstError.refetch}
        />
      )}
    </div>
  )
}

// ─── one column ─────────────────────────────────────────────────────

interface ColumnProps {
  team: string
  fetch: FetchState<TeamProfile | null>
  isPrimary: boolean
  onRemove: () => void
  anyHasData: Record<TeamDiscipline, boolean>
  filters: FilterParams
}

function CompareColumn({
  team, fetch, isPrimary, onRemove, anyHasData, filters,
}: ColumnProps) {
  const profile = fetch.data

  if (fetch.loading && !profile) {
    return <div className="wisden-compare-col"><Spinner label="…" /></div>
  }
  if (!profile) {
    return (
      <div className="wisden-compare-col">
        <div className="wisden-empty">No data.</div>
      </div>
    )
  }

  const matches = teamMatchesInScope(profile)
  // FlagBadge returns null for unmappable club sides so this line
  // naturally degrades for franchise teams — no extra guard needed.
  const gender = filters.gender || null

  const qs = new URLSearchParams({ team, ...carryTeamFilters(filters) })
  const soloLink = `/teams?${qs}`

  return (
    <div className="wisden-compare-col">
      <div className="wisden-compare-col-head">
        <h2 className="wisden-compare-col-name">
          <span style={{ marginRight: '0.35rem' }}>
            <FlagBadge team={team} gender={gender} size="sm" />
          </span>
          <Link to={soloLink} className="wisden-compare-col-namelink">{team}</Link>
        </h2>
        <button
          type="button"
          className="wisden-compare-col-remove"
          onClick={onRemove}
          aria-label={isPrimary ? 'Clear comparison' : `Remove ${team}`}
          title={isPrimary ? 'Clear comparison — back to landing' : `Remove ${team}`}
        >
          ✕
        </button>
      </div>
      <div className="wisden-player-identity">
        {matches > 0 && <><span className="num">{matches}</span> matches</>}
        {matches === 0 && <em>no matches in scope</em>}
      </div>

      {DISCIPLINES.map(d => {
        if (!anyHasData[d]) return null
        const has = teamDisciplineHasData(d, profile)
        return (
          <TeamSummaryRow
            key={d}
            discipline={d}
            profile={profile}
            team={team}
            filters={filters}
            placeholder={!has}
          />
        )
      })}
    </div>
  )
}
