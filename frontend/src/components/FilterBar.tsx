import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getTournaments, getSeasons } from '../api'
import { useSetUrlParams } from '../hooks/useUrlState'
import type { FilterParams, Tournament } from '../types'

export function useFilters(): FilterParams {
  const [params] = useSearchParams()
  return {
    gender: params.get('gender') || undefined,
    team_type: params.get('team_type') || undefined,
    tournament: params.get('tournament') || undefined,
    season_from: params.get('season_from') || undefined,
    season_to: params.get('season_to') || undefined,
  }
}

export default function FilterBar() {
  const [params] = useSearchParams()
  const setUrlParams = useSetUrlParams()
  const [tournaments, setTournaments] = useState<Tournament[]>([])
  const [seasons, setSeasons] = useState<string[]>([])
  const [tournamentsError, setTournamentsError] = useState(false)
  const [seasonsError, setSeasonsError] = useState(false)

  // Narrow the dropdowns to the active context. A tournament isn't a
  // filter on the tournaments endpoint (self-referential), but it
  // absolutely narrows seasons — picking IPL should remove
  // CLT20/WPL/rare years MI played elsewhere from the From/To pickers.
  const team = params.get('team') || undefined
  const genderParam = params.get('gender') || undefined
  const teamTypeParam = params.get('team_type') || undefined
  const tournamentParam = params.get('tournament') || undefined
  useEffect(() => {
    getTournaments({ team, gender: genderParam, team_type: teamTypeParam })
      .then(d => { setTournaments(d.tournaments); setTournamentsError(false) })
      .catch(err => {
        console.warn('Failed to load tournaments:', err)
        setTournamentsError(true)
      })
  }, [team, genderParam, teamTypeParam])
  useEffect(() => {
    getSeasons({ team, gender: genderParam, team_type: teamTypeParam, tournament: tournamentParam })
      .then(d => { setSeasons(d.seasons); setSeasonsError(false) })
      .catch(err => {
        console.warn('Failed to load seasons:', err)
        setSeasonsError(true)
      })
  }, [team, genderParam, teamTypeParam, tournamentParam])

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
  // both — see docs/design-decisions.md "Tournament deep links".
  useEffect(() => {
    if (tournaments.length === 0 || !tournament) return
    if (gender && teamType) return
    const t = tournaments.find(x => x.event_name === tournament)
    if (!t) return
    const updates: Record<string, string> = {}
    if (!gender && t.gender) updates.gender = t.gender
    if (!teamType && t.team_type) updates.team_type = t.team_type
    if (Object.keys(updates).length > 0) setUrlParams(updates)
  }, [tournaments, tournament, gender, teamType])

  // When a team is selected (Teams page) AND no team_type / gender is
  // set yet AND the team's tournaments are unambiguous (one type, one
  // gender), auto-fill the filter so MI doesn't aggregate WPL women's
  // numbers etc. Driven by the team-scoped tournaments list above.
  useEffect(() => {
    if (!team || tournaments.length === 0) return
    if (gender && teamType) return
    const types = new Set(tournaments.map(t => t.team_type).filter(Boolean))
    const genders = new Set(tournaments.map(t => t.gender).filter(Boolean))
    const updates: Record<string, string> = {}
    if (!teamType && types.size === 1) updates.team_type = [...types][0] as string
    if (!gender && genders.size === 1) updates.gender = [...genders][0] as string
    if (Object.keys(updates).length > 0) setUrlParams(updates)
  }, [team, tournaments, gender, teamType])

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

  const filteredTournaments = tournaments.filter(t => {
    if (teamType && t.team_type !== teamType) return false
    if (gender && t.gender !== gender) return false
    return true
  })

  const segBtn = (active: boolean) => `wisden-seg${active ? ' is-active' : ''}`

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
        </div>
      </div>
    </div>
  )
}
