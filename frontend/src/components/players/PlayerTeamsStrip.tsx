/**
 * Teams-played-for strip — top of the player profile.
 *
 * Lists every team the player has appeared for at the active scope
 * with headline cross-discipline volume (matches · runs · wickets ·
 * catches) and a link into each discipline page filtered to that team.
 * Detailed averages live on those linked pages — this strip is the
 * navigational index of a player's clubs + countries (e.g. Kohli →
 * India + RCB; an overseas franchise journeyman → many).
 *
 * Totals come from /players/{id}/teams, which partitions the team-
 * filtered discipline /summary pages exactly, so the numbers here
 * reconcile with what the links land on.
 */

import { Link } from 'react-router-dom'
import { useFetch } from '../../hooks/useFetch'
import { useFilterDeps } from '../../hooks/useFilterDeps'
import { getPlayerTeams } from '../../api'
import { carryFilters } from './roleUtils'
import TeamLink from '../TeamLink'
import { SectionHeader } from '../ChartHeader'
import type { FilterParams, PlayerTeamTotals } from '../../types'

interface Props {
  playerId: string
  filters: FilterParams
}

function disciplineHref(
  base: '/batting' | '/bowling' | '/fielding',
  playerId: string,
  filters: FilterParams,
  team: string,
): string {
  // Carry the active scope, then pin filter_team to THIS team (the
  // override wins over any filter_team already in carryFilters).
  const qs = new URLSearchParams({
    player: playerId,
    ...carryFilters(filters),
    filter_team: team,
  })
  return `${base}?${qs}`
}

export default function PlayerTeamsStrip({ playerId, filters }: Props) {
  const filterDeps = [playerId, ...useFilterDeps()]
  const fetchState = useFetch<{ teams: PlayerTeamTotals[] } | null>(
    () => getPlayerTeams(playerId, filters),
    filterDeps,
  )
  const teams = fetchState.data?.teams ?? []
  if (fetchState.loading || teams.length === 0) return null

  return (
    <section className="wisden-teams-strip">
      <SectionHeader title="Teams played for" />
      {teams.map(t => (
        <div className="wisden-team-row" key={t.team}>
          <div className="wisden-team-id">
            <TeamLink teamName={t.team} gender={filters.gender} compact />
            <span className="wisden-team-matches">
              <span className="num">{t.matches}</span> {t.matches === 1 ? 'match' : 'matches'}
            </span>
          </div>
          <div className="wisden-team-totals">
            <span>Runs <b className="num">{t.runs.toLocaleString()}</b></span>
            <span>Wkts <b className="num">{t.wickets}</b></span>
            <span>Catches <b className="num">{t.catches}</b></span>
          </div>
          <div className="wisden-team-links">
            <Link className="comp-link" to={disciplineHref('/batting', playerId, filters, t.team)}>Batting</Link>
            <Link className="comp-link" to={disciplineHref('/bowling', playerId, filters, t.team)}>Bowling</Link>
            <Link className="comp-link" to={disciplineHref('/fielding', playerId, filters, t.team)}>Fielding</Link>
          </div>
        </div>
      ))}
    </section>
  )
}
