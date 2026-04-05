import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getTournaments, getSeasons } from '../api'
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
  const [params, setParams] = useSearchParams()
  const [tournaments, setTournaments] = useState<Tournament[]>([])
  const [seasons, setSeasons] = useState<string[]>([])

  useEffect(() => {
    getTournaments().then(d => setTournaments(d.tournaments)).catch(() => {})
    getSeasons().then(d => setSeasons(d.seasons)).catch(() => {})
  }, [])

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const gender = params.get('gender') || ''
  const teamType = params.get('team_type') || ''
  const tournament = params.get('tournament') || ''
  const seasonFrom = params.get('season_from') || ''
  const seasonTo = params.get('season_to') || ''

  const filteredTournaments = tournaments.filter(t => {
    if (teamType && t.team_type !== teamType) return false
    if (gender && t.gender !== gender) return false
    return true
  })

  return (
    <div className="flex flex-wrap items-center gap-3 bg-gray-50 border-b border-gray-200 px-4 py-2 text-sm">
      {/* Gender */}
      <div className="flex rounded-md border border-gray-300 overflow-hidden">
        {['', 'male', 'female'].map(v => (
          <button key={v} onClick={() => set('gender', v)}
            className={`px-3 py-1 ${gender === v ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'}`}
          >{v === '' ? 'All' : v === 'male' ? 'Men' : 'Women'}</button>
        ))}
      </div>

      {/* Team Type */}
      <div className="flex rounded-md border border-gray-300 overflow-hidden">
        {['', 'international', 'club'].map(v => (
          <button key={v} onClick={() => set('team_type', v)}
            className={`px-3 py-1 ${teamType === v ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'}`}
          >{v === '' ? 'All' : v === 'international' ? 'Intl' : 'Club'}</button>
        ))}
      </div>

      {/* Tournament */}
      <select value={tournament} onChange={e => set('tournament', e.target.value)}
        className="rounded-md border border-gray-300 px-2 py-1 bg-white text-gray-700">
        <option value="">All Tournaments</option>
        {filteredTournaments.map(t => (
          <option key={t.event_name} value={t.event_name}>{t.event_name} ({t.matches})</option>
        ))}
      </select>

      {/* Season Range */}
      <select value={seasonFrom} onChange={e => set('season_from', e.target.value)}
        className="rounded-md border border-gray-300 px-2 py-1 bg-white text-gray-700">
        <option value="">From</option>
        {seasons.map(s => <option key={s} value={s}>{s}</option>)}
      </select>
      <span className="text-gray-400">-</span>
      <select value={seasonTo} onChange={e => set('season_to', e.target.value)}
        className="rounded-md border border-gray-300 px-2 py-1 bg-white text-gray-700">
        <option value="">To</option>
        {seasons.map(s => <option key={s} value={s}>{s}</option>)}
      </select>
    </div>
  )
}
