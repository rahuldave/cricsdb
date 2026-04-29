import { useState } from 'react'
import { useFetch } from '../../hooks/useFetch'
import { getTournaments, getSeasons } from '../../api'
import VenueSearch from '../VenueSearch'
import { ANY_SENTINEL } from '../../hooks/useUrlState'
import type { FilterParams } from '../../types'
import type { SlotOverrides } from '../../hooks/useCompareSlots'

interface Props {
  primary: FilterParams
  team?: string
  initial: SlotOverrides
  onApply: (overrides: SlotOverrides) => void
  onReset: () => void
  onCancel: () => void
}

// Editor state encodes the user's intent for each field as one of:
//  - '' (empty)  → inherit primary (no override)
//  - ANY_SENTINEL ('__any__') → explicit empty, do NOT inherit
//  - any other string → narrow to that value
//
// `cmp(local, primaryVal)` decides whether to write an override on
// Apply. `__any__` always counts as an override (it's the sentinel).
const cmp = (a: string, b?: string) => a !== (b ?? '') && a !== ''

// Translate stored override (which may be ANY_SENTINEL) → editor state.
// Stored sentinel keeps the literal '__any__' string so the dropdown's
// "(any)" option stays selected on round-trip.
const toEditorValue = (override: string | undefined, primaryVal?: string): string => {
  if (override === undefined) return primaryVal ?? ''
  return override
}

export default function SlotScopeEditor({
  primary, team, initial, onApply, onReset, onCancel,
}: Props) {
  const [tournament, setTournament] = useState(toEditorValue(initial.tournament, primary.tournament))
  const [seasonFrom, setSeasonFrom] = useState(toEditorValue(initial.season_from, primary.season_from))
  const [seasonTo, setSeasonTo]     = useState(toEditorValue(initial.season_to,   primary.season_to))
  const [filterVenue, setFilterVenue] = useState(toEditorValue(initial.filter_venue, primary.filter_venue))
  const [seriesType, setSeriesType] = useState(toEditorValue(initial.series_type, primary.series_type))
  const [teamClass, setTeamClass]   = useState(toEditorValue(initial.team_class,  primary.team_class))
  const [inning, setInning]         = useState(toEditorValue(initial.inning,      primary.inning))

  const isInternational = primary.team_type === 'international'

  // For fields where primary HAS a value, expose an "(any — show all)"
  // option in the dropdown — selecting it broadens the slot past
  // primary's narrowing. For fields primary doesn't narrow, the option
  // is meaningless (clearing == inheriting primary's already-empty
  // value), so we hide it.
  const showAny = {
    tournament: !!primary.tournament,
    season:     !!(primary.season_from || primary.season_to),
    venue:      !!primary.filter_venue,
    series:     !!primary.series_type,
    teamClass:  !!primary.team_class,
    inning:     !!primary.inning,
  }

  const tournamentsFetch = useFetch(
    () => getTournaments({
      team,
      gender: primary.gender,
      team_type: primary.team_type,
    }),
    [team, primary.gender, primary.team_type],
  )
  const seasonsFetch = useFetch(
    () => getSeasons({
      team,
      gender: primary.gender,
      team_type: primary.team_type,
      tournament: (tournament && tournament !== ANY_SENTINEL) ? tournament : undefined,
    }),
    [team, primary.gender, primary.team_type, tournament],
  )

  const handleApply = () => {
    const o: SlotOverrides = {}
    if (cmp(tournament, primary.tournament))   o.tournament   = tournament
    if (cmp(seasonFrom, primary.season_from))  o.season_from  = seasonFrom
    if (cmp(seasonTo,   primary.season_to))    o.season_to    = seasonTo
    if (cmp(filterVenue, primary.filter_venue)) o.filter_venue = filterVenue
    if (cmp(seriesType, primary.series_type))  o.series_type  = seriesType
    if (cmp(teamClass, primary.team_class))    o.team_class   = teamClass
    if (cmp(inning,    primary.inning))        o.inning       = inning
    onApply(o)
  }

  const tournaments = tournamentsFetch.data?.tournaments ?? []
  const seasons     = seasonsFetch.data?.seasons ?? []

  const fieldStyle: React.CSSProperties = { marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }
  const labelStyle: React.CSSProperties = { minWidth: '5rem', fontSize: '0.85em', opacity: 0.8 }

  return (
    <div className="wisden-slot-scope-editor" style={{
      border: '1px solid var(--ink-3, rgba(0,0,0,0.2))',
      padding: '0.65rem',
      marginTop: '0.4rem',
      marginBottom: '0.5rem',
      background: 'var(--bg-soft, rgba(0,0,0,0.03))',
      fontSize: '0.85em',
    }}>
      <div style={fieldStyle}>
        <span style={labelStyle}>Tournament</span>
        <select value={tournament} onChange={e => setTournament(e.target.value)} style={{ flex: 1 }}>
          <option value="">— inherit primary —</option>
          {showAny.tournament && (
            <option value={ANY_SENTINEL}>(any — show all tournaments)</option>
          )}
          {tournaments.map(t => (
            <option key={t.event_name} value={t.event_name}>{t.event_name}</option>
          ))}
        </select>
      </div>
      <div style={fieldStyle}>
        <span style={labelStyle}>Season</span>
        <select value={seasonFrom} onChange={e => setSeasonFrom(e.target.value)}>
          <option value="">— inherit —</option>
          {showAny.season && <option value={ANY_SENTINEL}>(any)</option>}
          {seasons.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <span style={{ opacity: 0.6 }}>to</span>
        <select value={seasonTo} onChange={e => setSeasonTo(e.target.value)}>
          <option value="">— inherit —</option>
          {showAny.season && <option value={ANY_SENTINEL}>(any)</option>}
          {seasons.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div style={fieldStyle}>
        <span style={labelStyle}>Venue</span>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <div style={{ flex: 1 }}>
            <VenueSearch
              value={filterVenue === ANY_SENTINEL ? '' : filterVenue}
              onSelect={setFilterVenue}
              onClear={() => setFilterVenue('')}
              placeholder={filterVenue === ANY_SENTINEL ? '(any venue)' : 'Inherit primary'}
            />
          </div>
          {showAny.venue && (
            <button
              type="button"
              className="comp-link"
              onClick={() => setFilterVenue(ANY_SENTINEL)}
              title="Override to all venues — broadens past primary's venue narrowing"
              style={{ fontSize: '0.85em' }}
            >
              any
            </button>
          )}
        </div>
      </div>
      {isInternational && (
        <div style={fieldStyle}>
          <span style={labelStyle}>Series</span>
          <select value={seriesType} onChange={e => setSeriesType(e.target.value)}>
            <option value="">— inherit —</option>
            {showAny.series && <option value={ANY_SENTINEL}>(any — all series)</option>}
            <option value="bilateral_only">Bilaterals only</option>
            <option value="tournament_only">Tournaments only</option>
          </select>
        </div>
      )}
      {isInternational && (
        <div style={fieldStyle}>
          <span style={labelStyle}>Class</span>
          <select
            value={teamClass}
            onChange={e => setTeamClass(e.target.value)}
            title="Narrow the pool to matches where both teams are ICC full members (excludes associate teams like Namibia, USA, Nepal …)."
          >
            <option value="">— inherit —</option>
            {showAny.teamClass && (
              <option value={ANY_SENTINEL}>(any — all teams, override primary)</option>
            )}
            <option value="full_member">Full members only</option>
          </select>
        </div>
      )}
      <div style={fieldStyle}>
        <span style={labelStyle}>Innings</span>
        <select
          value={inning}
          onChange={e => setInning(e.target.value)}
          title={
            "1st innings = matches' inning_number=0; 2nd innings = inning_number=1.\n\n" +
            "On Compare slots this is dual-meaning: BATTING row reads matches where this team BATTED FIRST (= they batted in inning 0); " +
            "BOWLING and FIELDING rows read matches where this team BOWLED FIRST (= opposition batted in inning 0). " +
            "Two complementary subsets of the team's match log, surfaced together as 'first-up activity across roles'."
          }
        >
          <option value="">— inherit —</option>
          {showAny.inning && (
            <option value={ANY_SENTINEL}>(any — all innings)</option>
          )}
          <option value="0">1st innings only</option>
          <option value="1">2nd innings only</option>
        </select>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.4rem' }}>
        <button type="button" className="comp-link" onClick={handleApply}>Apply</button>
        <button type="button" className="comp-link" onClick={onReset} title="Drop all overrides — slot inherits primary">Reset to primary</button>
        <button type="button" className="comp-link" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
