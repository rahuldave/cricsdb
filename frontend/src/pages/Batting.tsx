import { useState } from 'react'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch, type FetchState } from '../hooks/useFetch'
import PlayerSearch from '../components/PlayerSearch'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import LineChart from '../components/charts/LineChart'
import ScatterChart from '../components/charts/ScatterChart'
import DonutChart from '../components/charts/DonutChart'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import {
  getBatterSummary, getBatterInnings, getBatterVsBowlers, getBatterByOver,
  getBatterByPhase, getBatterBySeason, getBatterDismissals, getBatterInterWicket,
} from '../api'
import type {
  PlayerSearchResult, BattingSummary, BattingInnings, BowlerMatchup,
  OverStats, PhaseStats, SeasonBattingStats, DismissalAnalysis, InterWicketStats,
} from '../types'

// Small helper for the consistent loading/error pattern in each tab.
function TabState({ fetch }: { fetch: FetchState<unknown> }) {
  if (fetch.loading) return <Spinner label="Loading…" />
  if (fetch.error) return <ErrorBanner message={fetch.error} onRetry={fetch.refetch} />
  return null
}

const tabs = ['By Season', 'By Over', 'By Phase', 'vs Bowlers', 'Dismissals', 'Inter-Wicket', 'Innings List'] as const
const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

export default function Batting() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const setUrlParams = useSetUrlParams()

  const [inningsOffset, setInningsOffset] = useState(0)
  const [selectedBowlerId, setSelectedBowlerId] = useState<string | null>(null)

  const handleSelect = (p: PlayerSearchResult) => {
    setUrlParams({ player: p.id, tab: 'By Season' })
  }

  const filterDeps = [
    playerId, filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
  ]

  // Summary drives the page header — page-level state
  const summaryFetch = useFetch<BattingSummary | null>(
    () => playerId ? getBatterSummary(playerId, filters) : Promise.resolve(null),
    filterDeps,
  )
  const summary = summaryFetch.data

  // Per-tab fetches: each is gated on `activeTab === '...'` so only the
  // visible tab does network work. Switching tabs re-runs the gated fetch.
  const seasonFetch = useFetch<{ by_season: SeasonBattingStats[] } | null>(
    () => playerId && activeTab === 'By Season'
      ? getBatterBySeason(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const seasonData = seasonFetch.data?.by_season ?? []

  const overFetch = useFetch<{ by_over: OverStats[] } | null>(
    () => playerId && activeTab === 'By Over'
      ? getBatterByOver(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const overData = overFetch.data?.by_over ?? []

  const phaseFetch = useFetch<{ by_phase: PhaseStats[] } | null>(
    () => playerId && activeTab === 'By Phase'
      ? getBatterByPhase(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const phaseData = phaseFetch.data?.by_phase ?? []

  const matchupsFetch = useFetch<{ matchups: BowlerMatchup[] } | null>(
    () => playerId && activeTab === 'vs Bowlers'
      ? getBatterVsBowlers(playerId, { ...filters, min_balls: 6 })
      : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const bowlerMatchups = matchupsFetch.data?.matchups ?? []

  const dismissalsFetch = useFetch<DismissalAnalysis | null>(
    () => playerId && activeTab === 'Dismissals'
      ? getBatterDismissals(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const dismissals = dismissalsFetch.data

  const interWicketFetch = useFetch<{ inter_wicket: InterWicketStats[] } | null>(
    () => playerId && activeTab === 'Inter-Wicket'
      ? getBatterInterWicket(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const interWicket = interWicketFetch.data?.inter_wicket ?? []

  const inningsFetch = useFetch<{ innings: BattingInnings[]; total: number } | null>(
    () => playerId && activeTab === 'Innings List'
      ? getBatterInnings(playerId, { ...filters, limit: 50, offset: inningsOffset })
      : Promise.resolve(null),
    [...filterDeps, activeTab, inningsOffset],
  )
  const innings = inningsFetch.data?.innings ?? []
  const inningsTotal = inningsFetch.data?.total ?? 0

  const inningsColumns: Column<BattingInnings>[] = [
    { key: 'date', label: 'Date', sortable: true },
    { key: 'opponent', label: 'Opponent', sortable: true },
    { key: 'tournament', label: 'Tournament' },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'fours', label: '4s' },
    { key: 'sixes', label: '6s' },
    { key: 'strike_rate', label: 'SR', sortable: true, format: (v: any) => fmt(v) },
    { key: 'how_out', label: 'Dismissal', format: (_: any, r: any) => r.not_out ? 'not out' : String(r.how_out || '-') },
  ]

  const bowlerColumns: Column<BowlerMatchup>[] = [
    { key: 'bowler_name', label: 'Bowler', sortable: true },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'dismissals', label: 'Outs', sortable: true },
    { key: 'strike_rate', label: 'SR', sortable: true, format: (v: any) => fmt(v) },
    { key: 'average', label: 'Avg', sortable: true, format: (v: any) => fmt(v) },
    { key: 'balls_per_boundary', label: 'B/Bnd', sortable: true, format: (v: any) => fmt(v) },
  ]

  return (
    <div>
      <div className="mb-6">
        <PlayerSearch role="batter" onSelect={handleSelect} placeholder="Search for a batter..." />
      </div>

      {!playerId && <div className="text-center text-gray-400 py-16">Search for a batter to view stats</div>}

      {playerId && summaryFetch.loading && <Spinner label="Loading batter…" size="lg" />}

      {playerId && summaryFetch.error && (
        <ErrorBanner
          message={`Could not load batter: ${summaryFetch.error}`}
          onRetry={summaryFetch.refetch}
        />
      )}

      {playerId && summary && !summaryFetch.loading && (
        <>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">{summary.name}</h2>
          <div className="grid grid-cols-5 gap-3 mb-2">
            <StatCard label="Runs" value={summary.runs} />
            <StatCard label="Average" value={fmt(summary.average)} />
            <StatCard label="Strike Rate" value={fmt(summary.strike_rate)} />
            <StatCard label="Innings" value={summary.innings} />
            <StatCard label="Boundaries" value={summary.boundaries} subtitle={`${summary.fours} 4s, ${summary.sixes} 6s`} />
          </div>
          <div className="grid grid-cols-5 gap-3 mb-6">
            <StatCard label="B/Four" value={fmt(summary.balls_per_four)} />
            <StatCard label="B/Six" value={fmt(summary.balls_per_six)} />
            <StatCard label="B/Boundary" value={fmt(summary.balls_per_boundary)} />
            <StatCard label="Dot %" value={summary.dot_pct != null ? `${summary.dot_pct}%` : '-'} />
            <StatCard label="50s / 100s" value={`${summary.fifties} / ${summary.hundreds}`} />
          </div>

          <div className="border-b border-gray-200 mb-4">
            <div className="flex gap-1 overflow-x-auto">
              {tabs.map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 ${activeTab === tab ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                >{tab}</button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg border p-6 shadow-sm">
            {activeTab === 'By Season' && (
              <>
                <TabState fetch={seasonFetch as FetchState<unknown>} />
                {!seasonFetch.loading && !seasonFetch.error && seasonData.length > 0 && (
                  <div className="flex gap-6 flex-wrap">
                    <BarChart data={seasonData} categoryAccessor="season" valueAccessor="runs"
                      title="Runs by Season" categoryLabel="Season" valueLabel="Runs"
                      width={600} height={350} colorScheme={['#3b82f6']} />
                    <BarChart data={seasonData.filter(s => s.strike_rate != null)}
                      categoryAccessor="season" valueAccessor={(d: Record<string, any>) => d.strike_rate ?? 0}
                      title="Strike Rate by Season" categoryLabel="Season" valueLabel="Strike Rate"
                      width={600} height={350} colorScheme={['#10b981']} />
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
                    categoryAccessor="over" valueAccessor={(d: Record<string, any>) => (d.strike_rate as number) ?? 0}
                    title="Strike Rate by Over" categoryLabel="Over" valueLabel="Strike Rate"
                    colorBy="phase" colorScheme={['#3b82f6', '#22c55e', '#ef4444']}
                    width={700} height={350} />
                )}
              </>
            )}

            {activeTab === 'By Phase' && (
              <>
                <TabState fetch={phaseFetch as FetchState<unknown>} />
                {!phaseFetch.loading && !phaseFetch.error && phaseData.length > 0 && (
                  <div className="grid grid-cols-3 gap-4">
                    {phaseData.map(p => (
                      <div key={p.phase} className="text-center">
                        <h3 className="font-semibold text-gray-700 mb-2 capitalize">{p.phase}</h3>
                        <div className="text-sm text-gray-500">Overs {p.overs}</div>
                        <div className="grid grid-cols-2 gap-2 mt-2 text-sm">
                          <div><span className="text-gray-500">Runs:</span> {p.runs}</div>
                          <div><span className="text-gray-500">Balls:</span> {p.balls}</div>
                          <div><span className="text-gray-500">SR:</span> {fmt(p.strike_rate)}</div>
                          <div><span className="text-gray-500">Dots:</span> {fmt(p.dot_pct)}%</div>
                          <div><span className="text-gray-500">4s:</span> {p.fours}</div>
                          <div><span className="text-gray-500">6s:</span> {p.sixes}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {activeTab === 'vs Bowlers' && (
              <>
                <TabState fetch={matchupsFetch as FetchState<unknown>} />
                {!matchupsFetch.loading && !matchupsFetch.error && bowlerMatchups.length > 0 && (() => {
                  const valid = bowlerMatchups.filter(m => m.strike_rate != null && m.average != null)
                  // Top 8 by balls faced get a name label directly on the chart.
                  // Semiotic v3 uses `widget` annotations anchored via the same field
                  // names as the chart's accessors (here: strike_rate and average).
                  const topByBalls = [...valid].sort((a, b) => (b.balls ?? 0) - (a.balls ?? 0)).slice(0, 8)
                  const annotations: Record<string, any>[] = topByBalls.map(m => ({
                    type: 'widget',
                    strike_rate: m.strike_rate,
                    average: m.average,
                    dy: -12,
                    content: (
                      <span style={{
                        fontSize: 11, fontWeight: 600, color: '#1f2937',
                        background: 'rgba(255,255,255,0.45)', padding: '0 3px',
                        borderRadius: 2, whiteSpace: 'nowrap',
                        textShadow: '0 0 2px rgba(255,255,255,0.9)',
                      }}>{m.bowler_name}</span>
                    ),
                  }))
                  // If a row is selected, draw a highlight ring around it.
                  // Semiotic v3's `enclose` needs >= 2 coordinates (it uses
                  // d3.packEnclose for a hull), so for a single-point ring
                  // use `highlight` which filters chart data by field/value.
                  const selected = selectedBowlerId
                    ? valid.find(m => m.bowler_id === selectedBowlerId)
                    : null
                  if (selected) {
                    annotations.push({
                      type: 'highlight',
                      field: 'bowler_id',
                      value: selectedBowlerId,
                      color: '#dc2626',
                      r: 14,
                    })
                    // Use `label` (pure SVG text via d3-annotation) rather
                    // than `widget` (foreignObject + HTML span). Safari has
                    // long-standing bugs reusing foreignObject contents
                    // when React props change with the same key, so the
                    // selected name pill stays stale. The top-N labels
                    // above don't change, so they can stay as widgets.
                    annotations.push({
                      type: 'label',
                      strike_rate: selected.strike_rate,
                      average: selected.average,
                      label: selected.bowler_name,
                      dx: 24, dy: -28,
                      color: '#dc2626',
                    })
                  }
                  return (
                    <div>
                      <p className="text-xs text-gray-500 mb-2">
                        Hover any dot to see the bowler. Top 8 by balls faced are labelled.
                        Click a row in the table to find that bowler on the chart.
                      </p>
                      <ScatterChart
                        data={valid}
                        xAccessor="strike_rate"
                        yAccessor="average"
                        sizeBy="balls"
                        title="SR vs Average (dot size = balls faced)"
                        xLabel="Strike Rate" yLabel="Average" width={600} height={400}
                        tooltip={{
                          title: 'bowler_name',
                          fields: ['balls', 'runs', 'dismissals', 'strike_rate', 'average'],
                        }}
                        annotations={annotations}
                        pointIdAccessor="bowler_id"
                      />
                      <div className="mt-4">
                        <DataTable
                          columns={bowlerColumns}
                          data={bowlerMatchups}
                          rowKey={(r: Record<string, any>) => r.bowler_id}
                          highlightKey={selectedBowlerId}
                          onRowClick={(r: Record<string, any>) => setSelectedBowlerId(r.bowler_id)}
                        />
                      </div>
                    </div>
                  )
                })()}
              </>
            )}

            {activeTab === 'Dismissals' && (
              <>
                <TabState fetch={dismissalsFetch as FetchState<unknown>} />
                {!dismissalsFetch.loading && !dismissalsFetch.error && dismissals && (
                  <div className="flex gap-6 flex-wrap">
                    <DonutChart
                      data={Object.entries(dismissals.by_kind).map(([label, value]) => ({ label, value }))}
                      categoryAccessor="label" valueAccessor="value"
                      title={`Dismissals (${dismissals.total_dismissals})`} width={350} height={350} />
                    <BarChart
                      data={dismissals.by_over.filter(o => o.dismissals > 0)}
                      categoryAccessor={(d: Record<string, any>) => String(d.over_number)}
                      valueAccessor="dismissals"
                      title="Dismissals by Over" categoryLabel="Over" valueLabel="Dismissals"
                      width={500} height={300} colorScheme={['#ef4444']} />
                  </div>
                )}
              </>
            )}

            {activeTab === 'Inter-Wicket' && (
              <>
                <TabState fetch={interWicketFetch as FetchState<unknown>} />
                {!interWicketFetch.loading && !interWicketFetch.error && interWicket.length > 0 && (
                  <div className="flex gap-6 flex-wrap">
                    <LineChart
                      data={interWicket.map(iw => ({ x: iw.wickets_down, y: iw.strike_rate ?? 0 }))}
                      xAccessor="x" yAccessor="y"
                      title="Strike Rate by Wickets Down" xLabel="Wickets Down" yLabel="Strike Rate"
                      width={500} height={350} showPoints />
                    <BarChart
                      data={interWicket} categoryAccessor={(d: Record<string, any>) => String(d.wickets_down)}
                      valueAccessor="runs"
                      title="Total Runs by Wickets Down" categoryLabel="Wickets Down" valueLabel="Runs"
                      width={500} height={350} colorScheme={['#8b5cf6']} />
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
