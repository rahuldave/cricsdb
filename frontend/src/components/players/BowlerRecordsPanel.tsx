/**
 * BowlerRecordsPanel — top-N bowling record lists for a player.
 *
 * 2 lists in a 2-col responsive grid: best_figures (5/35-style),
 * most_economical (min 18 balls / 3 overs gate, economy ASC).
 * Reads BowlerRecords from /api/v1/bowlers/{id}/records.
 */
import { Link } from 'react-router-dom'
import DataTable, { type Column } from '../DataTable'
import { SectionHeader } from '../ChartHeader'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import type { BowlerRecords, PlayerBowlingRecord } from '../../types'

interface Props {
  data: BowlerRecords | null
  loading: boolean
  error: string | null
  refetch?: () => void
  lists?: Array<keyof Omit<BowlerRecords, 'person_id' | 'name'>>
}

const matchLink = (matchId: number, label: string | number) => (
  <Link to={`/matches/${matchId}`} className="comp-link">{label}</Link>
)

const editionCell = (r: PlayerBowlingRecord) => {
  if (r.tournament && r.season) return `${r.tournament}, ${r.season}`
  return r.tournament ?? r.season ?? '-'
}

const bowlingCols: Column<PlayerBowlingRecord>[] = [
  { key: 'figures', label: 'Figures', sortable: false,
    format: (_v, r) => r.figures },
  { key: 'overs', label: 'Overs', sortable: false },
  { key: 'economy', label: 'Econ', sortable: false,
    format: v => v == null ? '-' : String(v) },
  { key: 'opponent', label: 'vs', sortable: false },
  { key: 'season', label: 'Edition', sortable: false,
    format: (_v, r) => editionCell(r) },
  { key: 'date', label: 'Date', sortable: false,
    format: (v, r) => v ? (matchLink(r.match_id, String(v)) as unknown as string) : '-' },
]

interface ListDef {
  key: keyof Omit<BowlerRecords, 'person_id' | 'name'>
  title: string
  rows: (d: BowlerRecords) => PlayerBowlingRecord[]
}

const LISTS: ListDef[] = [
  { key: 'best_figures', title: 'Best bowling figures',
    rows: d => d.best_figures },
  { key: 'most_economical', title: 'Most economical spells (min 3 overs)',
    rows: d => d.most_economical },
]

export default function BowlerRecordsPanel({ data, loading, error, refetch, lists }: Props) {
  if (loading) return <Spinner label="Loading records…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null
  const filtered = lists ? LISTS.filter(l => lists.includes(l.key)) : LISTS
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      {filtered.map(list => (
        <div key={list.key}>
          <SectionHeader title={list.title} />
          <DataTable
            columns={bowlingCols}
            data={list.rows(data)}
            rowKey={r => `${list.key}-${r.match_id}-${r.wickets}-${r.runs}`}
          />
        </div>
      ))}
    </div>
  )
}
