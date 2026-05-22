/**
 * PlayerRecordsSummary — condensed top-5 records section on the
 * Players profile (/players?player=X).
 *
 * One row per applicable discipline:
 *   - Batting:  top 5 highest scores
 *   - Bowling:  top 5 best figures
 *   - Fielding: top 5 most dismissals in a match
 *
 * Discipline rows render only if the player has data in that
 * discipline (hasBatting/hasBowling/hasFielding from PlayerProfile).
 * Each row reuses the corresponding *RecordsPanel with `lists` set
 * to the single most-headline list — so the dense full Records
 * subtab on /batting?player=X etc. is the "drill down for more"
 * destination.
 *
 * Fetches are gated on the discipline being relevant — no fan-out
 * for batting-only or bowling-only specialists.
 */
import { useFetch } from '../../hooks/useFetch'
import { useFilterDeps } from '../../hooks/useFilterDeps'
import { getBatterRecords, getBowlerRecords, getFielderRecords } from '../../api'
import { SectionHeader } from '../ChartHeader'
import BatterRecordsPanel from './BatterRecordsPanel'
import BowlerRecordsPanel from './BowlerRecordsPanel'
import FielderRecordsPanel from './FielderRecordsPanel'
import type {
  BatterRecords, BowlerRecords, FielderRecords, FilterParams,
} from '../../types'

interface Props {
  playerId: string
  filters: FilterParams
  hasBatting: boolean
  hasBowling: boolean
  hasFielding: boolean
}

export default function PlayerRecordsSummary({
  playerId, filters, hasBatting, hasBowling, hasFielding,
}: Props) {
  const filterDeps = [playerId, ...useFilterDeps()]

  const battingFetch = useFetch<BatterRecords | null>(
    () => hasBatting
      ? getBatterRecords(playerId, { ...filters, limit: 5 })
      : Promise.resolve(null),
    filterDeps,
  )
  const bowlingFetch = useFetch<BowlerRecords | null>(
    () => hasBowling
      ? getBowlerRecords(playerId, { ...filters, limit: 5 })
      : Promise.resolve(null),
    filterDeps,
  )
  const fieldingFetch = useFetch<FielderRecords | null>(
    () => hasFielding
      ? getFielderRecords(playerId, { ...filters, limit: 5 })
      : Promise.resolve(null),
    filterDeps,
  )

  // Empty render until ANY discipline has data.
  if (!hasBatting && !hasBowling && !hasFielding) return null

  return (
    <div className="mt-8">
      <SectionHeader
        title="Records"
        subtitle="Top 5 per discipline at the current scope. Drill into the Records subtab on each discipline page for the full lists."
      />
      {/* Side-by-side records grid (user-asked 2026-05-22). Drops to
          one column on mobile via wisden-records-grid class in
          index.css — see @media (max-width: 720px). */}
      <div className="wisden-records-grid">
        {hasBatting && (
          <BatterRecordsPanel
            data={battingFetch.data}
            loading={battingFetch.loading}
            error={battingFetch.error}
            refetch={battingFetch.refetch}
            lists={['highest_scores']}
          />
        )}
        {hasBowling && (
          <BowlerRecordsPanel
            data={bowlingFetch.data}
            loading={bowlingFetch.loading}
            error={bowlingFetch.error}
            refetch={bowlingFetch.refetch}
            lists={['best_figures']}
          />
        )}
        {hasFielding && (
          <FielderRecordsPanel
            data={fieldingFetch.data}
            loading={fieldingFetch.loading}
            error={fieldingFetch.error}
            refetch={fieldingFetch.refetch}
            lists={['most_dismissals_match']}
          />
        )}
      </div>
    </div>
  )
}
