import { Link } from 'react-router-dom'
import FlagBadge from '../FlagBadge'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import ScopeIndicator from '../ScopeIndicator'
import TeamSummaryRow from './TeamSummaryRow'
import AvgSummaryRow from './AvgSummaryRow'
import PhaseBandsRow from './PhaseBandsRow'
import PartnershipByWicketRows from './PartnershipByWicketRows'
import SeasonTrajectoryStrip from './SeasonTrajectoryStrip'
import {
  teamDisciplineHasData, teamMatchesInScope, carryTeamFilters,
  avgDisciplineHasData, scopeAvgLabel,
  type TeamDiscipline,
} from './teamUtils'
import { useFetch, type FetchState } from '../../hooks/useFetch'
import { useSetUrlParams, useUrlParam } from '../../hooks/useUrlState'
import { getTeamProfile, getScopeAverageProfile } from '../../api'
import type { TeamProfile, ScopeAverageProfile, FilterParams } from '../../types'

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
  const [avgSlotParam] = useUrlParam('avg_slot')
  const avgSlot = avgSlotParam === '1'

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
  const fAvg = useFetch<ScopeAverageProfile | null>(
    () => avgSlot ? getScopeAverageProfile(filters) : Promise.resolve(null),
    [avgSlot, ...filterDeps],
  )
  const fetches: FetchState<TeamProfile | null>[] =
    [f0, f1, f2].slice(0, teams.length)

  const anyLoading = fetches.some(f => f.loading && !f.data) || (avgSlot && fAvg.loading && !fAvg.data)
  const firstError = fetches.find(f => f.error) ?? (avgSlot ? (fAvg.error ? fAvg : undefined) : undefined)

  const removeAt = (idx: number) => {
    if (idx === 0) {
      // Removing primary clears compare AND drops the tab param so the
      // landing doesn't render under a stale `tab=Compare` URL residue.
      setUrlParams({ team: '', compare: '', tab: '', avg_slot: '' })
      return
    }
    const compares = teams.slice(1).filter((_, i) => i + 1 !== idx)
    setUrlParams({ compare: compares.join(',') })
  }

  const removeAvgSlot = () => setUrlParams({ avg_slot: '' })

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
  if (avgSlot && fAvg.data) {
    for (const d of DISCIPLINES) {
      if (avgDisciplineHasData(d, fAvg.data)) anyHasData[d] = true
    }
  }

  const totalColumns = teams.length + (avgSlot ? 1 : 0)
  const avgLabel = scopeAvgLabel(filters)

  return (
    <div>
      <ScopeIndicator filters={filters} />

      <div
        className="wisden-compare-legend"
        style={{
          fontSize: '0.85em',
          opacity: 0.65,
          fontStyle: 'italic',
          marginBottom: '0.75rem',
        }}
        title="Compact substats appear after the primary number on phase + partnership-by-wicket rows."
      >
        Substats: <strong>b</strong> = boundary % · <strong>d</strong> = dot % ·
        <strong> w</strong> = wickets ·
        <strong> n</strong> = partnerships in scope ·
        <strong> hi</strong> = highest single partnership
      </div>

      <div
        className="wisden-compare-columns"
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${totalColumns}, minmax(0, 1fr))`,
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
        {avgSlot && (
          <AvgCompareColumn
            key="__avg__"
            label={avgLabel}
            fetch={fAvg}
            anyHasData={anyHasData}
            onRemove={removeAvgSlot}
          />
        )}
      </div>

      {anyLoading && !fetches.every(f => f.data) && (
        <Spinner label="Loading teams…" />
      )}
      {firstError && !anyLoading && (
        <ErrorBanner
          message={`Could not load one of the columns: ${firstError.error}`}
          onRetry={firstError.refetch}
        />
      )}

      <SeasonTrajectoryStrip
        columns={[
          ...teams.map((name, idx) => ({
            label: name,
            profile: fetches[idx]?.data,
            isAverage: false,
          })).filter((c): c is { label: string; profile: TeamProfile; isAverage: boolean } => !!c.profile),
          ...(avgSlot && fAvg.data
            ? [{ label: avgLabel, profile: fAvg.data, isAverage: true }]
            : []),
        ]}
      />
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
          <div key={d}>
            <TeamSummaryRow
              discipline={d}
              profile={profile}
              team={team}
              filters={filters}
              placeholder={!has}
            />
            {(d === 'batting' || d === 'bowling') && (
              <PhaseBandsRow profile={profile} discipline={d} placeholder={!has} />
            )}
            {d === 'partnerships' && (
              <PartnershipByWicketRows profile={profile} placeholder={!has} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── league-average column ──────────────────────────────────────────

interface AvgColumnProps {
  label: string
  fetch: FetchState<ScopeAverageProfile | null>
  anyHasData: Record<TeamDiscipline, boolean>
  onRemove: () => void
}

function AvgCompareColumn({
  label, fetch, anyHasData, onRemove,
}: AvgColumnProps) {
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

  const matches = profile.summary?.matches ?? 0

  return (
    <div className="wisden-compare-col">
      <div className="wisden-compare-col-head">
        <h2 className="wisden-compare-col-name">
          {/* FlagBadge null-render: no flag for the league average. */}
          <span
            className="wisden-compare-col-namelink"
            title="Pool-weighted league baseline scoped to the active filters"
            style={{ fontStyle: 'italic' }}
          >
            {label}
          </span>
        </h2>
        <button
          type="button"
          className="wisden-compare-col-remove"
          onClick={onRemove}
          aria-label="Remove league average"
          title="Remove league average column"
        >
          ✕
        </button>
      </div>
      <div className="wisden-player-identity">
        {matches > 0 && <><span className="num">{matches}</span> matches in scope</>}
        {matches === 0 && <em>no matches in scope</em>}
      </div>

      {DISCIPLINES.map(d => {
        if (!anyHasData[d]) return null
        const has = avgDisciplineHasData(d, profile)
        return (
          <div key={d}>
            <AvgSummaryRow
              discipline={d}
              profile={profile}
              placeholder={!has}
            />
            {(d === 'batting' || d === 'bowling') && (
              <PhaseBandsRow profile={profile} discipline={d} placeholder={!has} />
            )}
            {d === 'partnerships' && (
              <PartnershipByWicketRows
                profile={profile}
                isAverage
                placeholder={!has}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
