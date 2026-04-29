import { ANY_SENTINEL } from '../../hooks/useUrlState'
import type { SlotState } from '../../hooks/useCompareSlots'

interface Props {
  slot: SlotState
}

const SERIES_TYPE_LABEL: Record<string, string> = {
  bilateral_only: 'bilaterals',
  tournament_only: 'tournaments',
  all: 'all matches',
}

const isAny = (v: string | undefined) => v === ANY_SENTINEL

// Italic sub-line below a team-slot's name surfacing the scope fields
// that differ from primary. Picker / editor only writes overrides for
// actually-divergent fields, so any key in slot.overrides is treated
// as a real divergence.
//
// `__any__` overrides render as "any <axis>" so the user can see the
// slot has explicitly broadened past primary's narrowing (vs the
// no-override case where the chip is suppressed entirely).
//
// Avg slots fold scope into their column label (scopeAvgLabel reads
// the resolved scope), so a chip there would duplicate the label —
// suppressed.
export default function SlotHeaderChip({ slot }: Props) {
  if (slot.kind === 'avg') return null
  const o = slot.overrides
  const parts: string[] = []

  if (o.tournament !== undefined) {
    parts.push(isAny(o.tournament) ? 'any tournament' : (o.tournament || '(no tournament)'))
  }
  const sf = o.season_from
  const st = o.season_to
  if (sf !== undefined || st !== undefined) {
    const sfAny = isAny(sf)
    const stAny = isAny(st)
    if (sfAny && stAny) parts.push('any season')
    else if (sfAny) parts.push(st ? `up to ${st}` : 'any season')
    else if (stAny) parts.push(sf ? `${sf}+` : 'any season')
    else if (sf && st) parts.push(sf === st ? sf : `${sf}-${st}`)
    else if (sf) parts.push(`${sf}+`)
    else if (st) parts.push(`-${st}`)
    else parts.push('all seasons')
  }
  if (o.filter_venue !== undefined) {
    parts.push(isAny(o.filter_venue)
      ? 'any venue'
      : `@ ${o.filter_venue || '(any venue)'}`)
  }
  if (o.series_type !== undefined) {
    if (isAny(o.series_type)) parts.push('any series')
    else parts.push(SERIES_TYPE_LABEL[o.series_type] ?? o.series_type)
  }
  if (o.team_class !== undefined) {
    if (isAny(o.team_class)) parts.push('all teams')
    else if (o.team_class === 'full_member') parts.push('full members only')
  }

  if (parts.length === 0) return null

  return (
    <div
      className="wisden-compare-slot-chip"
      title="This slot's scope differs from the FilterBar above. Chip values baseline against the slot's scope."
    >
      · {parts.join(' · ')}
    </div>
  )
}
