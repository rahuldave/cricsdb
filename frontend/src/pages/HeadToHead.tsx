import { Link } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import PlayerSearch from '../components/PlayerSearch'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import DonutChart from '../components/charts/DonutChart'
import { WISDEN_PHASES } from '../components/charts/palette'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { getHeadToHead } from '../api'
import type { PlayerSearchResult, HeadToHeadResponse, HeadToHeadMatch } from '../types'

const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

export default function HeadToHead() {
  const filters = useFilters()
  const [batterId, setBatterId] = useUrlParam('batter')
  const [bowlerId, setBowlerId] = useUrlParam('bowler')

  const handleBatter = (p: PlayerSearchResult) => setBatterId(p.id)
  const handleBowler = (p: PlayerSearchResult) => setBowlerId(p.id)

  const enabled = !!(batterId && bowlerId)
  // Title set after fetch resolves; on first paint with no selection, show generic.
  const { data, loading, error, refetch } = useFetch<HeadToHeadResponse | null>(
    () => enabled
      ? getHeadToHead(batterId, bowlerId, filters)
      : Promise.resolve(null),
    [batterId, bowlerId, filters.gender, filters.team_type, filters.tournament,
     filters.season_from, filters.season_to],
  )
  useDocumentTitle(
    data ? `${data.batter.name} v ${data.bowler.name}` : enabled ? null : 'Head to Head'
  )

  const matchColumns: Column<HeadToHeadMatch>[] = [
    { key: 'date', label: 'Date', sortable: true, format: (v: any, r: any) => (
      <Link
        to={`/matches/${r.match_id}?highlight_batter=${encodeURIComponent(batterId || '')}&highlight_bowler=${encodeURIComponent(bowlerId || '')}`}
        className="comp-link"
        onClick={e => e.stopPropagation()}>{v || '-'}</Link>
    ) as unknown as string },
    { key: 'tournament', label: 'Tournament' },
    { key: 'venue', label: 'Venue' },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'fours', label: '4s' },
    { key: 'sixes', label: '6s' },
    { key: 'how_out', label: 'Out?', format: (_: any, r: any) => r.dismissed ? (r.how_out || 'yes') : '-' },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex gap-6 items-start mb-8">
        <div className="flex-1">
          <label className="wisden-h2h-label">Batter</label>
          <PlayerSearch role="batter" onSelect={handleBatter} placeholder="Search batter…" />
        </div>
        <span className="wisden-h2h-vs">v</span>
        <div className="flex-1">
          <label className="wisden-h2h-label">Bowler</label>
          <PlayerSearch role="bowler" onSelect={handleBowler} placeholder="Search bowler…" />
        </div>
      </div>

      {!enabled && (
        <div className="wisden-empty">Select both a batter and bowler to view head-to-head stats</div>
      )}

      {enabled && loading && <Spinner label="Loading head-to-head…" size="lg" />}

      {enabled && error && (
        <ErrorBanner
          message={`Could not load head-to-head: ${error}`}
          onRetry={refetch}
        />
      )}

      {enabled && data && !loading && !error && (
        <>
          <h2 className="wisden-page-title">
            {data.batter.name} <span style={{ fontStyle: 'italic', color: 'var(--accent)', fontWeight: 400 }}>v</span> {data.bowler.name}
          </h2>

          <div className="wisden-statrow cols-5">
            <StatCard label="Balls" value={data.summary.balls} />
            <StatCard label="Runs" value={data.summary.runs} />
            <StatCard label="Outs" value={data.summary.dismissals} />
            <StatCard label="Average" value={fmt(data.summary.average)} />
            <StatCard label="Strike Rate" value={fmt(data.summary.strike_rate)} />
          </div>
          <div className="wisden-statrow">
            <StatCard label="Fours" value={data.summary.fours} />
            <StatCard label="Sixes" value={data.summary.sixes} />
            <StatCard label="Dots" value={data.summary.dots} />
            <StatCard label="Dot %" value={data.summary.dot_pct != null ? `${data.summary.dot_pct}%` : '-'} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {data.by_phase.length > 0 && (
              <BarChart
                data={data.by_phase}
                categoryAccessor="phase" valueAccessor={(d: Record<string, any>) => (d.strike_rate as number) ?? 0}
                title="Strike Rate by Phase" categoryLabel="Phase" valueLabel="SR"
                height={280} colorScheme={WISDEN_PHASES} />
            )}
            {Object.keys(data.dismissal_kinds).length > 0 && (
              <DonutChart
                data={Object.entries(data.dismissal_kinds).map(([label, value]) => ({ label, value }))}
                categoryAccessor="label" valueAccessor="value"
                title={`Dismissals (${data.summary.dismissals})`} width={300} height={280} />
            )}
          </div>

          {data.by_season.length > 0 && (
            <div className="mb-8">
              <BarChart
                data={data.by_season.filter(s => s.strike_rate != null)}
                categoryAccessor="season" valueAccessor={(d: Record<string, any>) => d.strike_rate ?? 0}
                title="Strike Rate by Season" categoryLabel="Season" valueLabel="SR"
                height={300} />
            </div>
          )}

          {data.by_over.length > 0 && (
            <div className="mb-8">
              <BarChart
                data={data.by_over.filter(o => o.balls > 0).map(o => ({ ...o, over: `${o.over_number}` }))}
                categoryAccessor="over"
                valueAccessor="runs"
                title="Runs by Over" categoryLabel="Over" valueLabel="Runs"
                height={300} />
            </div>
          )}

          <div>
            <div className="section-head"><span className="section-label">Match by Match</span></div>
            <div className="rule" />
            <DataTable columns={matchColumns} data={data.by_match} />
          </div>
        </>
      )}
    </div>
  )
}
