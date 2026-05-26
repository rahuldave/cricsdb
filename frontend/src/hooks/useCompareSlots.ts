import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { FilterParams } from '../types'
import { ANY_SENTINEL } from './useUrlState'

export const AVG_SENTINEL = '__avg__'

export type SlotKind = 'team' | 'avg'

export const OVERRIDABLE_SLOT_KEYS = [
  'tournament', 'season_from', 'season_to',
  'filter_venue', 'series_type', 'team_class', 'inning',
] as const
export type OverridableSlotKey = typeof OVERRIDABLE_SLOT_KEYS[number]

export type ResolvedSlotScope = Pick<FilterParams,
  'gender' | 'team_type' | 'tournament' | 'season_from' | 'season_to'
  | 'filter_venue' | 'series_type' | 'team_class' | 'inning'>

// Override entries hold either a real value (narrowing) or
// ANY_SENTINEL ('__any__') meaning "explicit empty / do not inherit
// primary." Resolved scope folds ANY_SENTINEL → undefined so the
// downstream fetcher sends no narrowing for that field.
export type SlotOverrides = Partial<Pick<ResolvedSlotScope, OverridableSlotKey>>

export interface SlotState {
  kind: SlotKind
  entity: string | null
  scope: ResolvedSlotScope
  overrides: SlotOverrides
}

export interface CompareSlots {
  slot1: SlotState | null
  slot2: SlotState | null
}

export function clearSlotUpdates(slotIdx: 1 | 2): Record<string, string> {
  const out: Record<string, string> = { [`compare${slotIdx}`]: '' }
  for (const k of OVERRIDABLE_SLOT_KEYS) out[`compare${slotIdx}_${k}`] = ''
  return out
}

function inheritedScope(primary: FilterParams): ResolvedSlotScope {
  return {
    gender: primary.gender,
    team_type: primary.team_type,
    tournament: primary.tournament,
    season_from: primary.season_from,
    season_to: primary.season_to,
    filter_venue: primary.filter_venue,
    series_type: primary.series_type,
    // team_class is the 9th FilterBar key (post-v3); slots inherit
    // primary by default, override via compareN_team_class URL param —
    // peer of every other overridable axis.
    team_class: primary.team_class,
    // inning is an AuxParams aux field (not a FilterBar key). Slots
    // inherit primary's URL `?inning=` (the page-level InningToggle's
    // value, when set on team Batting/Bowling/Fielding tabs) and may
    // override via `compareN_inning=`. Under Option B (one neutral
    // toggle per column) inning=0 = the team batted first for ALL its
    // rows; bowling/fielding rows draw the bowling in those matches
    // (bowled second). The backend resolves it per-event — the slot
    // sends the raw value, no frontend flip. Spec:
    // spec-inning-unify-option-b.md §5 (governing rule).
    inning: primary.inning,
  }
}

function readSlot(
  params: URLSearchParams, n: 1 | 2, primary: FilterParams,
): SlotState | null {
  const raw = params.get(`compare${n}`)
  if (!raw) return readLegacySlot(params, n, primary)
  const kind: SlotKind = raw === AVG_SENTINEL ? 'avg' : 'team'
  const overrides: SlotOverrides = {}
  const scope = inheritedScope(primary)
  for (const k of OVERRIDABLE_SLOT_KEYS) {
    const v = params.get(`compare${n}_${k}`)
    if (v == null) continue          // missing → default-inherit, no override
    overrides[k] = v                  // record divergence (sentinel or real value)
    if (v === ANY_SENTINEL) {
      // Explicit empty — drop the inherited primary value from
      // resolved scope so the slot's fetcher sends no narrowing for
      // this axis.
      scope[k] = undefined
    } else {
      scope[k] = v
    }
  }
  return { kind, entity: kind === 'team' ? raw : null, scope, overrides }
}

// Legacy fallback so the grid renders correctly between mount and
// the migration useEffect's first run. Removed implicitly once the
// migration rewrites the URL with replace:true.
function readLegacySlot(
  params: URLSearchParams, n: 1 | 2, primary: FilterParams,
): SlotState | null {
  const csv = params.get('compare')
  const teams = csv ? csv.split(',').map(s => s.trim()).filter(Boolean) : []
  const wantsAvg = params.get('avg_slot') === '1'
  let kind: SlotKind | null = null
  let entity: string | null = null
  if (n === 1) {
    if (teams[0]) { kind = 'team'; entity = teams[0] }
    else if (wantsAvg) { kind = 'avg' }
  } else {
    if (teams[1]) { kind = 'team'; entity = teams[1] }
    else if (wantsAvg && teams.length === 1) { kind = 'avg' }
  }
  if (kind == null) return null
  return { kind, entity, scope: inheritedScope(primary), overrides: {} }
}

export function useCompareSlots(primary: FilterParams): CompareSlots {
  const [params] = useSearchParams()
  const qs = params.toString()
  // primary is itself memoed by qs in useFilters, so qs alone is a
  // sufficient memo key; lint-disabled to stop hooks/exhaustive-deps
  // from demanding primary in the dep array.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => ({
    slot1: readSlot(params, 1, primary),
    slot2: readSlot(params, 2, primary),
  }), [qs])
}
