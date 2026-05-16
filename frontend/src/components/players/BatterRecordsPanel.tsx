/**
 * BatterRecordsPanel — top-N batting record lists for a player.
 *
 * Renders 6 lists in a 2-col responsive grid (1-col on mobile):
 *   - Highest scores
 *   - Fastest 50s / 100s
 *   - Most sixes / fours in an innings
 *   - Best strike rates (min 20 balls)
 *
 * Mirrors the Tournament RecordsTab visual idiom but with batting-
 * specific columns. Reads BatterRecords from
 * /api/v1/batters/{id}/records.
 *
 * Compact variant (`compact={true}`) drops less-essential columns
 * (Tournament, Edition) and is what the Players profile mounts.
 */
import { Link } from 'react-router-dom'
import DataTable, { type Column } from '../DataTable'
import { SectionHeader } from '../ChartHeader'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import type { BatterRecords, PlayerBattingRecord } from '../../types'

interface Props {
  data: BatterRecords | null
  loading: boolean
  error: string | null
  refetch?: () => void
  compact?: boolean
  /** If set, only show this subset of lists (used by the
   *  cross-discipline Players-profile records summary). */
  lists?: Array<keyof Omit<BatterRecords, 'person_id' | 'name'>>
}

const matchLink = (matchId: number, label: string | number) => (
  <Link to={`/matches/${matchId}`} className="comp-link">{label}</Link>
)

const editionCell = (r: PlayerBattingRecord) => {
  if (r.tournament && r.season) return `${r.tournament}, ${r.season}`
  return r.tournament ?? r.season ?? '-'
}

const battingCols = (extra?: { showSixes?: boolean; showFours?: boolean; showSR?: boolean }): Column<PlayerBattingRecord>[] => {
  const cols: Column<PlayerBattingRecord>[] = [
    { key: 'figures', label: 'Score', sortable: false,
      format: (_v, r) => r.figures },
    { key: 'opponent', label: 'vs', sortable: false },
  ]
  if (extra?.showSixes) cols.push({ key: 'sixes', label: '6s', sortable: false })
  if (extra?.showFours) cols.push({ key: 'fours', label: '4s', sortable: false })
  if (extra?.showSR) cols.push({
    key: 'strike_rate', label: 'SR', sortable: false,
    format: (v) => v == null ? '-' : String(v),
  })
  cols.push({
    key: 'season', label: 'Edition', sortable: false,
    format: (_v, r) => editionCell(r),
  })
  cols.push({
    key: 'date', label: 'Date', sortable: false,
    format: (v, r) => v ? (matchLink(r.match_id, String(v)) as unknown as string) : '-',
  })
  return cols
}

interface ListDef {
  key: keyof Omit<BatterRecords, 'person_id' | 'name'>
  title: string
  rows: (d: BatterRecords) => PlayerBattingRecord[]
  cols: Column<PlayerBattingRecord>[]
}

const LISTS: ListDef[] = [
  { key: 'highest_scores', title: 'Highest scores',
    rows: d => d.highest_scores, cols: battingCols({ showSR: true }) },
  { key: 'fastest_50s', title: 'Fastest 50s',
    rows: d => d.fastest_50s, cols: battingCols({ showSR: true }) },
  { key: 'fastest_100s', title: 'Fastest 100s',
    rows: d => d.fastest_100s, cols: battingCols({ showSR: true }) },
  { key: 'most_sixes_innings', title: 'Most sixes in an innings',
    rows: d => d.most_sixes_innings, cols: battingCols({ showSixes: true }) },
  { key: 'most_fours_innings', title: 'Most fours in an innings',
    rows: d => d.most_fours_innings, cols: battingCols({ showFours: true }) },
  { key: 'best_strike_rates', title: 'Best strike rates (min 20 balls)',
    rows: d => d.best_strike_rates, cols: battingCols({ showSR: true }) },
]

export default function BatterRecordsPanel({ data, loading, error, refetch, lists }: Props) {
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
            columns={list.cols}
            data={list.rows(data)}
            rowKey={r => `${list.key}-${r.match_id}-${r.runs}-${r.balls}`}
          />
        </div>
      ))}
    </div>
  )
}
