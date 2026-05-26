import { Fragment, useState } from 'react'
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
import ColumnScopeStrip from './ColumnScopeStrip'
import SlotScopeEditor from './SlotScopeEditor'
import {
  teamDisciplineHasData, teamMatchesInScope, carryTeamFilters,
  avgDisciplineHasData, scopeAvgLabel,
  DISCIPLINE_TOTAL_ROWS,
  type TeamDiscipline,
} from './teamUtils'
import { useFetch, type FetchState } from '../../hooks/useFetch'
import { getTeamProfile, getScopeAverageProfile } from '../../api'
import type { TeamProfile, ScopeAverageProfile, FilterParams } from '../../types'
import type { SlotState, CompareSlots, SlotOverrides } from '../../hooks/useCompareSlots'
import { OVERRIDABLE_SLOT_KEYS } from '../../hooks/useCompareSlots'

type SlotIdx = 1 | 2

interface Props {
  primaryTeam: string
  primaryFilters: FilterParams
  slots: CompareSlots
  onClearPrimary: () => void
  onRemoveTeam: (name: string) => void
  onRemoveAvg: () => void
  /** Replace a slot's overrides wholesale. */
  onUpdateSlotScope: (slotIdx: SlotIdx, overrides: SlotOverrides) => void
  /** Drop all overrides on a slot — slot inherits primary again. */
  onResetSlotScope: (slotIdx: SlotIdx) => void
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
      team_class: filters.team_class,
      // inning is the one aux the primary column carries — so the
      // left/primary column honors a carried-over ?inning= identically
      // to how the peer slots inherit it (useCompareSlots.inheritedScope).
      // Without this the primary showed ALL innings while a 1st-innings
      // slot sat beside it — an unfair comparison + disagreeing scope
      // strips. Under Option B inning=0 = batted first for ALL rows
      // (the backend resolves it per-event). toss_outcome/result are
      // deliberately NOT carried: the league-average baseline can't
      // express them (≈50% by construction), so narrowing the team
      // columns by them would break chip↔baseline symmetry.
      inning: filters.inning,
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

/** Pick out a peer avg slot's resolved scope so the team-side chip
 *  baseline aligns to whatever the avg col displays. Two encodings
 *  ride together for back-compat through the rollout:
 *
 *  - `chip_team_class` — the narrow v3 hint that ONLY conveys the
 *    team_class axis. Backend reads this in `_league_aux` (Commit 1
 *    of this spec preserves the path). Kept here so a backend that
 *    hasn't shipped the new mechanism still aligns under
 *    narrowing-direction overrides.
 *  - `chip_baseline_scope_json` — base64-JSON of the avg slot's
 *    FULL effective scope (FilterBar fields + synthesized
 *    `scope_to_team` when the auto-narrow applies). Backend honors
 *    this in Commit 3; ignored as an unknown query param until
 *    then. Generalises chip alignment to broaden-direction
 *    overrides (e.g. primary tournament=IPL, avg slot
 *    tournament=__any__ → chip baseline = all-club pool).
 *
 *  Spec: spec-slot-override-chip-alignment.md §4.2, §6.4. */
type ChipAlign = { chip_team_class?: string; chip_baseline_scope_json?: string }
function chipAlignmentFor(slots: CompareSlots, primaryTeam: string): ChipAlign {
  const avg = slots.slot1?.kind === 'avg' ? slots.slot1
            : slots.slot2?.kind === 'avg' ? slots.slot2 : null
  if (!avg) return {}

  const out: ChipAlign = {}
  // Back-compat — backend's existing _league_aux path reads this.
  if (avg.scope.team_class) out.chip_team_class = avg.scope.team_class

  // Forward — full-scope serialization. Mirror the auto-narrow logic
  // in fetchSlot so the chip baseline carries the same scope_to_team
  // synthesis that drives the avg col's actual aggregation.
  const isClub = avg.scope.team_type === 'club'
  // Skip the auto-narrow when the slot has explicitly declared a club
  // tier — `team_class=primary_club` / `secondary_club` is the user's
  // own pool dimension, and intersecting with `scope_to_team` would
  // collapse it back to the team's tournament universe (e.g. CSK +
  // primary_club ⇒ IPL ∩ primary = IPL again, swallowing the broaden).
  const explicitClubTier =
    avg.scope.team_class === 'primary_club' ||
    avg.scope.team_class === 'secondary_club'
  const shouldNarrow = isClub && !avg.scope.tournament && !explicitClubTier
  const payload: Record<string, string> = {}
  if (avg.scope.gender)       payload.gender = avg.scope.gender
  if (avg.scope.team_type)    payload.team_type = avg.scope.team_type
  for (const k of OVERRIDABLE_SLOT_KEYS) {
    const v = avg.scope[k]
    if (v) payload[k] = v
  }
  if (shouldNarrow) payload.scope_to_team = primaryTeam
  if (Object.keys(payload).length > 0) {
    // btoa with JSON is URL-safe enough for query params; Python
    // base64.urlsafe_b64decode tolerates standard b64 too.
    out.chip_baseline_scope_json = btoa(JSON.stringify(payload))
  }
  return out
}

function fetchSlot(
  slot: SlotState | null,
  primaryTeam: string,
  chipAlign: ChipAlign,
): Promise<AnyProfile | null> {
  if (!slot) return Promise.resolve(null)
  if (slot.kind === 'avg') {
    // Auto-narrow to primary team's tournament universe ONLY for clubs
    // (closed-league semantic — RCB → IPL avg is a meaningful baseline
    // because every IPL team plays every other IPL team). For
    // internationals the auto-narrow degenerates to a team-centered
    // baseline (Australia's "tournament universe" is the 6 tours/events
    // Aus played in, all of which contain Australia by construction —
    // so the avg col becomes "average of Aus's matches" and chips read
    // as flatteringly above-average by structure). For internationals
    // the avg col defaults to the full pool (e.g. Men's T20I 2024-25 =
    // 870 matches); the user can opt into a tighter pool with
    // team_class=full_member from the slot picker.
    const isClub = slot.scope.team_type === 'club'
    // Mirror chipAlignmentFor: skip auto-narrow when explicit club
    // tier is set so the slot's pool reflects the user's broaden.
    const explicitClubTier =
      slot.scope.team_class === 'primary_club' ||
      slot.scope.team_class === 'secondary_club'
    const shouldNarrow = isClub && !slot.scope.tournament && !explicitClubTier
    const scope = shouldNarrow
      ? { ...slot.scope, scope_to_team: primaryTeam }
      : slot.scope
    return getScopeAverageProfile(scope)
  }
  // Team-side request: chip baselines must align to the avg col's
  // scope (team_class), not the team's own. team data stays on the
  // team's slot scope so Aus shows all 22 of its matches even when
  // the avg col is FM-only.
  return getTeamProfile(slot.entity!, { ...slot.scope, ...chipAlign })
}

function disciplineHasData(slot: SlotState, profile: AnyProfile, d: TeamDiscipline): boolean {
  if (slot.kind === 'avg') return avgDisciplineHasData(d, profile as ScopeAverageProfile)
  return teamDisciplineHasData(d, profile as TeamProfile)
}

function slotMatches(slot: SlotState, profile: AnyProfile): number {
  if (slot.kind === 'avg') return (profile as ScopeAverageProfile).summary?.matches ?? 0
  return teamMatchesInScope(profile as TeamProfile)
}

function slotLabel(slot: SlotState, _primaryTeam: string, primaryTournaments: string[]): string {
  // Used by the season-trajectory strip's legend (single-line). Avg
  // slots use the anchor (line1) only — gender / season detail in line2
  // is the same across all legend entries (it's the FilterBar scope)
  // and would just clutter the chart key.
  if (slot.kind === 'avg') return scopeAvgLabel(slot.scope, primaryTournaments).line1
  return slot.entity ?? ''
}

export default function TeamCompareGrid({
  primaryTeam, primaryFilters, slots,
  onClearPrimary, onRemoveTeam, onRemoveAvg,
  onUpdateSlotScope, onResetSlotScope,
}: Props) {
  const primary = primarySlotOf(primaryTeam, primaryFilters)
  const slot1 = slots.slot1
  const slot2 = slots.slot2

  // Chip-baseline alignment hint: when ANY peer slot is an avg, the
  // team-side chip baseline must use the avg's effective scope so the
  // chip's scope_avg numerically equals the avg col's displayed value.
  // Stable string-keyed for useFetch deps — concatenate both fields so
  // edits to either side bust the cache.
  const chipAlign = chipAlignmentFor(slots, primaryTeam)
  const chipAlignKey =
    `${chipAlign.chip_team_class ?? ''}|${chipAlign.chip_baseline_scope_json ?? ''}`

  // Fixed-arity useFetch calls: one per slot. Discriminate kind inside
  // the fetcher so the same hook position serves both team and avg.
  const f0 = useFetch<AnyProfile | null>(() => fetchSlot(primary, primaryTeam, chipAlign), [slotKey(primary), primaryTeam, chipAlignKey])
  const f1 = useFetch<AnyProfile | null>(() => fetchSlot(slot1,   primaryTeam, chipAlign), [slotKey(slot1),   primaryTeam, chipAlignKey])
  const f2 = useFetch<AnyProfile | null>(() => fetchSlot(slot2,   primaryTeam, chipAlign), [slotKey(slot2),   primaryTeam, chipAlignKey])

  const renderColumns: { slot: SlotState; fetch: ProfileFetch; isPrimary: boolean; slotIdx: SlotIdx | null }[] = [
    { slot: primary, fetch: f0, isPrimary: true,  slotIdx: null },
  ]
  if (slot1) renderColumns.push({ slot: slot1, fetch: f1, isPrimary: false, slotIdx: 1 })
  if (slot2) renderColumns.push({ slot: slot2, fetch: f2, isPrimary: false, slotIdx: 2 })

  const anyLoading = renderColumns.some(c => c.fetch.loading && !c.fetch.data)
  const firstError = renderColumns.find(c => c.fetch.error)

  // Primary team's tournament universe in current scope — drives the
  // avg-col label promotion (singleton → folded into line1) and the
  // legend label. Empty array until the primary fetch resolves.
  const primaryTournaments = (f0.data as TeamProfile | null)?.summary?.tournaments_in_scope ?? []

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

  // Nested subgrid row count: every individual row that needs to align
  // across columns is one parent grid track. Per-discipline counts:
  //   results:      6 = section-head + 5 stat rows
  //   batting:      9 = section-head + 5 stat rows + 3 phase rows
  //   bowling:     10 = section-head + 6 stat rows + 3 phase rows
  //   fielding:     7 = section-head + 6 stat rows
  //   partnerships: 18 = section-head + 7 stat rows + 10 by-wicket rows
  // Plus 4 fixed top-level rows (col-head, chip-area, editor-row,
  // identity). The TeamSummaryRow / AvgSummaryRow / PhaseBandsRow /
  // PartnershipByWicketRows components each declare their own grid-row
  // span via inline style, and their inner dls are subgrids over the
  // stat rows. Result: every row natively pins across columns; no
  // min-height / pixel-hack patches needed for alignment.
  const visibleDisciplineRows = DISCIPLINES
    .filter(d => anyHasData[d])
    .reduce((s, d) => s + DISCIPLINE_TOTAL_ROWS[d], 0)
  const totalRows = 4 + visibleDisciplineRows

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

      {/* Outer wrapper enables horizontal scroll on narrow viewports.
       *  At iPhone 13 width (390px) three 13rem-min columns + gap
       *  exceed the viewport — user pans horizontally rather than
       *  squeezing columns to ~115px. 13rem (208px) was bumped from
       *  11rem after the avg-col label moved to a noun phrase
       *  ("Indian Premier League average") that can't fit at the
       *  narrower floor without wrapping to 4 lines. At desktop
       *  widths the minmax(13rem, 1fr) template behaves as 1fr split. */}
      <div style={{ overflowX: 'auto' }}>
        <div
          className="wisden-compare-columns"
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${totalColumns}, minmax(13rem, 1fr))`,
            gridTemplateRows: `repeat(${totalRows}, auto)`,
            columnGap: '1.5rem',
            rowGap: '0',
            alignItems: 'start',
          }}
        >
          {renderColumns.map((c, idx) => (
            <CompareSlotColumn
              key={c.isPrimary ? `__primary__${c.slot.entity}` : `slot${idx}-${c.slot.kind}-${c.slot.entity ?? 'avg'}`}
              slot={c.slot}
              slotIdx={c.slotIdx}
              primary={primaryFilters}
              primaryTeam={primaryTeam}
              primaryTournaments={primaryTournaments}
              fetch={c.fetch}
              isPrimary={c.isPrimary}
              anyHasData={anyHasData}
              onRemove={() => handleRemove(c.slot, c.isPrimary)}
              onUpdateScope={onUpdateSlotScope}
              onResetScope={onResetSlotScope}
            />
          ))}
        </div>
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
            label: slotLabel(c.slot, primaryTeam, primaryTournaments),
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
  slotIdx: SlotIdx | null
  primary: FilterParams
  /** Primary team name — passed in for the SlotScopeEditor's reset
   *  affordance and ✕-button labels. */
  primaryTeam: string
  /** Distinct tournaments the primary team appears in within scope —
   *  drives the avg-col label promotion (singleton folds into line1). */
  primaryTournaments: string[]
  fetch: ProfileFetch
  isPrimary: boolean
  anyHasData: Record<TeamDiscipline, boolean>
  onRemove: () => void
  onUpdateScope: (slotIdx: SlotIdx, overrides: SlotOverrides) => void
  onResetScope: (slotIdx: SlotIdx) => void
}

function CompareSlotColumn({
  slot, slotIdx, primary, primaryTeam, primaryTournaments, fetch, isPrimary, anyHasData,
  onRemove, onUpdateScope, onResetScope,
}: ColumnProps) {
  const [editing, setEditing] = useState(false)
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

  // Avg-col two-line label. line1 anchors on a tournament name when the
  // primary team's universe collapses to a singleton (RCB → IPL); else
  // "League average" / "Full-member average". line2 is the italic scope
  // subtitle (gender · season range).
  const avgLbl = !isTeam ? scopeAvgLabel(slot.scope, primaryTournaments) : null

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
              title={
                slot.scope.team_type === 'club' && !slot.scope.tournament && primaryTournaments.length === 1
                  ? `Pool-weighted league baseline — primary team's universe collapses to ${primaryTournaments[0]} so the avg is computed over that tournament.`
                  : slot.scope.team_type === 'club' && !slot.scope.tournament
                  ? `Pool-weighted league baseline narrowed to tournaments ${primaryTeam} has played in (auto-scope).`
                  : 'Pool-weighted league baseline scoped to the active filters'
              }
              style={{ fontStyle: 'italic' }}
            >
              {avgLbl!.line1}
            </span>
          )}
        </h2>
        {!isPrimary && slotIdx != null && (
          <button
            type="button"
            className="wisden-compare-col-edit"
            onClick={() => setEditing(e => !e)}
            aria-label={editing ? 'Close scope editor' : 'Edit slot scope'}
            title={editing ? 'Close scope editor' : 'Override this column\'s scope (tournament / season / venue / series)'}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: '0.95em', padding: '0 0.25rem', marginRight: '0.1rem',
              opacity: 0.7,
            }}
          >
            ✎
          </button>
        )}
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

      {/* Chip-area: per-column scope readout. Mirrors the global
       *  ScopeStatusStrip below the FilterBar so users can match a
       *  column's scope to the page-wide one at a glance. Every
       *  column renders a strip — primary, team slots, avg slots —
       *  with overridden segments marked `✎`. Subgrid sizes the row
       *  to the tallest column's wrapped strip; columns whose strip
       *  is shorter just have whitespace below. User feedback
       *  2026-04-29 explicitly accepted "all columns forced down 2-3
       *  rows" as the right tradeoff. */}
      <div className="wisden-compare-chip-area">
        <ColumnScopeStrip
          scope={slot.scope}
          overrideKeys={new Set(Object.keys(slot.overrides))}
        />
      </div>

      {/* Editor-row slot — always rendered so every column has the
       *  same number of subgrid children (auto-placement keeps
       *  identity + discipline rows aligned). Empty in primary +
       *  non-editing slot columns; collapses to ~0 height. */}
      <div className="wisden-compare-editor-row">
        {editing && slotIdx != null && (
          <SlotScopeEditor
            primary={primary}
            team={isTeam ? teamName : undefined}
            initial={slot.overrides}
            onApply={(o) => { onUpdateScope(slotIdx, o); setEditing(false) }}
            onReset={() => { onResetScope(slotIdx); setEditing(false) }}
            onCancel={() => setEditing(false)}
          />
        )}
      </div>

      <div className="wisden-player-identity">
        {matches > 0 && (
          <>
            <span className="num">{matches}</span>{' '}
            {isTeam ? 'matches' : 'matches in scope'}
          </>
        )}
        {matches === 0 && <em>no matches in scope</em>}
      </div>

      {/* Each visible discipline contributes its rows AS DIRECT SIBLINGS
       *  of the column subgrid (no wrapper div) so each section,
       *  phase-band dl, and by-wicket dl is its own subgrid item with
       *  an explicit `grid-row: span N`. Fragment keeps React happy
       *  with the per-discipline key without adding a layout box. */}
      {DISCIPLINES.map(d => {
        if (!anyHasData[d]) return null
        const has = disciplineHasData(slot, profile, d)
        if (isTeam) {
          const tp = profile as TeamProfile
          return (
            <Fragment key={d}>
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
            </Fragment>
          )
        }
        const ap = profile as ScopeAverageProfile
        return (
          <Fragment key={d}>
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
          </Fragment>
        )
      })}
    </div>
  )
}
