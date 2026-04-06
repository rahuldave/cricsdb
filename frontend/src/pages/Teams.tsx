import { useState, useEffect } from 'react'
import { useFilters } from '../components/FilterBar'
import { useUrlParam } from '../hooks/useUrlState'
import { getTeams, getTeamSummary, getTeamByseason, getTeamVs, getTeamResults, getTeamOpponents } from '../api'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import type { TeamInfo, TeamSummary, TeamSeasonRecord, TeamVsOpponent, TeamResult } from '../types'

const tabs = ['By Season', 'vs Opponent', 'Match List'] as const

export default function Teams() {
  const filters = useFilters()
  const [selected, setSelected] = useUrlParam('team')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const [opponent, setOpponent] = useUrlParam('vs')

  const [teams, setTeams] = useState<TeamInfo[]>([])
  const [opponents, setOpponents] = useState<{ name: string; matches: number }[]>([])
  const [query, setQuery] = useState(selected || '')
  const [showDropdown, setShowDropdown] = useState(false)
  const [summary, setSummary] = useState<TeamSummary | null>(null)
  const [seasons, setSeasons] = useState<TeamSeasonRecord[]>([])
  const [vsData, setVsData] = useState<TeamVsOpponent | null>(null)
  const [results, setResults] = useState<TeamResult[]>([])
  const [resultsTotal, setResultsTotal] = useState(0)
  const [resultsOffset, setResultsOffset] = useState(0)

  useEffect(() => {
    if (!query || selected) return
    getTeams({ ...filters, q: query }).then(d => { setTeams(d.teams); setShowDropdown(true) }).catch(() => {})
  }, [filters.gender, filters.team_type, filters.tournament, query, selected])

  useEffect(() => {
    if (!selected) { setOpponents([]); return }
    getTeamOpponents(selected, filters).then(d => setOpponents(d.opponents)).catch(() => {})
  }, [selected, filters.gender, filters.team_type, filters.tournament, filters.season_from, filters.season_to])

  useEffect(() => {
    if (!selected) { setSummary(null); return }
    getTeamSummary(selected, filters).then(setSummary).catch(() => {})
    getTeamByseason(selected, filters).then(d => setSeasons(d.seasons)).catch(() => {})
  }, [selected, filters.gender, filters.team_type, filters.tournament, filters.season_from, filters.season_to])

  useEffect(() => {
    if (!selected || !opponent) { setVsData(null); return }
    getTeamVs(selected, opponent, filters).then(setVsData).catch(() => {})
  }, [selected, opponent, filters.gender, filters.team_type, filters.tournament, filters.season_from, filters.season_to])

  useEffect(() => {
    if (!selected) return
    getTeamResults(selected, { ...filters, limit: 50, offset: resultsOffset }).then(d => {
      setResults(d.results); setResultsTotal(d.total)
    }).catch(() => {})
  }, [selected, resultsOffset, filters.gender, filters.team_type, filters.tournament, filters.season_from, filters.season_to])

  const selectTeam = (name: string) => {
    setSelected(name); setQuery(name); setShowDropdown(false)
  }

  const resultColumns: Column<TeamResult>[] = [
    { key: 'date', label: 'Date', sortable: true },
    { key: 'opponent', label: 'Opponent', sortable: true },
    { key: 'venue', label: 'Venue' },
    { key: 'tournament', label: 'Tournament' },
    { key: 'result', label: 'Result', sortable: true },
    { key: 'margin', label: 'Margin' },
  ]

  return (
    <div>
      <div className="mb-6 relative">
        <input type="text" value={query}
          onChange={e => { setQuery(e.target.value); setSelected(''); setSummary(null); setShowDropdown(true) }}
          placeholder="Search teams..."
          className="w-full max-w-md rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none" />
        {showDropdown && teams.length > 0 && !selected && (
          <ul className="absolute z-10 mt-1 max-w-md rounded-lg border border-gray-200 bg-white shadow-lg max-h-60 overflow-y-auto">
            {teams.slice(0, 20).map(t => (
              <li key={t.name} className="px-4 py-2 hover:bg-blue-50 cursor-pointer flex justify-between text-sm"
                onClick={() => selectTeam(t.name)}>
                <span className="font-medium">{t.name}</span>
                <span className="text-gray-400">{t.matches} matches</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {!selected && <div className="text-center text-gray-400 py-16">Search for a team to view stats</div>}

      {selected && summary && (
        <>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">{selected}</h2>
          <div className="grid grid-cols-4 gap-3 mb-6">
            <StatCard label="Matches" value={summary.matches} />
            <StatCard label="Wins" value={summary.wins} />
            <StatCard label="Losses" value={summary.losses} />
            <StatCard label="Win %" value={summary.win_pct != null ? `${summary.win_pct}%` : '-'} />
          </div>

          <div className="border-b border-gray-200 mb-4">
            <div className="flex gap-1">
              {tabs.map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 ${activeTab === tab ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                >{tab}</button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg border p-6 shadow-sm">
            {activeTab === 'By Season' && seasons.length > 0 && (
              <BarChart data={seasons} categoryAccessor="season" valueAccessor="wins"
                title="Wins by Season" categoryLabel="Season" valueLabel="Wins"
                width={700} height={350} colorScheme={['#22c55e']} />
            )}

            {activeTab === 'vs Opponent' && (
              <div>
                <div className="mb-4">
                  <select value={opponent} onChange={e => setOpponent(e.target.value)}
                    className="rounded-md border border-gray-300 px-3 py-2 text-sm bg-white">
                    <option value="">Select opponent...</option>
                    {opponents.map(t => (
                      <option key={t.name} value={t.name}>{t.name} ({t.matches})</option>
                    ))}
                  </select>
                </div>
                {vsData && (
                  <div>
                    <div className="grid grid-cols-4 gap-3 mb-4">
                      <StatCard label="Matches" value={vsData.overall.matches} />
                      <StatCard label="Wins" value={vsData.overall.wins} />
                      <StatCard label="Losses" value={vsData.overall.losses} />
                      <StatCard label="Ties" value={vsData.overall.ties} />
                    </div>
                    {vsData.by_season.length > 0 && (
                      <BarChart data={vsData.by_season} categoryAccessor="season" valueAccessor="wins"
                        title={`Wins vs ${opponent} by Season`} categoryLabel="Season" valueLabel="Wins"
                        width={700} height={300} colorScheme={['#3b82f6']} />
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'Match List' && (
              <DataTable columns={resultColumns} data={results}
                pagination={{ total: resultsTotal, limit: 50, offset: resultsOffset, onPage: setResultsOffset }} />
            )}
          </div>
        </>
      )}
    </div>
  )
}
