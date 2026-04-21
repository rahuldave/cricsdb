import type React from 'react'
import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useFilters } from '../hooks/useFilters'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { getMatches, getTeams } from '../api'
import PlayerSearch from '../components/PlayerSearch'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import Score from '../components/Score'
import TeamLink from '../components/TeamLink'
import EdHelp from '../components/EdHelp'
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

  // Transient typing buffer for the team filter — `null` = not editing,
  // input falls through to `team` (URL truth). See PlayerSearch for the
  // full rationale.
  const [teamTyping, setTeamTyping] = useState<string | null>(null)
  const [teamSuggest, setTeamSuggest] = useState<TeamInfo[]>([])
  const [showTeamDropdown, setShowTeamDropdown] = useState(false)

  const teamInputValue = teamTyping ?? team ?? ''

  const [offset, setOffset] = useState(0)

  // Reset pagination when filters change
  useEffect(() => { setOffset(0) }, [
    filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to, filters.filter_venue,
    team, playerId,
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
     filters.season_from, filters.season_to, filters.filter_venue,
     team, playerId, offset],
  )
  const matches = listData?.matches ?? []
  const total = listData?.total ?? 0

  // Team autocomplete — fires only while the user is typing.
  useEffect(() => {
    if (teamTyping === null || teamTyping.length < 1) { setTeamSuggest([]); return }
    getTeams({ ...filters, q: teamTyping })
      .then(d => { setTeamSuggest(d.teams.slice(0, 10)); setShowTeamDropdown(true) })
      .catch(() => {})
  }, [teamTyping, filters.gender, filters.team_type, filters.tournament])

  const selectTeam = (name: string) => {
    setTeam(name)
    setTeamTyping(null)
    setShowTeamDropdown(false)
  }

  const clearTeam = () => { setTeam(''); setTeamTyping(null); setTeamSuggest([]) }

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
            value={teamInputValue}
            onChange={e => { setTeamTyping(e.target.value); setShowTeamDropdown(true) }}
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
      <EdHelp />
      <div className="overflow-x-auto">
        <table className="wisden-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Match</th>
              <th className="hidden md:table-cell">Edition</th>
              <th className="hidden lg:table-cell">Venue</th>
              <th className="hidden sm:table-cell">Result</th>
            </tr>
          </thead>
          <tbody>
            {matches.map(m => {
              // Row is clickable → scorecard. Team / edition cells
              // override the row click so they go to the team / series
              // dossier instead. Preserves FilterBar context.
              const stop = (e: React.MouseEvent) => e.stopPropagation()
              // Edition text — just the season when the FilterBar is
              // already pinned to one tournament (the tournament repeats
              // in every row), otherwise "Tournament, Season".
              const editionText = filters.tournament
                ? (m.season ?? '')
                : [m.tournament, m.season].filter(Boolean).join(', ')
              const editionHref = m.tournament
                ? (() => {
                    const p = new URLSearchParams({ tournament: m.tournament })
                    if (filters.gender) p.set('gender', filters.gender)
                    if (filters.team_type) p.set('team_type', filters.team_type)
                    if (m.season) { p.set('season_from', m.season); p.set('season_to', m.season) }
                    return `/series?${p.toString()}`
                  })()
                : null
              // TeamLink subscriptSource pins the (ed) to THIS match's
              // edition (tournament + season from the row), regardless
              // of the FilterBar's season window. team1: null / team2:
              // null explicitly clear any FilterBar rivalry pair so the
              // bilateral-series concern doesn't strip the tournament
              // from the (ed) URL. See design-decisions.md "Per-row
              // '(ed)' tag" for the convention.
              const edScope = {
                tournament: m.tournament,
                season: m.season,
                team1: null,
                team2: null,
              }
              return (
              <tr key={m.match_id}
                onClick={() => navigate(`/matches/${m.match_id}`)}
                className="is-clickable">
                <td className="num whitespace-nowrap" style={{ color: 'var(--ink-faint)' }}>
                  {m.date ? (
                    <Link to={`/matches/${m.match_id}`} className="comp-link"
                      style={{ color: 'inherit' }} onClick={stop}>{m.date}</Link>
                  ) : '-'}
                </td>
                <td>
                  <div
                    onClick={stop}
                    style={{ fontFamily: 'var(--serif)', fontSize: '1rem', color: 'var(--ink)', fontVariationSettings: '"opsz" 14' }}>
                    <TeamLink
                      teamName={m.team1}
                      gender={filters.gender ?? null}
                      team_type={filters.team_type ?? null}
                      subscriptSource={edScope}
                      maxTiers={1}
                      phraseLabel="ed"
                      phraseClassName="scope-phrase-ed"
                    />
                    {' '}<span style={{ fontStyle: 'italic', color: 'var(--ink-faint)' }}>v</span>{' '}
                    <TeamLink
                      teamName={m.team2}
                      gender={filters.gender ?? null}
                      team_type={filters.team_type ?? null}
                      subscriptSource={edScope}
                      maxTiers={1}
                      phraseLabel="ed"
                      phraseClassName="scope-phrase-ed"
                    />
                  </div>
                  {(m.team1_score || m.team2_score) && (
                    <div style={{ fontSize: '0.78rem', color: 'var(--ink-faint)', marginTop: '0.15rem' }}>
                      <Score team1Score={m.team1_score} team2Score={m.team2_score} />
                    </div>
                  )}
                  <div className="sm:hidden" style={{ fontSize: '0.78rem', color: 'var(--ink-soft)', marginTop: '0.15rem', fontFamily: 'var(--serif)' }}>{m.result_text}</div>
                  <div className="md:hidden" style={{ fontSize: '0.72rem', color: 'var(--ink-faint)', marginTop: '0.1rem' }}>{editionText}</div>
                </td>
                <td className="hidden md:table-cell" onClick={stop}>
                  {editionHref
                    ? <Link to={editionHref} className="comp-link">{editionText || '-'}</Link>
                    : (editionText || '-')}
                </td>
                <td className="hidden lg:table-cell">
                  {m.venue ? (
                    <>
                      <Link to={`/matches?filter_venue=${encodeURIComponent(m.venue)}`}
                        className="comp-link" onClick={stop}>{m.venue}</Link>
                      {m.city && m.city !== m.venue && (
                        <span style={{ color: 'var(--ink-faint)' }}> · {m.city}</span>
                      )}
                    </>
                  ) : (m.city || '-')}
                </td>
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
