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
import type { ReactNode } from 'react'
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

/** Props of `PlayerRecordsSummary`. */
interface Props {
  playerId: string // the player whose records are fetched
  filters: FilterParams // the scope of the records
  hasBatting: boolean // show and fetch the batting row
  hasBowling: boolean // show and fetch the bowling row
  hasFielding: boolean // show and fetch the fielding row
  /** Optional trailing cell rendered inside the records grid after
   *  the discipline panels. Used to slot the "Compare with another
   *  player" picker into the spare column on the last row. */
  trailingSlot?: ReactNode
}

/** Show the top 5 records of each discipline the player has data in, under one Records header; nothing when there is none. */
export default function PlayerRecordsSummary({
  playerId, filters, hasBatting, hasBowling, hasFielding, trailingSlot,
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
        {trailingSlot}
      </div>
    </div>
  )
}
