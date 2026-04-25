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
import SlotHeaderChip from './SlotHeaderChip'
import {
  teamDisciplineHasData, teamMatchesInScope, carryTeamFilters,
  avgDisciplineHasData, scopeAvgLabel,
  type TeamDiscipline,
} from './teamUtils'
import { useFetch, type FetchState } from '../../hooks/useFetch'
import { getTeamProfile, getScopeAverageProfile } from '../../api'
import type { TeamProfile, ScopeAverageProfile, FilterParams } from '../../types'
import type { SlotState, CompareSlots } from '../../hooks/useCompareSlots'

interface Props {
  primaryTeam: string
  primaryFilters: FilterParams
  slots: CompareSlots
  onClearPrimary: () => void
  onRemoveTeam: (name: string) => void
  onRemoveAvg: () => void
}

const DISCIPLINES: TeamDiscipline[] = [
  'results', 'batting', 'bowling', 'fielding', 'partnerships',
]

type AnyProfile = TeamProfile | ScopeAverageProfile
type ProfileFetch = FetchState<AnyProfile | null>

// Synthesize a primary "slot" so column 0 fits the same iteration as
// the two compare slots. Primary is always kind='team', no overrides.
function primarySlotOf(team: string, filters: FilterParams): SlotState {
  return {
    kind: 'team',
    entity: team,
    scope: {
      gender: filters.gender,
      team_type: filters.team_type,
      tournament: filters.tournament,
      season_from: filters.season_from,
      season_to: filters.season_to,
      filter_venue: filters.filter_venue,
      series_type: filters.series_type,
    },
    overrides: {},
  }
}

// Stable string fingerprint per slot so useFetch deps stay primitive
// across renders (slots is rebuilt on every URL change but its inner
// shape only differs when user actually edits scope).
function slotKey(s: SlotState | null): string {
  if (!s) return ''
  return `${s.kind}|${s.entity ?? ''}|${JSON.stringify(s.scope)}`
}

function fetchSlot(slot: SlotState | null): Promise<AnyProfile | null> {
  if (!slot) return Promise.resolve(null)
  if (slot.kind === 'avg') return getScopeAverageProfile(slot.scope)
  return getTeamProfile(slot.entity!, slot.scope)
}

function disciplineHasData(slot: SlotState, profile: AnyProfile, d: TeamDiscipline): boolean {
  if (slot.kind === 'avg') return avgDisciplineHasData(d, profile as ScopeAverageProfile)
  return teamDisciplineHasData(d, profile as TeamProfile)
}

function slotMatches(slot: SlotState, profile: AnyProfile): number {
  if (slot.kind === 'avg') return (profile as ScopeAverageProfile).summary?.matches ?? 0
  return teamMatchesInScope(profile as TeamProfile)
}

function slotLabel(slot: SlotState): string {
  if (slot.kind === 'avg') return scopeAvgLabel(slot.scope)
  return slot.entity ?? ''
}

export default function TeamCompareGrid({
  primaryTeam, primaryFilters, slots,
  onClearPrimary, onRemoveTeam, onRemoveAvg,
}: Props) {
  const primary = primarySlotOf(primaryTeam, primaryFilters)
  const slot1 = slots.slot1
  const slot2 = slots.slot2

  // Fixed-arity useFetch calls: one per slot. Discriminate kind inside
  // the fetcher so the same hook position serves both team and avg.
  const f0 = useFetch<AnyProfile | null>(() => fetchSlot(primary), [slotKey(primary)])
  const f1 = useFetch<AnyProfile | null>(() => fetchSlot(slot1),  [slotKey(slot1)])
  const f2 = useFetch<AnyProfile | null>(() => fetchSlot(slot2),  [slotKey(slot2)])

  const renderColumns: { slot: SlotState; fetch: ProfileFetch; isPrimary: boolean }[] = [
    { slot: primary, fetch: f0, isPrimary: true },
  ]
  if (slot1) renderColumns.push({ slot: slot1, fetch: f1, isPrimary: false })
  if (slot2) renderColumns.push({ slot: slot2, fetch: f2, isPrimary: false })

  const anyLoading = renderColumns.some(c => c.fetch.loading && !c.fetch.data)
  const firstError = renderColumns.find(c => c.fetch.error)

  // Drive row visibility — a discipline renders if ANY column has data.
  const anyHasData: Record<TeamDiscipline, boolean> = {
    results: false, batting: false, bowling: false, fielding: false, partnerships: false,
  }
  for (const c of renderColumns) {
    if (!c.fetch.data) continue
    for (const d of DISCIPLINES) {
      if (disciplineHasData(c.slot, c.fetch.data, d)) anyHasData[d] = true
    }
  }

  const totalColumns = renderColumns.length

  const handleRemove = (slot: SlotState, isPrimary: boolean) => {
    if (isPrimary) onClearPrimary()
    else if (slot.kind === 'avg') onRemoveAvg()
    else if (slot.entity) onRemoveTeam(slot.entity)
  }

  return (
    <div>
      <ScopeIndicator filters={primaryFilters} />

      <div
        className="wisden-compare-legend"
        style={{
          fontSize: '0.85em',
          opacity: 0.7,
          fontStyle: 'italic',
          marginBottom: '0.75rem',
          lineHeight: 1.5,
        }}
      >
        <div title="Each chip is the team's value vs the league baseline computed for that COLUMN's scope. Slots that don't override scope inherit from the FilterBar above; slots that do (look for the scope chip below the team name, once enabled) baseline against their own narrower scope.">
          <strong>↑/↓ ±X%</strong> = team value vs league baseline in each
          column's scope. Arrow shows numerical direction (↑ above league, ↓
          below); colour shows good/bad — <span style={{ color: 'rgb(36,128,68)', fontWeight: 500 }}>green = better</span>,
          <span style={{ color: 'rgb(170,52,52)', fontWeight: 500 }}> red = worse</span>{' '}
          (econ lower-better, RR higher-better — colour bakes that in).
        </div>
        <div style={{ marginTop: '0.2rem' }}>
          Substats: <strong>b</strong> = boundary % · <strong>d</strong> = dot % ·
          <strong> w</strong> = wickets ·
          <strong> n</strong> = partnerships in scope ·
          <strong> hi</strong> = highest single partnership
        </div>
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
        {renderColumns.map((c, idx) => (
          <CompareSlotColumn
            key={c.isPrimary ? `__primary__${c.slot.entity}` : `slot${idx}-${c.slot.kind}-${c.slot.entity ?? 'avg'}`}
            slot={c.slot}
            fetch={c.fetch}
            isPrimary={c.isPrimary}
            anyHasData={anyHasData}
            onRemove={() => handleRemove(c.slot, c.isPrimary)}
          />
        ))}
      </div>

      {anyLoading && !renderColumns.every(c => c.fetch.data) && (
        <Spinner label="Loading teams…" />
      )}
      {firstError && !anyLoading && (
        <ErrorBanner
          message={`Could not load one of the columns: ${firstError.fetch.error}`}
          onRetry={firstError.fetch.refetch}
        />
      )}

      <SeasonTrajectoryStrip
        columns={renderColumns
          .filter(c => !!c.fetch.data)
          .map(c => ({
            label: slotLabel(c.slot),
            profile: c.fetch.data!,
            isAverage: c.slot.kind === 'avg',
          }))}
      />
    </div>
  )
}

// ─── one column (team or avg) ───────────────────────────────────────

interface ColumnProps {
  slot: SlotState
  fetch: ProfileFetch
  isPrimary: boolean
  anyHasData: Record<TeamDiscipline, boolean>
  onRemove: () => void
}

function CompareSlotColumn({
  slot, fetch, isPrimary, anyHasData, onRemove,
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

  const matches = slotMatches(slot, profile)
  const isTeam = slot.kind === 'team'
  const teamName = slot.entity ?? ''
  const gender = slot.scope.gender || null

  const soloLink = isTeam
    ? `/teams?${new URLSearchParams({ team: teamName, ...carryTeamFilters(slot.scope as FilterParams) })}`
    : null

  return (
    <div className="wisden-compare-col">
      <div className="wisden-compare-col-head">
        <h2 className="wisden-compare-col-name">
          {isTeam && (
            <>
              <span style={{ marginRight: '0.35rem' }}>
                <FlagBadge team={teamName} gender={gender} size="sm" />
              </span>
              <Link to={soloLink!} className="wisden-compare-col-namelink">{teamName}</Link>
            </>
          )}
          {!isTeam && (
            <span
              className="wisden-compare-col-namelink"
              title="Pool-weighted league baseline scoped to the active filters"
              style={{ fontStyle: 'italic' }}
            >
              {scopeAvgLabel(slot.scope)}
            </span>
          )}
        </h2>
        <button
          type="button"
          className="wisden-compare-col-remove"
          onClick={onRemove}
          aria-label={
            isPrimary ? 'Clear comparison'
              : isTeam ? `Remove ${teamName}`
              : 'Remove league average'
          }
          title={
            isPrimary ? 'Clear comparison — back to landing'
              : isTeam ? `Remove ${teamName}`
              : 'Remove league average column'
          }
        >
          ✕
        </button>
      </div>

      <SlotHeaderChip overrides={slot.overrides} />

      <div className="wisden-player-identity">
        {matches > 0 && (
          <>
            <span className="num">{matches}</span>{' '}
            {isTeam ? 'matches' : 'matches in scope'}
          </>
        )}
        {matches === 0 && <em>no matches in scope</em>}
      </div>

      {DISCIPLINES.map(d => {
        if (!anyHasData[d]) return null
        const has = disciplineHasData(slot, profile, d)
        if (isTeam) {
          const tp = profile as TeamProfile
          return (
            <div key={d}>
              <TeamSummaryRow
                discipline={d}
                profile={tp}
                team={teamName}
                filters={slot.scope as FilterParams}
                placeholder={!has}
              />
              {(d === 'batting' || d === 'bowling') && (
                <PhaseBandsRow profile={tp} discipline={d} placeholder={!has} />
              )}
              {d === 'partnerships' && (
                <PartnershipByWicketRows profile={tp} placeholder={!has} />
              )}
            </div>
          )
        }
        const ap = profile as ScopeAverageProfile
        return (
          <div key={d}>
            <AvgSummaryRow
              discipline={d}
              profile={ap}
              placeholder={!has}
            />
            {(d === 'batting' || d === 'bowling') && (
              <PhaseBandsRow profile={ap} discipline={d} placeholder={!has} />
            )}
            {d === 'partnerships' && (
              <PartnershipByWicketRows
                profile={ap}
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
