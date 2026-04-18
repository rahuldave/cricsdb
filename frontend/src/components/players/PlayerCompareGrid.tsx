import { Link } from 'react-router-dom'
import FlagBadge from '../FlagBadge'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import ScopeIndicator from '../ScopeIndicator'
import PlayerSummaryRow, { disciplineHasData } from './PlayerSummaryRow'
import { classifyRole, matchesInScope, carryFilters } from './roleUtils'
import { useFetch, type FetchState } from '../../hooks/useFetch'
import { useSetUrlParams } from '../../hooks/useUrlState'
import { getPlayerProfile } from '../../api'
import type {
  PlayerProfile as PlayerProfileT, FilterParams,
} from '../../types'

interface Props {
  ids: string[]          // [primary, ...compareIds] length 2 or 3
  filters: FilterParams
}

type Discipline = 'batting' | 'bowling' | 'fielding' | 'keeping'
const DISCIPLINES: Discipline[] = ['batting', 'bowling', 'fielding', 'keeping']

export default function PlayerCompareGrid({ ids, filters }: Props) {
  const setUrlParams = useSetUrlParams()

  const filterDeps = [
    filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_team, filters.filter_opponent,
    filters.filter_venue,
  ]

  // Fixed-arity slots (primary + up to 2 compares) so React sees the
  // same number of useFetch calls every render. Empty slots resolve
  // to null and are skipped at render.
  const primaryId  = ids[0] ?? ''
  const compareId1 = ids[1] ?? ''
  const compareId2 = ids[2] ?? ''
  const primaryFetch = useFetch<PlayerProfileT | null>(
    () => primaryId ? getPlayerProfile(primaryId, filters) : Promise.resolve(null),
    [primaryId, ...filterDeps],
  )
  const compare1Fetch = useFetch<PlayerProfileT | null>(
    () => compareId1 ? getPlayerProfile(compareId1, filters) : Promise.resolve(null),
    [compareId1, ...filterDeps],
  )
  const compare2Fetch = useFetch<PlayerProfileT | null>(
    () => compareId2 ? getPlayerProfile(compareId2, filters) : Promise.resolve(null),
    [compareId2, ...filterDeps],
  )
  const fetches: FetchState<PlayerProfileT | null>[] =
    [primaryFetch, compare1Fetch, compare2Fetch].slice(0, ids.length)

  const anyLoading = fetches.some(f => f.loading && !f.data)
  const firstError = fetches.find(f => f.error)

  const removeAt = (idx: number) => {
    if (idx === 0) {
      // Removing primary clears compare too — back to landing.
      setUrlParams({ player: '', compare: '' })
      return
    }
    const compareIds = ids.slice(1).filter((_, i) => i + 1 !== idx)
    setUrlParams({ compare: compareIds.join(',') })
  }

  // Which disciplines have ANY column with data — drives band
  // visibility. Columns whose own profile lacks that discipline
  // render a placeholder (keeps rows vertically aligned).
  const anyHasData: Record<Discipline, boolean> = {
    batting:  false, bowling: false, fielding: false, keeping: false,
  }
  for (const f of fetches) {
    if (!f.data) continue
    for (const d of DISCIPLINES) {
      if (disciplineHasData(d, f.data)) anyHasData[d] = true
    }
  }

  return (
    <div>
      <ScopeIndicator filters={filters} />

      <div
        className="wisden-compare-columns"
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${ids.length}, minmax(0, 1fr))`,
          gap: '1.5rem',
          alignItems: 'start',
        }}
      >
        {ids.map((id, idx) => (
          <CompareColumn
            key={id}
            id={id}
            fetch={fetches[idx]}
            isPrimary={idx === 0}
            onRemove={() => removeAt(idx)}
            anyHasData={anyHasData}
            filters={filters}
          />
        ))}
      </div>

      {anyLoading && !fetches.every(f => f.data) && (
        <Spinner label="Loading profiles…" />
      )}
      {firstError && !anyLoading && (
        <ErrorBanner
          message={`Could not load one of the players: ${firstError.error}`}
          onRetry={firstError.refetch}
        />
      )}
    </div>
  )
}

// ─── one column ─────────────────────────────────────────────────────

interface ColumnProps {
  id: string
  fetch: FetchState<PlayerProfileT | null>
  isPrimary: boolean
  onRemove: () => void
  anyHasData: Record<Discipline, boolean>
  filters: FilterParams
}

function CompareColumn({
  id, fetch, isPrimary, onRemove, anyHasData, filters,
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

  const identity = profile.batting ?? profile.bowling ?? profile.fielding
  const name = identity?.name ?? id
  const nationalities = identity?.nationalities ?? []
  const role = classifyRole(profile)
  const matches = matchesInScope(profile)

  const deepLinkQs = new URLSearchParams({
    player: id, ...carryFilters(filters),
  })
  const soloLink = `/players?${deepLinkQs}`

  return (
    <div className="wisden-compare-col">
      <div className="wisden-compare-col-head">
        <h2 className="wisden-compare-col-name">
          {nationalities.length > 0 && (
            <span style={{ marginRight: '0.35rem' }}>
              {nationalities.map(n => (
                <FlagBadge key={`${n.team}-${n.gender}`} team={n.team} gender={n.gender} size="sm" />
              ))}
            </span>
          )}
          <Link to={soloLink} className="wisden-compare-col-namelink">{name}</Link>
        </h2>
        <button
          type="button"
          className="wisden-compare-col-remove"
          onClick={onRemove}
          aria-label={isPrimary ? 'Clear comparison' : `Remove ${name}`}
          title={isPrimary ? 'Clear comparison — return to single view' : `Remove ${name}`}
        >
          ✕
        </button>
      </div>
      <div className="wisden-player-identity">
        <em>{role}</em>
        {matches > 0 && <> · <span className="num">{matches}</span> matches</>}
      </div>

      {DISCIPLINES.map(d => {
        if (!anyHasData[d]) return null
        const has = disciplineHasData(d, profile)
        return (
          <PlayerSummaryRow
            key={d}
            discipline={d}
            profile={profile}
            playerId={id}
            filters={filters}
            placeholder={!has}
            compact
          />
        )
      })}
    </div>
  )
}
