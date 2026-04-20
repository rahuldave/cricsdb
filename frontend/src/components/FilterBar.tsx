import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getTournaments, getSeasons } from '../api'
import { useSetUrlParams } from '../hooks/useUrlState'
import { useFilters } from '../hooks/useFilters'
import VenueSearch from './VenueSearch'
import type { Tournament } from '../types'

export default function FilterBar() {
  const [params] = useSearchParams()
  const setUrlParams = useSetUrlParams()
  const filters = useFilters()
  const [tournaments, setTournaments] = useState<Tournament[]>([])
  const [seasons, setSeasons] = useState<string[]>([])
  const [tournamentsError, setTournamentsError] = useState(false)
  const [seasonsError, setSeasonsError] = useState(false)

  // Dropdown-narrowing fetches. Pass the FULL filter state through so
  // every narrowing field (including future additions — filter_venue,
  // season range, etc.) automatically participates. The backend drops
  // self-referential axes per-endpoint (e.g. /tournaments ignores
  // `tournament`, /seasons ignores `season_from`/`season_to`).
  //
  // `series_type` is a Series-tab URL param (not in FilterParams —
  // doesn't ride through to every other tab). Read directly from URL
  // so the Series dossier's bilateral/ICC toggle narrows the dropdown.
  const pathTeam = params.get('team') || undefined
  const filterTeam = filters.filter_team
  const filterOpponent = filters.filter_opponent
  // Path team (Teams page identity) wins over filter_team when set —
  // same precedence rule used elsewhere. Opponent only applies when
  // there's no path team (rivalry scope is URL-filter-mediated).
  const teamForFetch = pathTeam || filterTeam
  const opponentForFetch = pathTeam ? undefined : filterOpponent
  const seriesType = params.get('series_type') || undefined
  useEffect(() => {
    getTournaments({
      ...filters,
      team: teamForFetch,
      opponent: opponentForFetch,
      series_type: seriesType,
    })
      .then(d => { setTournaments(d.tournaments); setTournamentsError(false) })
      .catch(err => {
        console.warn('Failed to load tournaments:', err)
        setTournamentsError(true)
      })
  }, [
    teamForFetch, opponentForFetch, seriesType,
    filters.gender, filters.team_type, filters.filter_venue,
    filters.season_from, filters.season_to,
  ])
  useEffect(() => {
    getSeasons({
      ...filters,
      team: teamForFetch,
      series_type: seriesType,
    })
      .then(d => { setSeasons(d.seasons); setSeasonsError(false) })
      .catch(err => {
        console.warn('Failed to load seasons:', err)
        setSeasonsError(true)
      })
  }, [
    teamForFetch, seriesType,
    filters.gender, filters.team_type, filters.tournament,
    filters.filter_team, filters.filter_opponent, filters.filter_venue,
  ])

  const set = (key: string, value: string) => {
    setUrlParams({ [key]: value })
  }

  const gender = params.get('gender') || ''
  const teamType = params.get('team_type') || ''
  const tournament = params.get('tournament') || ''

  // Self-correcting deep links: when a URL has ?tournament=X but no
  // gender or team_type (e.g. clicking the IPL link on the home page),
  // fill them in from the tournament's metadata as soon as the
  // tournaments list loads. Without this, /matches?tournament=IPL
  // would aggregate IPL men + WPL women for any team that exists in
  // both — see internal_docs/design-decisions.md "Tournament deep links".
  useEffect(() => {
    if (tournaments.length === 0 || !tournament) return
    if (gender && teamType) return
    const t = tournaments.find(x => x.event_name === tournament)
    if (!t) return
    const updates: Record<string, string> = {}
    if (!gender && t.gender) updates.gender = t.gender
    if (!teamType && t.team_type) updates.team_type = t.team_type
    // Auto-correcting deep link → replace (no history entry for
    // something the user didn't actively pick).
    if (Object.keys(updates).length > 0) setUrlParams(updates, { replace: true })
  }, [tournaments, tournament, gender, teamType])

  // When a team is selected (Teams page) AND no team_type / gender is
  // set yet AND the team's tournaments are unambiguous (one type, one
  // gender), auto-fill the filter so MI doesn't aggregate WPL women's
  // numbers etc. Driven by the team-scoped tournaments list above.
  useEffect(() => {
    if (!teamForFetch || tournaments.length === 0) return
    if (gender && teamType) return
    const types = new Set(tournaments.map(t => t.team_type).filter(Boolean))
    const genders = new Set(tournaments.map(t => t.gender).filter(Boolean))
    const updates: Record<string, string> = {}
    if (!teamType && types.size === 1) updates.team_type = [...types][0] as string
    if (!gender && genders.size === 1) updates.gender = [...genders][0] as string
    if (Object.keys(updates).length > 0) setUrlParams(updates, { replace: true })
  }, [teamForFetch, tournaments, gender, teamType])

  // Intra-tournament rivalry auto-narrow: when BOTH filter_team and
  // filter_opponent are set AND the two teams only ever meet in a
  // single tournament (e.g. MI × CSK → IPL only), auto-set tournament.
  // For multi-tournament rivalries (Ind vs Aus spans bilaterals + ICC)
  // the server returns multiple entries and we leave tournament empty
  // so the user picks manually. We intentionally do NOT use this for
  // single-team scoping — MI alone plays IPL + WPL so the set can look
  // unambiguous while actually hiding the women's side.
  useEffect(() => {
    if (!filterTeam || !filterOpponent) return
    if (tournament) return
    if (tournaments.length !== 1) return
    setUrlParams({ tournament: tournaments[0].event_name }, { replace: true })
  }, [filterTeam, filterOpponent, tournaments, tournament])

  const setGender = (v: string) => {
    const updates: Record<string, string> = { gender: v }
    if (tournament) {
      const t = tournaments.find(x => x.event_name === tournament)
      if (t && v && t.gender !== v) updates.tournament = ''
    }
    setUrlParams(updates)
  }

  const setTeamType = (v: string) => {
    const updates: Record<string, string> = { team_type: v }
    if (tournament) {
      const t = tournaments.find(x => x.event_name === tournament)
      if (t && v && t.team_type !== v) updates.tournament = ''
    }
    setUrlParams(updates)
  }

  const setTournament = (v: string) => {
    const updates: Record<string, string> = { tournament: v }
    if (v) {
      const t = tournaments.find(x => x.event_name === v)
      if (t) {
        updates.gender = t.gender
        updates.team_type = t.team_type
      }
    }
    setUrlParams(updates)
  }
  const seasonFrom = params.get('season_from') || ''
  const seasonTo = params.get('season_to') || ''
  const filterVenue = params.get('filter_venue') || ''

  const filteredTournaments = tournaments.filter(t => {
    if (teamType && t.team_type !== teamType) return false
    if (gender && t.gender !== gender) return false
    return true
  })

  const segBtn = (active: boolean) => `wisden-seg${active ? ' is-active' : ''}`

  const anyFilterSet = Boolean(gender || teamType || tournament || seasonFrom || seasonTo || filterVenue)
  const latestInScope = seasons.length > 0 && !seasonsError ? seasons[seasons.length - 1] : null
  const clearSeasons = () => setUrlParams({ season_from: '', season_to: '' })
  const setLatest = () => {
    if (!latestInScope) return
    // Updates ONLY season_from + season_to — gender/team_type/
    // tournament (and team, if set) are preserved by useSetUrlParams.
    // The latest-in-scope lookup itself already respects those filters
    // via the seasons-fetch effect above.
    setUrlParams({ season_from: latestInScope, season_to: latestInScope })
  }
  const setLastN = (n: number) => {
    if (seasons.length === 0) return
    // Scope-aware last-N — seasons list is already narrowed by
    // gender/team_type/tournament via the seasons-fetch effect. Takes
    // the last N entries (API returns chronological ascending).
    const latest = seasons.slice(-n)
    const from = latest[0]
    const to = latest[latest.length - 1]
    setUrlParams({ season_from: from, season_to: to })
  }
  const clearAll = () => setUrlParams({
    gender: '', team_type: '', tournament: '',
    season_from: '', season_to: '', filter_venue: '',
  })

  const setVenue = (name: string) => setUrlParams({ filter_venue: name })
  const clearVenue = () => setUrlParams({ filter_venue: '' })

  return (
    <div className="wisden-filterbar">
      <div className="wisden-filterbar-inner">
        <div className="wisden-filter-group">
          <span className="wisden-filter-label">Gender</span>
          {['', 'male', 'female'].map(v => (
            <button key={v} onClick={() => setGender(v)} className={segBtn(gender === v)}>
              {v === '' ? 'All' : v === 'male' ? 'Men' : 'Women'}
            </button>
          ))}
        </div>

        <div className="wisden-filter-group">
          <span className="wisden-filter-label">Type</span>
          {['', 'international', 'club'].map(v => (
            <button key={v} onClick={() => setTeamType(v)} className={segBtn(teamType === v)}>
              {v === '' ? 'All' : v === 'international' ? 'Intl' : 'Club'}
            </button>
          ))}
        </div>

        <div className="wisden-filter-group">
          <span className="wisden-filter-label">Tournament</span>
          <select
            value={tournament}
            onChange={e => setTournament(e.target.value)}
            disabled={tournamentsError}
            className="wisden-select"
          >
            <option value="">{tournamentsError ? '⚠ failed to load' : 'All'}</option>
            {filteredTournaments.map(t => (
              <option key={t.event_name} value={t.event_name}>{t.event_name} ({t.matches})</option>
            ))}
          </select>
        </div>

        <div className="wisden-filter-group">
          <span className="wisden-filter-label">Seasons</span>
          <select
            value={seasonFrom}
            onChange={e => set('season_from', e.target.value)}
            disabled={seasonsError}
            className="wisden-select"
          >
            <option value="">{seasonsError ? '⚠' : 'From'}</option>
            {seasons.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <span className="wisden-filter-dash">–</span>
          <select
            value={seasonTo}
            onChange={e => set('season_to', e.target.value)}
            disabled={seasonsError}
            className="wisden-select"
          >
            <option value="">{seasonsError ? '⚠' : 'To'}</option>
            {seasons.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <button type="button" onClick={clearSeasons} className="wisden-reset"
            title="Clear season range — show all-time">
            all-time
          </button>
          {seasons.length >= 3 && (
            <button type="button" onClick={() => setLastN(3)} className="wisden-reset"
              title={`Last 3 seasons in scope (${seasons.slice(-3).join(', ')})`}>
              last 3
            </button>
          )}
          {latestInScope && (
            <button type="button" onClick={setLatest} className="wisden-reset"
              title={`Jump to latest season in scope (${latestInScope})`}>
              latest
            </button>
          )}
        </div>

        <div className="wisden-filter-group">
          <span className="wisden-filter-label">Venue</span>
          <VenueSearch
            value={filterVenue}
            onSelect={setVenue}
            onClear={clearVenue}
          />
        </div>

        {anyFilterSet && (
          <button type="button" onClick={clearAll} className="wisden-reset wisden-reset-all"
            title="Clear every filter">
            reset all
          </button>
        )}
      </div>
    </div>
  )
}
