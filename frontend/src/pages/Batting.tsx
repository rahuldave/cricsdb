import { useState, useEffect } from 'react'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import PlayerSearch from '../components/PlayerSearch'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import LineChart from '../components/charts/LineChart'
import ScatterChart from '../components/charts/ScatterChart'
import DonutChart from '../components/charts/DonutChart'
import {
  getBatterSummary, getBatterInnings, getBatterVsBowlers, getBatterByOver,
  getBatterByPhase, getBatterBySeason, getBatterDismissals, getBatterInterWicket,
} from '../api'
import type {
  PlayerSearchResult, BattingSummary, BattingInnings, BowlerMatchup,
  OverStats, PhaseStats, SeasonBattingStats, DismissalAnalysis, InterWicketStats,
} from '../types'

const tabs = ['By Season', 'By Over', 'By Phase', 'vs Bowlers', 'Dismissals', 'Inter-Wicket', 'Innings List'] as const
const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

export default function Batting() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const setUrlParams = useSetUrlParams()

  const [summary, setSummary] = useState<BattingSummary | null>(null)
  const [seasonData, setSeasonData] = useState<SeasonBattingStats[]>([])
  const [overData, setOverData] = useState<OverStats[]>([])
  const [phaseData, setPhaseData] = useState<PhaseStats[]>([])
  const [bowlerMatchups, setBowlerMatchups] = useState<BowlerMatchup[]>([])
  const [dismissals, setDismissals] = useState<DismissalAnalysis | null>(null)
  const [interWicket, setInterWicket] = useState<InterWicketStats[]>([])
  const [innings, setInnings] = useState<BattingInnings[]>([])
  const [inningsTotal, setInningsTotal] = useState(0)
  const [inningsOffset, setInningsOffset] = useState(0)

  const handleSelect = (p: PlayerSearchResult) => {
    setUrlParams({ player: p.id, tab: 'By Season' })
  }

  useEffect(() => {
    if (!playerId) return
    setSummary(null)
    getBatterSummary(playerId, filters).then(setSummary).catch(() => {})
  }, [playerId, filters.gender, filters.team_type, filters.tournament, filters.season_from, filters.season_to])

  useEffect(() => {
    if (!playerId) return
    if (activeTab === 'By Season') getBatterBySeason(playerId, filters).then(d => setSeasonData(d.by_season)).catch(() => {})
    if (activeTab === 'By Over') getBatterByOver(playerId, filters).then(d => setOverData(d.by_over)).catch(() => {})
    if (activeTab === 'By Phase') getBatterByPhase(playerId, filters).then(d => setPhaseData(d.by_phase)).catch(() => {})
    if (activeTab === 'vs Bowlers') getBatterVsBowlers(playerId, { ...filters, min_balls: 6 }).then(d => setBowlerMatchups(d.matchups)).catch(() => {})
    if (activeTab === 'Dismissals') getBatterDismissals(playerId, filters).then(setDismissals).catch(() => {})
    if (activeTab === 'Inter-Wicket') getBatterInterWicket(playerId, filters).then(d => setInterWicket(d.inter_wicket)).catch(() => {})
    if (activeTab === 'Innings List') {
      getBatterInnings(playerId, { ...filters, limit: 50, offset: inningsOffset }).then(d => {
        setInnings(d.innings); setInningsTotal(d.total)
      }).catch(() => {})
    }
  }, [playerId, activeTab, inningsOffset, filters.gender, filters.team_type, filters.tournament, filters.season_from, filters.season_to])

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
    { key: 'balls_per_boundary', label: 'B/Bnd', format: (v: any) => fmt(v) },
  ]

  return (
    <div>
      <div className="mb-6">
        <PlayerSearch role="batter" onSelect={handleSelect} placeholder="Search for a batter..." />
      </div>

      {!playerId && <div className="text-center text-gray-400 py-16">Search for a batter to view stats</div>}

      {playerId && summary && (
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
            {activeTab === 'By Season' && seasonData.length > 0 && (
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

            {activeTab === 'By Over' && overData.length > 0 && (
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

            {activeTab === 'By Phase' && phaseData.length > 0 && (
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

            {activeTab === 'vs Bowlers' && bowlerMatchups.length > 0 && (
              <div>
                <ScatterChart
                  data={bowlerMatchups.filter(m => m.strike_rate != null && m.average != null)}
                  xAccessor={(d: Record<string, any>) => (d.strike_rate as number) ?? 0}
                  yAccessor={(d: Record<string, any>) => (d.average as number) ?? 0}
                  sizeBy={(d: Record<string, any>) => (d.balls as number) ?? 6}
                  title="SR vs Average (dot size = balls faced)"
                  xLabel="Strike Rate" yLabel="Average" width={600} height={400} />
                <div className="mt-4">
                  <DataTable columns={bowlerColumns} data={bowlerMatchups} />
                </div>
              </div>
            )}

            {activeTab === 'Dismissals' && dismissals && (
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

            {activeTab === 'Inter-Wicket' && interWicket.length > 0 && (
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
