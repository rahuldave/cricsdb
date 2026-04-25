import { useState } from 'react'
import { useFetch } from '../../hooks/useFetch'
import { getTournaments, getSeasons } from '../../api'
import VenueSearch from '../VenueSearch'
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

const cmp = (a: string, b?: string) => a !== (b ?? '')

export default function SlotScopeEditor({
  primary, team, initial, onApply, onReset, onCancel,
}: Props) {
  const [tournament, setTournament] = useState(initial.tournament ?? primary.tournament ?? '')
  const [seasonFrom, setSeasonFrom] = useState(initial.season_from ?? primary.season_from ?? '')
  const [seasonTo, setSeasonTo]     = useState(initial.season_to   ?? primary.season_to   ?? '')
  const [filterVenue, setFilterVenue] = useState(initial.filter_venue ?? primary.filter_venue ?? '')
  const [seriesType, setSeriesType] = useState(initial.series_type ?? primary.series_type ?? '')

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
      tournament: tournament || undefined,
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
          <option value="">All tournaments</option>
          {tournaments.map(t => (
            <option key={t.event_name} value={t.event_name}>{t.event_name}</option>
          ))}
        </select>
      </div>
      <div style={fieldStyle}>
        <span style={labelStyle}>Season</span>
        <select value={seasonFrom} onChange={e => setSeasonFrom(e.target.value)}>
          <option value="">—</option>
          {seasons.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <span style={{ opacity: 0.6 }}>to</span>
        <select value={seasonTo} onChange={e => setSeasonTo(e.target.value)}>
          <option value="">—</option>
          {seasons.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div style={fieldStyle}>
        <span style={labelStyle}>Venue</span>
        <div style={{ flex: 1 }}>
          <VenueSearch
            value={filterVenue}
            onSelect={setFilterVenue}
            onClear={() => setFilterVenue('')}
            placeholder="Any venue"
          />
        </div>
      </div>
      <div style={fieldStyle}>
        <span style={labelStyle}>Series</span>
        <select value={seriesType} onChange={e => setSeriesType(e.target.value)}>
          <option value="">— inherit —</option>
          <option value="all">All matches</option>
          <option value="bilateral_only">Bilaterals only</option>
          <option value="tournament_only">Tournaments only</option>
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
