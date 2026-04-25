import type { SlotState } from '../../hooks/useCompareSlots'

interface Props {
  slot: SlotState
}

const SERIES_TYPE_LABEL: Record<string, string> = {
  bilateral_only: 'bilaterals',
  tournament_only: 'tournaments',
  all: 'all matches',
}

// Italic sub-line below a team-slot's name surfacing the scope fields
// that differ from primary. Picker / editor only writes overrides for
// actually-divergent fields, so any key in slot.overrides is treated
// as a real divergence.
//
// Avg slots fold scope into their column label (scopeAvgLabel reads
// the resolved scope), so a chip there would duplicate the label —
// suppressed.
export default function SlotHeaderChip({ slot }: Props) {
  if (slot.kind === 'avg') return null
  const o = slot.overrides
  const parts: string[] = []

  if (o.tournament !== undefined) {
    parts.push(o.tournament || '(no tournament)')
  }
  const sf = o.season_from
  const st = o.season_to
  if (sf !== undefined || st !== undefined) {
    if (sf && st) parts.push(sf === st ? sf : `${sf}-${st}`)
    else if (sf) parts.push(`${sf}+`)
    else if (st) parts.push(`-${st}`)
    else parts.push('all seasons')
  }
  if (o.filter_venue !== undefined) {
    parts.push(`@ ${o.filter_venue || '(any venue)'}`)
  }
  if (o.series_type !== undefined) {
    parts.push(SERIES_TYPE_LABEL[o.series_type] ?? o.series_type)
  }

  if (parts.length === 0) return null

  return (
    <div
      className="wisden-compare-slot-chip"
      style={{
        fontSize: '0.85em',
        fontStyle: 'italic',
        opacity: 0.7,
        marginTop: '-0.15rem',
        marginBottom: '0.4rem',
      }}
      title="This slot's scope differs from the FilterBar above. Chip values baseline against the slot's scope."
    >
      · {parts.join(' · ')}
    </div>
  )
}
