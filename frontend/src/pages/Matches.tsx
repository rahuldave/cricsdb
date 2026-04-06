import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { getMatches, getTeams } from '../api'
import PlayerSearch from '../components/PlayerSearch'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import type { TeamInfo } from '../types'

const PAGE_SIZE = 50

export default function Matches() {
  const navigate = useNavigate()
  const filters = useFilters()
  const [team, setTeam] = useUrlParam('team')
  const [playerId] = useUrlParam('player')
  const [playerName] = useUrlParam('player_name')
  const setUrlParams = useSetUrlParams()

  const [teamQuery, setTeamQuery] = useState(team || '')
  const [teamSuggest, setTeamSuggest] = useState<TeamInfo[]>([])
  const [showTeamDropdown, setShowTeamDropdown] = useState(false)

  const [offset, setOffset] = useState(0)

  // Reset pagination when filters change
  useEffect(() => { setOffset(0) }, [
    filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to, team, playerId,
  ])

  // Fetch match list
  const { data: listData, loading, error, refetch } = useFetch(
    () => getMatches({
      ...filters,
      team: team || undefined,
      player_id: playerId || undefined,
      limit: PAGE_SIZE,
      offset,
    }),
    [filters.gender, filters.team_type, filters.tournament,
     filters.season_from, filters.season_to, team, playerId, offset],
  )
  const matches = listData?.matches ?? []
  const total = listData?.total ?? 0

  // Team autocomplete
  useEffect(() => {
    if (!teamQuery || teamQuery === team) { setTeamSuggest([]); return }
    getTeams({ ...filters, q: teamQuery })
      .then(d => { setTeamSuggest(d.teams.slice(0, 10)); setShowTeamDropdown(true) })
      .catch(() => {})
  }, [teamQuery, filters.gender, filters.team_type, filters.tournament])

  const selectTeam = (name: string) => {
    setTeam(name)
    setTeamQuery(name)
    setShowTeamDropdown(false)
  }

  const clearTeam = () => { setTeam(''); setTeamQuery(''); setTeamSuggest([]) }

  const clearPlayer = () => {
    setUrlParams({ player: '', player_name: '' })
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div>
      {/* Filter row: team + player */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative w-64">
          <input
            type="text"
            value={teamQuery}
            onChange={e => { setTeamQuery(e.target.value); setShowTeamDropdown(true) }}
            placeholder="Filter by team..."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          {team && (
            <button onClick={clearTeam}
              className="absolute right-2 top-2 text-gray-400 hover:text-gray-700 text-sm">×</button>
          )}
          {showTeamDropdown && teamSuggest.length > 0 && (
            <ul className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg max-h-60 overflow-y-auto">
              {teamSuggest.map(t => (
                <li key={t.name}
                  className="px-3 py-2 hover:bg-blue-50 cursor-pointer text-sm flex justify-between"
                  onClick={() => selectTeam(t.name)}>
                  <span>{t.name}</span>
                  <span className="text-gray-400">{t.matches}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="w-64 flex items-center gap-2">
          <PlayerSearch
            role="batter"
            placeholder="Filter by player..."
            onSelect={p => setUrlParams({ player: p.id, player_name: p.name })}
          />
          {playerId && playerName && (
            <button onClick={clearPlayer}
              className="text-xs text-gray-500 hover:text-gray-800 whitespace-nowrap">
              ×&nbsp;{playerName}
            </button>
          )}
        </div>

        <div className="ml-auto text-sm text-gray-600">
          {loading ? '…' : `${total.toLocaleString()} matches`}
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <ErrorBanner
            message={`Could not load matches: ${error}`}
            onRetry={refetch}
          />
        </div>
      )}

      {/* Match list */}
      <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-200 bg-gray-50">
              <th className="px-3 py-2 font-medium">Date</th>
              <th className="px-3 py-2 font-medium">Match</th>
              <th className="px-3 py-2 font-medium hidden md:table-cell">Tournament</th>
              <th className="px-3 py-2 font-medium hidden lg:table-cell">Venue</th>
              <th className="px-3 py-2 font-medium hidden sm:table-cell">Result</th>
            </tr>
          </thead>
          <tbody>
            {matches.map(m => {
              return (
                <tr key={m.match_id}
                  onClick={() => navigate(`/matches/${m.match_id}`)}
                  className="border-b border-gray-100 cursor-pointer hover:bg-blue-50">
                  <td className="px-3 py-2 whitespace-nowrap text-gray-600 align-top">{m.date || '-'}</td>
                  <td className="px-3 py-2">
                    <div className="font-medium text-gray-900">{m.team1} vs {m.team2}</div>
                    <div className="text-xs text-gray-500">
                      {m.team1_score && <>{m.team1}: {m.team1_score}</>}
                      {m.team1_score && m.team2_score && <>  ·  </>}
                      {m.team2_score && <>{m.team2}: {m.team2_score}</>}
                    </div>
                    {/* On narrow screens, show tournament + result inline since the columns are hidden */}
                    <div className="text-xs text-gray-600 mt-1 sm:hidden">{m.result_text}</div>
                    <div className="text-xs text-gray-500 mt-0.5 md:hidden">{m.tournament || ''}</div>
                  </td>
                  <td className="px-3 py-2 text-gray-600 hidden md:table-cell">{m.tournament || '-'}</td>
                  <td className="px-3 py-2 text-gray-600 hidden lg:table-cell">{m.city || m.venue || '-'}</td>
                  <td className="px-3 py-2 text-gray-700 hidden sm:table-cell">{m.result_text}</td>
                </tr>
              )
            })}
            {loading && matches.length === 0 && (
              <tr><td colSpan={5} className="p-0"><Spinner label="Loading matches…" /></td></tr>
            )}
            {!loading && !error && matches.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-gray-400">No matches</td></tr>
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-3 py-2 border-t border-gray-200 bg-gray-50 text-sm">
            <button
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={offset === 0}
              className="px-3 py-1 rounded border border-gray-300 bg-white text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed">
              Previous
            </button>
            <span className="text-gray-600">Page {currentPage} of {totalPages}</span>
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={offset + PAGE_SIZE >= total}
              className="px-3 py-1 rounded border border-gray-300 bg-white text-gray-700 disabled:opacity-50 disabled:cursor-not-allowed">
              Next
            </button>
          </div>
        )}
      </div>

      {/* Scorecard */}
    </div>
  )
}
