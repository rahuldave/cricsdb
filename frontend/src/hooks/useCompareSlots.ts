import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { FilterParams } from '../types'

export const AVG_SENTINEL = '__avg__'

export type SlotKind = 'team' | 'avg'

export const OVERRIDABLE_SLOT_KEYS = [
  'tournament', 'season_from', 'season_to',
  'filter_venue', 'series_type',
] as const
export type OverridableSlotKey = typeof OVERRIDABLE_SLOT_KEYS[number]

export type ResolvedSlotScope = Pick<FilterParams,
  'gender' | 'team_type' | 'tournament' | 'season_from' | 'season_to'
  | 'filter_venue' | 'series_type'>

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
    if (v != null) {
      overrides[k] = v
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
