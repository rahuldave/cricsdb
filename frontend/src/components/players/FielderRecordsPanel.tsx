/**
 * FielderRecordsPanel — top-N fielding record lists for a player.
 *
 * 3 lists in a 2-col responsive grid: most_catches_match,
 * most_stumpings_match (typically empty for outfielders),
 * most_dismissals_match (catches + stumpings + run-outs).
 *
 * Catches INCLUDE caught_and_bowled per Convention 3. Volume framing
 * — substitute appearances count (matches /leaders semantic, NOT the
 * /distribution master-sample semantic).
 */
import { Link } from 'react-router-dom'
import DataTable, { type Column } from '../DataTable'
import { SectionHeader } from '../ChartHeader'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import type { FielderRecords, PlayerFieldingRecord } from '../../types'

interface Props {
  data: FielderRecords | null
  loading: boolean
  error: string | null
  refetch?: () => void
  lists?: Array<keyof Omit<FielderRecords, 'person_id' | 'name'>>
}

const matchLink = (matchId: number, label: string | number) => (
  <Link to={`/matches/${matchId}`} className="comp-link">{label}</Link>
)

const editionCell = (r: PlayerFieldingRecord) => {
  if (r.tournament && r.season) return `${r.tournament}, ${r.season}`
  return r.tournament ?? r.season ?? '-'
}

const fieldingCols: Column<PlayerFieldingRecord>[] = [
  { key: 'catches', label: 'C', sortable: false },
  { key: 'stumpings', label: 'St', sortable: false },
  { key: 'run_outs', label: 'RO', sortable: false },
  { key: 'dismissals', label: 'Total', sortable: false },
  { key: 'opponent', label: 'vs', sortable: false },
  { key: 'season', label: 'Edition', sortable: false,
    format: (_v, r) => editionCell(r) },
  { key: 'date', label: 'Date', sortable: false,
    format: (v, r) => v ? (matchLink(r.match_id, String(v)) as unknown as string) : '-' },
]

interface ListDef {
  key: keyof Omit<FielderRecords, 'person_id' | 'name'>
  title: string
  rows: (d: FielderRecords) => PlayerFieldingRecord[]
}

const LISTS: ListDef[] = [
  { key: 'most_catches_match', title: 'Most catches in a match',
    rows: d => d.most_catches_match },
  { key: 'most_stumpings_match', title: 'Most stumpings in a match',
    rows: d => d.most_stumpings_match },
  { key: 'most_dismissals_match', title: 'Most dismissals in a match',
    rows: d => d.most_dismissals_match },
]

export default function FielderRecordsPanel({ data, loading, error, refetch, lists }: Props) {
  if (loading) return <Spinner label="Loading records…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null
  const filtered = lists ? LISTS.filter(l => lists.includes(l.key)) : LISTS
  const innerCls = filtered.length === 1
    ? 'grid grid-cols-1 gap-6 mt-4'
    : 'grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4'
  return (
    <div className={innerCls}>
      {filtered.map(list => (
        <div key={list.key}>
          <SectionHeader title={list.title} />
          <DataTable
            columns={fieldingCols}
            data={list.rows(data)}
            rowKey={r => `${list.key}-${r.match_id}-${r.dismissals}`}
          />
        </div>
      ))}
    </div>
  )
}
