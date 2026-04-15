import type React from 'react'
import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { getMatches, getTeams } from '../api'
import PlayerSearch from '../components/PlayerSearch'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import type { TeamInfo } from '../types'

const PAGE_SIZE = 50

export default function Matches() {
  useDocumentTitle('Matches')
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
    <div className="max-w-6xl mx-auto">
      <h2 className="wisden-page-title">Matches</h2>

      {/* Filter row: team + player */}
      <div className="flex flex-wrap items-center gap-6 mb-6">
        <div className="relative w-64 wisden-playersearch">
          <input
            type="text"
            value={teamQuery}
            onChange={e => { setTeamQuery(e.target.value); setShowTeamDropdown(true) }}
            placeholder="Filter by team…"
            className="wisden-playersearch-input"
          />
          {team && (
            <button onClick={clearTeam}
              className="absolute right-1 top-2 wisden-clear">×</button>
          )}
          {showTeamDropdown && teamSuggest.length > 0 && (
            <ul className="wisden-playersearch-list">
              {teamSuggest.map(t => (
                <li key={t.name} onClick={() => selectTeam(t.name)}>
                  <span className="wisden-playersearch-name">{t.name}</span>
                  <span className="wisden-playersearch-meta num">{t.matches}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="w-64 flex items-center gap-2">
          <PlayerSearch
            role="batter"
            placeholder="Filter by player…"
            onSelect={p => setUrlParams({ player: p.id, player_name: p.name })}
          />
          {playerId && playerName && (
            <button onClick={clearPlayer} className="wisden-clear">
              ×&nbsp;{playerName}
            </button>
          )}
        </div>

        <div className="ml-auto wisden-meta-count">
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
      <div className="overflow-x-auto">
        <table className="wisden-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Match</th>
              <th className="hidden md:table-cell">Tournament</th>
              <th className="hidden lg:table-cell">Venue</th>
              <th className="hidden sm:table-cell">Result</th>
            </tr>
          </thead>
          <tbody>
            {matches.map(m => {
              // Row is clickable → scorecard. Team / tournament cells
              // override the row click so they go to the team / tournament
              // dossier instead. Preserves FilterBar context.
              const stop = (e: React.MouseEvent) => e.stopPropagation()
              const teamHref = (t: string) => {
                const p = new URLSearchParams({ team: t })
                if (filters.gender) p.set('gender', filters.gender)
                if (filters.team_type) p.set('team_type', filters.team_type)
                if (m.tournament) p.set('tournament', m.tournament)
                return `/teams?${p.toString()}`
              }
              const tournamentHref = (t: string) => {
                const p = new URLSearchParams({ tournament: t })
                if (filters.gender) p.set('gender', filters.gender)
                if (filters.team_type) p.set('team_type', filters.team_type)
                return `/tournaments?${p.toString()}`
              }
              return (
              <tr key={m.match_id}
                onClick={() => navigate(`/matches/${m.match_id}`)}
                className="is-clickable">
                <td className="num whitespace-nowrap" style={{ color: 'var(--ink-faint)' }}>{m.date || '-'}</td>
                <td>
                  <div style={{ fontFamily: 'var(--serif)', fontSize: '1rem', color: 'var(--ink)', fontVariationSettings: '"opsz" 14' }}>
                    <Link to={teamHref(m.team1)} className="comp-link" onClick={stop}>{m.team1}</Link>
                    {' '}<span style={{ fontStyle: 'italic', color: 'var(--ink-faint)' }}>v</span>{' '}
                    <Link to={teamHref(m.team2)} className="comp-link" onClick={stop}>{m.team2}</Link>
                  </div>
                  <div className="num" style={{ fontSize: '0.78rem', color: 'var(--ink-faint)', marginTop: '0.15rem' }}>
                    {m.team1_score && <>{m.team1}: {m.team1_score}</>}
                    {m.team1_score && m.team2_score && <>  ·  </>}
                    {m.team2_score && <>{m.team2}: {m.team2_score}</>}
                  </div>
                  <div className="sm:hidden" style={{ fontSize: '0.78rem', color: 'var(--ink-soft)', marginTop: '0.15rem', fontFamily: 'var(--serif)' }}>{m.result_text}</div>
                  <div className="md:hidden" style={{ fontSize: '0.72rem', color: 'var(--ink-faint)', marginTop: '0.1rem' }}>{m.tournament || ''}</div>
                </td>
                <td className="hidden md:table-cell">
                  {m.tournament
                    ? <Link to={tournamentHref(m.tournament)} className="comp-link" onClick={stop}>{m.tournament}</Link>
                    : '-'}
                </td>
                <td className="hidden lg:table-cell">{m.city || m.venue || '-'}</td>
                <td className="hidden sm:table-cell" style={{ fontFamily: 'var(--serif)', fontVariationSettings: '"opsz" 14' }}>{m.result_text}</td>
              </tr>
              )
            })}
            {loading && matches.length === 0 && (
              <tr><td colSpan={5} className="p-0"><Spinner label="Loading matches…" /></td></tr>
            )}
            {!loading && !error && matches.length === 0 && (
              <tr><td colSpan={5} className="wisden-table-empty">No matches</td></tr>
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="wisden-pagination">
            <div className="wisden-pagination-buttons">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}>
                ← Previous
              </button>
            </div>
            <span>Page <span className="num">{currentPage}</span> of <span className="num">{totalPages}</span></span>
            <div className="wisden-pagination-buttons">
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}>
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
