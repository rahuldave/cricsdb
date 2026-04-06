import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch, type FetchState } from '../hooks/useFetch'
import PlayerSearch from '../components/PlayerSearch'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import ScatterChart from '../components/charts/ScatterChart'
import DonutChart from '../components/charts/DonutChart'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import {
  getBowlerSummary, getBowlerInnings, getBowlerVsBatters, getBowlerByOver,
  getBowlerByPhase, getBowlerBySeason, getBowlerWickets,
} from '../api'
import type {
  PlayerSearchResult, BowlingSummary, BowlingInnings, BatterMatchup,
  OverStats, PhaseStats, WicketAnalysis,
} from '../types'

function TabState({ fetch }: { fetch: FetchState<unknown> }) {
  if (fetch.loading) return <Spinner label="Loading…" />
  if (fetch.error) return <ErrorBanner message={fetch.error} onRetry={fetch.refetch} />
  return null
}

const tabs = ['By Season', 'By Over', 'By Phase', 'vs Batters', 'Wickets', 'Innings List'] as const
const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

export default function Bowling() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const setUrlParams = useSetUrlParams()

  const [inningsOffset, setInningsOffset] = useState(0)
  const [selectedBatterId, setSelectedBatterId] = useState<string | null>(null)

  const handleSelect = (p: PlayerSearchResult) => {
    setUrlParams({ player: p.id, tab: 'By Season' })
  }

  const filterDeps = [
    playerId, filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
  ]

  const summaryFetch = useFetch<BowlingSummary | null>(
    () => playerId ? getBowlerSummary(playerId, filters) : Promise.resolve(null),
    filterDeps,
  )
  const summary = summaryFetch.data

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seasonFetch = useFetch<{ by_season: any[] } | null>(
    () => playerId && activeTab === 'By Season'
      ? getBowlerBySeason(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const seasonData = seasonFetch.data?.by_season ?? []

  const overFetch = useFetch<{ by_over: OverStats[] } | null>(
    () => playerId && activeTab === 'By Over'
      ? getBowlerByOver(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const overData = overFetch.data?.by_over ?? []

  const phaseFetch = useFetch<{ by_phase: PhaseStats[] } | null>(
    () => playerId && activeTab === 'By Phase'
      ? getBowlerByPhase(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const phaseData = phaseFetch.data?.by_phase ?? []

  const matchupsFetch = useFetch<{ matchups: BatterMatchup[] } | null>(
    () => playerId && activeTab === 'vs Batters'
      ? getBowlerVsBatters(playerId, { ...filters, min_balls: 6 })
      : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const batterMatchups = matchupsFetch.data?.matchups ?? []

  const wicketsFetch = useFetch<WicketAnalysis | null>(
    () => playerId && activeTab === 'Wickets'
      ? getBowlerWickets(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const wicketData = wicketsFetch.data

  const inningsFetch = useFetch<{ innings: BowlingInnings[]; total: number } | null>(
    () => playerId && activeTab === 'Innings List'
      ? getBowlerInnings(playerId, { ...filters, limit: 50, offset: inningsOffset })
      : Promise.resolve(null),
    [...filterDeps, activeTab, inningsOffset],
  )
  const innings = inningsFetch.data?.innings ?? []
  const inningsTotal = inningsFetch.data?.total ?? 0

  const inningsColumns: Column<BowlingInnings>[] = [
    { key: 'date', label: 'Date', sortable: true, format: (v: any, r: any) => (
      <Link to={`/matches/${r.match_id}?highlight_bowler=${encodeURIComponent(playerId || '')}`}
        className="comp-link" onClick={e => e.stopPropagation()}>{v || '-'}</Link>
    ) as unknown as string },
    { key: 'opponent', label: 'Opponent', sortable: true },
    { key: 'tournament', label: 'Tournament' },
    { key: 'overs', label: 'Overs' },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'wickets', label: 'Wkts', sortable: true },
    { key: 'economy', label: 'Econ', sortable: true, format: (v: any) => fmt(v) },
    { key: 'dots', label: 'Dots' },
  ]

  const batterColumns: Column<BatterMatchup>[] = [
    { key: 'batter_name', label: 'Batter', sortable: true },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'runs_conceded', label: 'Runs', sortable: true },
    { key: 'wickets', label: 'Wkts', sortable: true },
    { key: 'economy', label: 'Econ', sortable: true, format: (v: any) => fmt(v) },
    { key: 'average', label: 'Avg', sortable: true, format: (v: any) => fmt(v) },
    { key: 'balls_per_boundary', label: 'B/Bnd', sortable: true, format: (v: any) => fmt(v) },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <PlayerSearch role="bowler" onSelect={handleSelect} placeholder="Search for a bowler…" />
      </div>

      {!playerId && <div className="wisden-empty">Search for a bowler to view stats</div>}

      {playerId && summaryFetch.loading && <Spinner label="Loading bowler…" size="lg" />}

      {playerId && summaryFetch.error && (
        <ErrorBanner
          message={`Could not load bowler: ${summaryFetch.error}`}
          onRetry={summaryFetch.refetch}
        />
      )}

      {playerId && summary && !summaryFetch.loading && (
        <>
          <h2 className="wisden-page-title">{summary.name}</h2>
          <div className="wisden-statrow cols-5">
            <StatCard label="Wickets" value={summary.wickets} />
            <StatCard label="Average" value={fmt(summary.average)} />
            <StatCard label="Economy" value={fmt(summary.economy)} />
            <StatCard label="Overs" value={summary.overs} />
            <StatCard label="Strike Rate" value={fmt(summary.strike_rate)} />
          </div>
          <div className="wisden-statrow cols-5">
            <StatCard label="B/Four" value={fmt(summary.balls_per_four)} />
            <StatCard label="B/Six" value={fmt(summary.balls_per_six)} />
            <StatCard label="B/Boundary" value={fmt(summary.balls_per_boundary)} />
            <StatCard label="Dot %" value={summary.dot_pct != null ? `${summary.dot_pct}%` : '-'} />
            <StatCard label="Best Figures" value={summary.best_figures || '-'} />
          </div>

          <div className="wisden-tabs">
            {tabs.map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`wisden-tab${activeTab === tab ? ' is-active' : ''}`}
              >{tab}</button>
            ))}
          </div>

          <div>
            {activeTab === 'By Season' && (
              <>
                <TabState fetch={seasonFetch as FetchState<unknown>} />
                {!seasonFetch.loading && !seasonFetch.error && seasonData.length > 0 && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <BarChart data={seasonData} categoryAccessor="season" valueAccessor={(d: Record<string, any>) => (d.wickets as number) ?? (d.dismissals as number) ?? 0}
                      title="Wickets by Season" categoryLabel="Season" valueLabel="Wickets"
                      height={350} colorScheme={['#ef4444']} />
                    <BarChart data={seasonData.filter(s => s.strike_rate != null)}
                      categoryAccessor="season" valueAccessor={(d: Record<string, any>) => d.strike_rate ?? 0}
                      title="Bowling Strike Rate by Season" categoryLabel="Season" valueLabel="SR"
                      height={350} colorScheme={['#f59e0b']} />
                  </div>
                )}
              </>
            )}

            {activeTab === 'By Over' && (
              <>
                <TabState fetch={overFetch as FetchState<unknown>} />
                {!overFetch.loading && !overFetch.error && overData.length > 0 && (
                  <BarChart
                    data={overData.map(o => ({
                      ...o, over: `${o.over_number}`,
                      phase: o.over_number <= 6 ? 'Powerplay' : o.over_number <= 15 ? 'Middle' : 'Death',
                    }))}
                    categoryAccessor="over"
                    valueAccessor={(d: Record<string, any>) => (d.economy as number) ?? 0}
                    title="Economy by Over" categoryLabel="Over" valueLabel="Economy"
                    colorBy="phase" colorScheme={['#3b82f6', '#22c55e', '#ef4444']}
                    height={350} />
                )}
              </>
            )}

            {activeTab === 'By Phase' && (
              <>
                <TabState fetch={phaseFetch as FetchState<unknown>} />
                {!phaseFetch.loading && !phaseFetch.error && phaseData.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-0">
                    {phaseData.map(p => (
                      <div key={p.phase} className="wisden-phaseblock">
                        <h3>{p.phase}</h3>
                        <div className="wisden-phaseblock-overs">Overs {p.overs}</div>
                        <div className="wisden-phaseblock-grid">
                          <div><span className="lbl">Balls</span></div><div className="num">{p.balls}</div>
                          <div><span className="lbl">Runs</span></div><div className="num">{p.runs}</div>
                          <div><span className="lbl">SR</span></div><div className="num">{fmt(p.strike_rate)}</div>
                          <div><span className="lbl">Dots</span></div><div className="num">{fmt(p.dot_pct)}%</div>
                          <div><span className="lbl">4s</span></div><div className="num">{p.fours}</div>
                          <div><span className="lbl">6s</span></div><div className="num">{p.sixes}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {activeTab === 'vs Batters' && (
              <>
                <TabState fetch={matchupsFetch as FetchState<unknown>} />
                {!matchupsFetch.loading && !matchupsFetch.error && batterMatchups.length > 0 && (() => {
                  // Switched Y axis from strike_rate (balls/wicket) to average
                  // (runs/wicket) — average is the more familiar bowling stat
                  // and "balls per wicket" was confusingly framed.
                  //
                  // Also FLIPPED the Y axis via frameProps.yExtent so low
                  // values appear at the TOP of the chart. With the flip,
                  // both axes have "good for bowler" toward the top-left:
                  //   left  = low economy = cheap
                  //   top   = low average = wickets cost few runs
                  // The visually prominent top-left corner is now the
                  // "dominant bowler" zone, fixing the previous problem
                  // where high values (bad for bowler) were on top.
                  const valid = batterMatchups.filter(m => m.economy != null && m.average != null)
                  const maxAvg = Math.max(...valid.map(m => m.average ?? 0), 30)
                  const topByBalls = [...valid].sort((a, b) => (b.balls ?? 0) - (a.balls ?? 0)).slice(0, 8)
                  const annotations: Record<string, any>[] = topByBalls.map(m => ({
                    type: 'widget',
                    economy: m.economy,
                    average: m.average,
                    dy: -12,
                    content: (
                      <span style={{
                        fontSize: 11, fontWeight: 600, color: '#1f2937',
                        background: 'rgba(255,255,255,0.45)', padding: '0 3px',
                        borderRadius: 2, whiteSpace: 'nowrap',
                        textShadow: '0 0 2px rgba(255,255,255,0.9)',
                      }}>{m.batter_name}</span>
                    ),
                  }))
                  const selected = selectedBatterId
                    ? valid.find(m => m.batter_id === selectedBatterId)
                    : null
                  if (selected) {
                    annotations.push({
                      type: 'highlight',
                      field: 'batter_id',
                      value: selectedBatterId,
                      color: '#dc2626',
                      r: 14,
                    })
                    annotations.push({
                      type: 'label',
                      economy: selected.economy,
                      average: selected.average,
                      label: selected.batter_name,
                      dx: 24, dy: -28,
                      color: '#dc2626',
                    })
                  }
                  return (
                    <div>
                      <p className="wisden-tab-help">
                        Hover any dot to see the batter. Top 8 by balls bowled are labelled.
                        Click a row in the table to find that batter on the chart.
                        <span style={{ opacity: 0.7 }}> Top-left corner = bowler dominated (low econ + low avg).</span>
                      </p>
                      <ScatterChart
                        data={valid}
                        xAccessor="economy"
                        yAccessor="average"
                        sizeBy="balls"
                        title="Economy vs Average (dot size = balls bowled)"
                        xLabel="Economy" yLabel="Average (runs / wicket)" height={400}
                        tooltip={{
                          title: 'batter_name',
                          fields: ['balls', 'runs_conceded', 'wickets', 'economy', 'average'],
                        }}
                        annotations={annotations}
                        pointIdAccessor="batter_id"
                        // Reverse Y so low average (good for bowler) sits at the top.
                        frameProps={{ yExtent: [maxAvg * 1.05, 0] }}
                      />
                      <div className="mt-4">
                        <DataTable
                          columns={batterColumns}
                          data={batterMatchups}
                          rowKey={(r: Record<string, any>) => r.batter_id}
                          highlightKey={selectedBatterId}
                          onRowClick={(r: Record<string, any>) => setSelectedBatterId(r.batter_id)}
                        />
                      </div>
                    </div>
                  )
                })()}
              </>
            )}

            {activeTab === 'Wickets' && (
              <>
                <TabState fetch={wicketsFetch as FetchState<unknown>} />
                {!wicketsFetch.loading && !wicketsFetch.error && wicketData && (
                  <div className="grid grid-cols-1 lg:grid-cols-[350px_minmax(0,1fr)] gap-6 items-start">
                    <DonutChart
                      data={Object.entries(wicketData.by_kind).map(([label, value]) => ({ label, value }))}
                      categoryAccessor="label" valueAccessor="value"
                      title={`Wicket Types (${wicketData.total_wickets})`} width={350} height={350} />
                    <BarChart
                      data={Object.entries(wicketData.by_phase).map(([phase, wkts]) => ({ phase, wickets: wkts }))}
                      categoryAccessor="phase" valueAccessor="wickets"
                      title="Wickets by Phase" categoryLabel="Phase" valueLabel="Wickets"
                      height={300} colorScheme={['#f59e0b']} />
                  </div>
                )}
              </>
            )}

            {activeTab === 'Innings List' && (
              <>
                <TabState fetch={inningsFetch as FetchState<unknown>} />
                {!inningsFetch.loading && !inningsFetch.error && (
                  <DataTable columns={inningsColumns} data={innings}
                    pagination={{ total: inningsTotal, limit: 50, offset: inningsOffset, onPage: setInningsOffset }} />
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
