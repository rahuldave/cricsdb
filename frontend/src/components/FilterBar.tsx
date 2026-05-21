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
  // Tracks WHICH scope the `tournaments` state was last fetched for.
  // Auto-narrow useEffects compare this against the current scope
  // signature to detect staleness SYNCHRONOUSLY. An async staleness
  // flag wouldn't work — the back-button URL change and the next
  // auto-narrow fire in the same render, before the async stale=true
  // setter lands, so they'd race.
  const [fetchedScope, setFetchedScope] = useState('')

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
  // Page-context player (set on /batting?player=X etc.). Forwarded to
  // /api/v1/seasons so the From/To dropdown options + the
  // first-3 / prev-3 / last-3 / latest quick-select buttons all
  // narrow to the player's actual career-in-scope. Fixes the
  // retired-player gap (e.g. clicking last-3 on AB de Villiers no
  // longer sets the filter to seasons he didn't play). Compare-tab
  // callers don't pass player and stay team-anchored.
  const playerForFetch = params.get('player') || undefined
  // Scope signature — every field that affects what /tournaments
  // returns. Compared against `fetchedScope` below for synchronous
  // staleness detection.
  const currentScope = JSON.stringify({
    teamForFetch, opponentForFetch, seriesType,
    gender: filters.gender, team_type: filters.team_type,
    filter_venue: filters.filter_venue,
    season_from: filters.season_from, season_to: filters.season_to,
  })
  const tournamentsStale = fetchedScope !== currentScope
  useEffect(() => {
    getTournaments({
      ...filters,
      team: teamForFetch,
      opponent: opponentForFetch,
      series_type: seriesType,
    })
      .then(d => {
        setTournaments(d.tournaments)
        setFetchedScope(currentScope)
        setTournamentsError(false)
      })
      .catch(err => {
        console.warn('Failed to load tournaments:', err)
        setTournamentsError(true)
      })
  }, [currentScope])
  useEffect(() => {
    getSeasons({
      ...filters,
      team: teamForFetch,
      series_type: seriesType,
      player: playerForFetch,
    })
      .then(d => { setSeasons(d.seasons); setSeasonsError(false) })
      .catch(err => {
        console.warn('Failed to load seasons:', err)
        setSeasonsError(true)
      })
  }, [
    teamForFetch, seriesType, playerForFetch,
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
    if (tournamentsStale) return
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
  }, [tournaments, tournamentsStale, tournament, gender, teamType])

  // When a team is selected (Teams page) AND no team_type / gender is
  // set yet AND the team's tournaments are unambiguous (one type, one
  // gender), auto-fill the filter so MI doesn't aggregate WPL women's
  // numbers etc. Driven by the team-scoped tournaments list above.
  useEffect(() => {
    if (tournamentsStale) return
    if (!teamForFetch || tournaments.length === 0) return
    if (gender && teamType) return
    const types = new Set(tournaments.map(t => t.team_type).filter(Boolean))
    const genders = new Set(tournaments.map(t => t.gender).filter(Boolean))
    const updates: Record<string, string> = {}
    if (!teamType && types.size === 1) updates.team_type = [...types][0] as string
    if (!gender && genders.size === 1) updates.gender = [...genders][0] as string
    if (Object.keys(updates).length > 0) setUrlParams(updates, { replace: true })
  }, [teamForFetch, tournaments, tournamentsStale, gender, teamType])

  // Intra-tournament rivalry auto-narrow: when BOTH filter_team and
  // filter_opponent are set AND the two teams only ever meet in a
  // single tournament (e.g. MI × CSK → IPL only), auto-set tournament.
  // For multi-tournament rivalries (Ind vs Aus spans bilaterals + ICC)
  // the server returns multiple entries and we leave tournament empty
  // so the user picks manually. We intentionally do NOT use this for
  // single-team scoping — MI alone plays IPL + WPL so the set can look
  // unambiguous while actually hiding the women's side.
  useEffect(() => {
    if (tournamentsStale) return
    if (!filterTeam || !filterOpponent) return
    if (tournament) return
    if (tournaments.length !== 1) return
    setUrlParams({ tournament: tournaments[0].event_name }, { replace: true })
  }, [filterTeam, filterOpponent, tournaments, tournamentsStale, tournament])

  const setGender = (v: string) => {
    const updates: Record<string, string> = { gender: v }
    if (tournament) {
      const t = tournaments.find(x => x.event_name === tournament)
      // Clear the tournament when (a) user picked a specific gender
      // that doesn't match the tournament, OR (b) user cleared the
      // gender entirely — otherwise the auto-correct deep-link
      // effect at the top of this component re-asserts the gender
      // from the tournament's metadata, "springing back" to the
      // value the user just cleared. Cascade-clear instead.
      if (t && (!v || t.gender !== v)) updates.tournament = ''
    }
    setUrlParams(updates)
  }

  const setTeamType = (v: string) => {
    const updates: Record<string, string> = { team_type: v }
    if (tournament) {
      const t = tournaments.find(x => x.event_name === tournament)
      // Same cascade-clear rule as setGender — see comment above.
      if (t && (!v || t.team_type !== v)) updates.tournament = ''
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
  const teamClass = params.get('team_class') || ''
  // `seriesType` itself is declared at the top of the component
  // (used for the /tournaments + /seasons scope-fetch effects).
  // `seriesType ?? ''` is used inline for the select's value attr.

  // Auto-clear team_class when its current value is incompatible with
  // the active team_type. Polymorphic over team_type:
  //   intl → only `full_member` is meaningful
  //   club → only `primary_club` / `secondary_club`
  //   ''   → all values cleared
  // Defensive deep-link guard + Type-segmented-control side effect.
  // Spec: spec-filterbar-team-class-club.md §3 + §4.1.
  useEffect(() => {
    if (!teamClass) return
    let invalid = false
    if (!teamType) invalid = true
    else if (teamType === 'international' && teamClass !== 'full_member') invalid = true
    else if (teamType === 'club' && teamClass !== 'primary_club' && teamClass !== 'secondary_club') invalid = true
    if (invalid) setUrlParams({ team_class: '' }, { replace: true })
  }, [teamType, teamClass])

  const filteredTournaments = tournaments.filter(t => {
    if (teamType && t.team_type !== teamType) return false
    if (gender && t.gender !== gender) return false
    return true
  })

  const segBtn = (active: boolean) => `wisden-seg${active ? ' is-active' : ''}`

  const anyFilterSet = Boolean(gender || teamType || tournament || seasonFrom || seasonTo || filterVenue || teamClass || seriesType)
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
  const setFirstN = (n: number) => {
    // Scope-aware first-N — first N entries of the seasons list.
    // Player-aware on player pages: the seasons list is narrowed
    // to the player's career-in-scope, so first-3 reflects each
    // player's debut arc rather than the dataset's earliest seasons.
    if (seasons.length < n) return
    const first = seasons.slice(0, n)
    const from = first[0]
    const to = first[first.length - 1]
    setUrlParams({ season_from: from, season_to: to })
  }
  const setLastN = (n: number) => {
    if (seasons.length === 0) return
    // Scope-aware last-N — seasons list is already narrowed by
    // gender/team_type/tournament via the seasons-fetch effect. Takes
    // the last N entries (API returns chronological ascending).
    // Player-aware (2026-05-07): for retired players the list ends at
    // their last season, so this no longer gives empty pages.
    const latest = seasons.slice(-n)
    const from = latest[0]
    const to = latest[latest.length - 1]
    setUrlParams({ season_from: from, season_to: to })
  }
  const setPrevN = (n: number) => {
    // Scope-aware prev-N — the N seasons immediately before the
    // last-N window. Useful for "form" comparisons where the
    // current arc is "last 3" and the prior arc is "prev 3."
    if (seasons.length < 2 * n) return
    const prev = seasons.slice(-2 * n, -n)
    const from = prev[0]
    const to = prev[prev.length - 1]
    setUrlParams({ season_from: from, season_to: to })
  }
  const clearAll = () => setUrlParams({
    gender: '', team_type: '', tournament: '',
    season_from: '', season_to: '', filter_venue: '',
    team_class: '', series_type: '',
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

        {/* Series type + Full-members are intl-only universe-narrowings.
         *  They sit BEFORE Tournament because logically you decide
         *  "what kind of competition" before "which competition." For
         *  club contexts both groups hide — bilateral is meaningless
         *  for clubs, and the FM list is a country roster. Stale URL
         *  state (series_type=… set, then user switches to club)
         *  follows the established team_class pattern: backend silently
         *  no-ops, ScopeStatusStrip surfaces the active value below. */}
        {teamType === 'international' && (
          <div className="wisden-filter-group">
            <span className="wisden-filter-label">Series Type</span>
            <select
              value={seriesType ?? ''}
              onChange={e => set('series_type', e.target.value)}
              className="wisden-select"
              title="Restrict to a category of international matches. Bilateral series partitions disjointly from Tournaments (T20 World Cup, Asia Cup, etc.); All shows both."
            >
              <option value="">All</option>
              <option value="bilateral_only">Bilateral series</option>
              <option value="tournament_only">Tournaments only</option>
            </select>
          </div>
        )}

        {teamType === 'international' && (
          <div className="wisden-filter-group">
            <button
              type="button"
              onClick={() => set('team_class', teamClass ? '' : 'full_member')}
              className={segBtn(teamClass === 'full_member')}
              title="Restrict to matches between two ICC full-member nations (excludes associate teams like Scotland, Nepal, USA, …)."
            >
              {teamClass === 'full_member' ? '▣' : '▢'} Full members only
            </button>
          </div>
        )}

        {/* Club tier — polymorphic counterpart to the FM toggle. Three
         *  buttons: All / Primary / Secondary. Primary = marquee
         *  international franchise leagues (IPL, BBL, PSL, …).
         *  Secondary = domestic state/county/provincial competitions
         *  + small-market franchises (Vitality Blast, Syed Mushtaq Ali,
         *  Super Smash, NPL, …). Spec:
         *  internal_docs/spec-filterbar-team-class-club.md §4.1. */}
        {teamType === 'club' && (
          <div className="wisden-filter-group">
            <span className="wisden-filter-label">Tier</span>
            <button
              type="button"
              onClick={() => set('team_class', '')}
              className={segBtn(!teamClass)}
              title="Show every club tournament regardless of tier."
            >
              All
            </button>
            <button
              type="button"
              onClick={() => set('team_class', 'primary_club')}
              className={segBtn(teamClass === 'primary_club')}
              title="Marquee international franchise leagues — IPL, BBL, PSL, BPL, CPL, SA20, ILT20, MLC, LPL, The Hundred (M+W), WBBL, WPL, Women's Cricket Super League."
            >
              Primary
            </button>
            <button
              type="button"
              onClick={() => set('team_class', 'secondary_club')}
              className={segBtn(teamClass === 'secondary_club')}
              title="Domestic state / county / provincial competitions — Vitality Blast, Syed Mushtaq Ali Trophy, CSA T20 Challenge, Super Smash, Nepal Premier League, Women's Super Smash."
            >
              Secondary
            </button>
          </div>
        )}

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
          {seasons.length >= 3 && (
            <button type="button" onClick={() => setFirstN(3)} className="wisden-reset"
              title={`First 3 seasons in scope (${seasons.slice(0, 3).join(', ')})${playerForFetch ? " — the player's earliest seasons" : ''}`}>
              first-3
            </button>
          )}
          <button type="button" onClick={clearSeasons} className="wisden-reset"
            title="Clear season range — show all-time">
            all-time
          </button>
          {seasons.length >= 6 && (
            <button type="button" onClick={() => setPrevN(3)} className="wisden-reset"
              title={`Previous 3 seasons before the most recent 3 (${seasons.slice(-6, -3).join(', ')}) — useful as the prior-arc comparison to "last-3"`}>
              prev-3
            </button>
          )}
          {seasons.length >= 3 && (
            <button type="button" onClick={() => setLastN(3)} className="wisden-reset"
              title={`Last 3 seasons in scope (${seasons.slice(-3).join(', ')})`}>
              last-3
            </button>
          )}
          {latestInScope && (
            <button type="button" onClick={setLatest} className="wisden-reset"
              title={`Jump to latest season in scope (${latestInScope})`}>
              latest
            </button>
          )}
        </div>

        <div className="wisden-filter-group wisden-filter-group-venue">
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
