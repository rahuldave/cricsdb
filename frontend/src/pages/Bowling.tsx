import { useState, useEffect } from 'react'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import PlayerSearch from '../components/PlayerSearch'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import ScatterChart from '../components/charts/ScatterChart'
import DonutChart from '../components/charts/DonutChart'
import {
  getBowlerSummary, getBowlerInnings, getBowlerVsBatters, getBowlerByOver,
  getBowlerByPhase, getBowlerBySeason, getBowlerWickets,
} from '../api'
import type {
  PlayerSearchResult, BowlingSummary, BowlingInnings, BatterMatchup,
  OverStats, PhaseStats, SeasonBattingStats, WicketAnalysis,
} from '../types'

const tabs = ['By Season', 'By Over', 'By Phase', 'vs Batters', 'Wickets', 'Innings List'] as const
const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

export default function Bowling() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const setUrlParams = useSetUrlParams()

  const [summary, setSummary] = useState<BowlingSummary | null>(null)
  const [seasonData, setSeasonData] = useState<SeasonBattingStats[]>([])
  const [overData, setOverData] = useState<OverStats[]>([])
  const [phaseData, setPhaseData] = useState<PhaseStats[]>([])
  const [batterMatchups, setBatterMatchups] = useState<BatterMatchup[]>([])
  const [wicketData, setWicketData] = useState<WicketAnalysis | null>(null)
  const [innings, setInnings] = useState<BowlingInnings[]>([])
  const [inningsTotal, setInningsTotal] = useState(0)
  const [inningsOffset, setInningsOffset] = useState(0)

  const handleSelect = (p: PlayerSearchResult) => {
    setUrlParams({ player: p.id, tab: 'By Season' })
  }

  useEffect(() => {
    if (!playerId) return
    setSummary(null)
    getBowlerSummary(playerId, filters).then(setSummary).catch(() => {})
  }, [playerId, filters.gender, filters.team_type, filters.tournament, filters.season_from, filters.season_to])

  useEffect(() => {
    if (!playerId) return
    if (activeTab === 'By Season') getBowlerBySeason(playerId, filters).then(d => setSeasonData(d.by_season)).catch(() => {})
    if (activeTab === 'By Over') getBowlerByOver(playerId, filters).then(d => setOverData(d.by_over)).catch(() => {})
    if (activeTab === 'By Phase') getBowlerByPhase(playerId, filters).then(d => setPhaseData(d.by_phase)).catch(() => {})
    if (activeTab === 'vs Batters') getBowlerVsBatters(playerId, { ...filters, min_balls: 6 }).then(d => setBatterMatchups(d.matchups)).catch(() => {})
    if (activeTab === 'Wickets') getBowlerWickets(playerId, filters).then(setWicketData).catch(() => {})
    if (activeTab === 'Innings List') {
      getBowlerInnings(playerId, { ...filters, limit: 50, offset: inningsOffset }).then(d => {
        setInnings(d.innings); setInningsTotal(d.total)
      }).catch(() => {})
    }
  }, [playerId, activeTab, inningsOffset, filters.gender, filters.team_type, filters.tournament, filters.season_from, filters.season_to])

  const inningsColumns: Column<BowlingInnings>[] = [
    { key: 'date', label: 'Date', sortable: true },
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
    <div>
      <div className="mb-6">
        <PlayerSearch role="bowler" onSelect={handleSelect} placeholder="Search for a bowler..." />
      </div>

      {!playerId && <div className="text-center text-gray-400 py-16">Search for a bowler to view stats</div>}

      {playerId && summary && (
        <>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">{summary.name}</h2>
          <div className="grid grid-cols-5 gap-3 mb-2">
            <StatCard label="Wickets" value={summary.wickets} />
            <StatCard label="Average" value={fmt(summary.average)} />
            <StatCard label="Economy" value={fmt(summary.economy)} />
            <StatCard label="Overs" value={summary.overs} />
            <StatCard label="Strike Rate" value={fmt(summary.strike_rate)} />
          </div>
          <div className="grid grid-cols-5 gap-3 mb-6">
            <StatCard label="B/Four" value={fmt(summary.balls_per_four)} />
            <StatCard label="B/Six" value={fmt(summary.balls_per_six)} />
            <StatCard label="B/Boundary" value={fmt(summary.balls_per_boundary)} />
            <StatCard label="Dot %" value={summary.dot_pct != null ? `${summary.dot_pct}%` : '-'} />
            <StatCard label="Best Figures" value={summary.best_figures || '-'} />
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
            {activeTab === 'By Season' && seasonData.length > 0 && (
              <div className="flex gap-6 flex-wrap">
                <BarChart data={seasonData} categoryAccessor="season" valueAccessor={(d: Record<string, any>) => (d.dismissals as number) ?? 0}
                  title="Wickets by Season" categoryLabel="Season" valueLabel="Wickets"
                  width={600} height={350} colorScheme={['#ef4444']} />
                <BarChart data={seasonData.filter(s => s.strike_rate != null)}
                  categoryAccessor="season" valueAccessor={(d: Record<string, any>) => d.strike_rate ?? 0}
                  title="Bowling Strike Rate by Season" categoryLabel="Season" valueLabel="SR"
                  width={600} height={350} colorScheme={['#f59e0b']} />
              </div>
            )}

            {activeTab === 'By Over' && overData.length > 0 && (
              <BarChart
                data={overData.map(o => ({
                  ...o, over: `${o.over_number}`,
                  phase: o.over_number <= 6 ? 'Powerplay' : o.over_number <= 15 ? 'Middle' : 'Death',
                }))}
                categoryAccessor="over"
                valueAccessor={(d: Record<string, any>) => {
                  const balls = d.balls as number
                  const runs = d.runs as number
                  return balls > 0 ? (runs / balls) * 6 : 0
                }}
                title="Economy by Over" categoryLabel="Over" valueLabel="Economy"
                colorBy="phase" colorScheme={['#3b82f6', '#22c55e', '#ef4444']}
                width={700} height={350} />
            )}

            {activeTab === 'By Phase' && phaseData.length > 0 && (
              <div className="grid grid-cols-3 gap-4">
                {phaseData.map(p => (
                  <div key={p.phase} className="text-center">
                    <h3 className="font-semibold text-gray-700 mb-2 capitalize">{p.phase}</h3>
                    <div className="text-sm text-gray-500">Overs {p.overs}</div>
                    <div className="grid grid-cols-2 gap-2 mt-2 text-sm">
                      <div><span className="text-gray-500">Balls:</span> {p.balls}</div>
                      <div><span className="text-gray-500">Runs:</span> {p.runs}</div>
                      <div><span className="text-gray-500">SR:</span> {fmt(p.strike_rate)}</div>
                      <div><span className="text-gray-500">Dots:</span> {fmt(p.dot_pct)}%</div>
                      <div><span className="text-gray-500">4s:</span> {p.fours}</div>
                      <div><span className="text-gray-500">6s:</span> {p.sixes}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === 'vs Batters' && batterMatchups.length > 0 && (
              <div>
                <ScatterChart
                  data={batterMatchups.filter(m => m.economy != null && m.strike_rate != null)}
                  xAccessor={(d: Record<string, any>) => (d.economy as number) ?? 0}
                  yAccessor={(d: Record<string, any>) => (d.strike_rate as number) ?? 0}
                  sizeBy={(d: Record<string, any>) => (d.balls as number) ?? 6}
                  title="Economy vs SR (dot size = balls bowled)"
                  xLabel="Economy" yLabel="Strike Rate" width={600} height={400} />
                <div className="mt-4">
                  <DataTable columns={batterColumns} data={batterMatchups} />
                </div>
              </div>
            )}

            {activeTab === 'Wickets' && wicketData && (
              <div className="flex gap-6 flex-wrap">
                <DonutChart
                  data={Object.entries(wicketData.by_kind).map(([label, value]) => ({ label, value }))}
                  categoryAccessor="label" valueAccessor="value"
                  title={`Wicket Types (${wicketData.total_wickets})`} width={350} height={350} />
                <BarChart
                  data={Object.entries(wicketData.by_phase).map(([phase, wkts]) => ({ phase, wickets: wkts }))}
                  categoryAccessor="phase" valueAccessor="wickets"
                  title="Wickets by Phase" categoryLabel="Phase" valueLabel="Wickets"
                  width={400} height={300} colorScheme={['#f59e0b']} />
              </div>
            )}

            {activeTab === 'Innings List' && (
              <DataTable columns={inningsColumns} data={innings}
                pagination={{ total: inningsTotal, limit: 50, offset: inningsOffset, onPage: setInningsOffset }} />
            )}
          </div>
        </>
      )}
    </div>
  )
}
