import type React from 'react'
import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import {
  getTeams, getTeamSummary, getTeamByseason, getTeamVs, getTeamResults,
  getTeamOpponentsMatrix, getTeamPlayersBySeason, getTeamsLanding,
  getTeamBattingSummary, getTeamBattingBySeason, getTeamBattingByPhase, getTeamTopBatters,
  getTeamBattingPhaseSeasonHeatmap,
  getTeamBowlingSummary, getTeamBowlingBySeason, getTeamBowlingByPhase, getTeamTopBowlers,
  getTeamBowlingPhaseSeasonHeatmap,
  getTeamFieldingSummary, getTeamFieldingBySeason, getTeamTopFielders,
  getTeamPartnershipsByWicket, getTeamPartnershipsBestPairs, getTeamPartnershipsHeatmap, getTeamPartnershipsTop,
} from '../api'
import StatCard from '../components/StatCard'
import FlagBadge from '../components/FlagBadge'
import PlayerLink from '../components/PlayerLink'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import LineChart from '../components/charts/LineChart'
import HeatmapChart from '../components/charts/HeatmapChart'
import BubbleMatrix from '../components/charts/BubbleMatrix'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import type {
  TeamInfo, TeamSummary, TeamSeasonRecord, TeamVsOpponent, TeamResult,
  OpponentRollup, OpponentsMatrix, TeamPlayersBySeason, TeamsLanding,
  TeamBattingSummary, TeamBattingSeason, TeamBattingPhase, TeamTopBatter,
  BattingPhaseSeasonHeatmap, BowlingPhaseSeasonHeatmap,
  TeamBowlingSummary, TeamBowlingSeason, TeamBowlingPhase, TeamTopBowler,
  TeamFieldingSummary, TeamFieldingSeason, TeamTopFielder,
  PartnershipByWicket, PartnershipPairEntry, PartnershipBestPairsResponse,
  PartnershipHeatmap, PartnershipTopEntry,
  FilterParams,
} from '../types'

// Tab order: discipline tabs come BEFORE the bare match list so the
// "list of games" sits at the end — same convention as the player
// pages (Batting/Bowling/Fielding all keep "Innings List" last).
const tabs = [
  'By Season', 'vs Opponent',
  'Batting', 'Bowling', 'Fielding', 'Partnerships',
  'Players', 'Match List',
] as const

export default function Teams() {
  const navigate = useNavigate()
  const filters = useFilters()
  const setUrlParams = useSetUrlParams()
  const [selected, setSelected] = useUrlParam('team')
  useDocumentTitle(selected || 'Teams')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const [opponent, setOpponent] = useUrlParam('vs')

  const [teams, setTeams] = useState<TeamInfo[]>([])
  const [query, setQuery] = useState(selected || '')
  const [showDropdown, setShowDropdown] = useState(false)
  const [resultsOffset, setResultsOffset] = useState(0)

  // Team-search dropdown stays a plain useEffect — debounce-style and
  // failure here is non-blocking.
  useEffect(() => {
    if (!query || selected) return
    getTeams({ ...filters, q: query }).then(d => { setTeams(d.teams); setShowDropdown(true) }).catch(() => {})
  }, [filters.gender, filters.team_type, filters.tournament, query, selected])

  const filterDeps = [
    selected, filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
  ]

  // Summary drives the page header — failure blocks the whole tab area.
  const summaryFetch = useFetch<TeamSummary | null>(
    () => selected ? getTeamSummary(selected, filters) : Promise.resolve(null),
    filterDeps,
  )
  const summary = summaryFetch.data

  const seasonsFetch = useFetch<{ seasons: TeamSeasonRecord[] } | null>(
    () => selected ? getTeamByseason(selected, filters) : Promise.resolve(null),
    filterDeps,
  )
  const seasons = seasonsFetch.data?.seasons ?? []

  const vsFetch = useFetch<TeamVsOpponent | null>(
    () => (selected && opponent) ? getTeamVs(selected, opponent, filters) : Promise.resolve(null),
    [...filterDeps, opponent],
  )
  const vsData = vsFetch.data

  const resultsFetch = useFetch<{ results: TeamResult[]; total: number } | null>(
    () => selected
      ? getTeamResults(selected, { ...filters, limit: 50, offset: resultsOffset })
      : Promise.resolve(null),
    [...filterDeps, resultsOffset],
  )
  const results = resultsFetch.data?.results ?? []
  const resultsTotal = resultsFetch.data?.total ?? 0

  const selectTeam = (name: string) => {
    setSelected(name); setQuery(name); setShowDropdown(false)
  }

  // Match-list convention (see CLAUDE.md): the `date` column is the
  // primary link to the scorecard. Keep the row clickable for extra
  // affordance, but the link must exist so users can cmd/ctrl-click
  // open in a new tab.
  const resultColumns: Column<TeamResult>[] = [
    { key: 'date', label: 'Date', sortable: true, format: (_v, r) => (
      <Link to={`/matches/${r.match_id}`} className="comp-link">
        {r.date ?? '-'}
      </Link>
    ) as unknown as string },
    { key: 'opponent', label: 'Opponent', sortable: true },
    { key: 'venue', label: 'Venue' },
    { key: 'tournament', label: 'Tournament' },
    { key: 'result', label: 'Result', sortable: true },
    { key: 'margin', label: 'Margin' },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8 relative max-w-md wisden-playersearch">
        <input type="text" value={query}
          onChange={e => { setQuery(e.target.value); setSelected(''); setShowDropdown(true) }}
          placeholder="Search teams…"
          className="wisden-playersearch-input" />
        {showDropdown && teams.length > 0 && !selected && (
          <ul className="wisden-playersearch-list">
            {teams.slice(0, 20).map(t => (
              <li key={t.name} onClick={() => selectTeam(t.name)}>
                <span className="wisden-playersearch-name">{t.name}</span>
                <span className="wisden-playersearch-meta num">{t.matches} matches</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {!selected && (
        <TeamsLandingBoard filters={filters} filterDeps={filterDeps} onPick={selectTeam} />
      )}

      {/* Only fully-block when we have NO summary yet (initial load). On
          subsequent fetches (filter changes) keep the previous data
          rendered so the tabs don't disappear — show a small inline
          indicator at the top of the page instead. */}
      {selected && !summary && summaryFetch.loading && (
        <Spinner label="Loading team…" size="lg" />
      )}

      {selected && summaryFetch.error && (
        <ErrorBanner
          message={`Could not load team summary: ${summaryFetch.error}`}
          onRetry={summaryFetch.refetch}
        />
      )}

      {selected && summary && (
        <>
          {summaryFetch.loading && (
            <div className="wisden-tab-help" style={{ marginTop: '-1rem', marginBottom: '1rem', fontStyle: 'italic' }}>
              Refreshing…
            </div>
          )}
          <h2 className="wisden-page-title">
            {selected}
            {/* FlagBadge returns null for franchise sides (they're not
                in TEAM_TO_FLAG) — no need to branch on team_type. */}
            <span style={{ marginLeft: '0.6rem', verticalAlign: 'middle' }}>
              <FlagBadge team={selected} size="lg" />
            </span>
          </h2>
          {summary.gender_breakdown && (
            <div className="wisden-gender-notice">
              Showing combined men's &amp; women's. —{' '}
              <button onClick={() => setUrlParams({ gender: 'male' })}>
                Men (<span className="num">{summary.gender_breakdown.male}</span>)
              </button>
              {' · '}
              <button onClick={() => setUrlParams({ gender: 'female' })}>
                Women (<span className="num">{summary.gender_breakdown.female}</span>)
              </button>
            </div>
          )}
          <div className="wisden-statrow">
            <StatCard label="Matches" value={summary.matches} />
            <StatCard label="Wins" value={summary.wins} />
            <StatCard label="Losses" value={summary.losses} />
            <StatCard label="Win %" value={summary.win_pct != null ? `${summary.win_pct}%` : '-'} />
          </div>

          {/* Tier 2 — keepers used by this team, if any identified. */}
          {summary.keepers && summary.keepers.length > 0 && (
            <p className="wisden-tab-help" style={{ marginTop: '-0.5rem', marginBottom: '1rem' }}>
              <span style={{ fontStyle: 'italic' }}>Keepers used:</span>{' '}
              {summary.keepers.slice(0, 6).map((k, i) => (
                <span key={k.person_id}>
                  {i > 0 && ', '}
                  <a href={`/fielding?player=${encodeURIComponent(k.person_id)}&tab=Keeping`}
                     className="comp-link">{k.name}</a>
                  {' '}
                  <span style={{ color: 'var(--ink-faint)' }}>({k.innings_kept})</span>
                </span>
              ))}
              {summary.keepers.length > 6 && (
                <span style={{ color: 'var(--ink-faint)' }}>, +{summary.keepers.length - 6} more</span>
              )}
              {summary.keeper_ambiguous_innings > 0 && (
                <span style={{ color: 'var(--ink-faint)' }}>
                  {' · '}{summary.keeper_ambiguous_innings} innings ambiguous
                </span>
              )}
            </p>
          )}

          <div className="wisden-tabs">
            {tabs.map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`wisden-tab${activeTab === tab ? ' is-active' : ''}`}
              >{tab}</button>
            ))}
          </div>

          <div>
            {activeTab === 'By Season' && (
              <>
                {seasonsFetch.loading && <Spinner label="Loading season records…" />}
                {seasonsFetch.error && (
                  <ErrorBanner
                    message={`Could not load by-season: ${seasonsFetch.error}`}
                    onRetry={seasonsFetch.refetch}
                  />
                )}
                {!seasonsFetch.loading && !seasonsFetch.error && seasons.length > 0 && (
                  <>
                    <h3 className="wisden-section-title">Wins by Season</h3>
                    <BarChart data={seasons} categoryAccessor="season" valueAccessor="wins"
                      categoryLabel="Season" valueLabel="Wins"
                      height={350}
                      topLabelFormat={(d) => d.win_pct != null ? `${d.win_pct}%` : null} />
                  </>
                )}
              </>
            )}

            {activeTab === 'vs Opponent' && selected && (
              <VsOpponentTab
                team={selected}
                filters={filters}
                filterDeps={filterDeps}
                opponent={opponent}
                setOpponent={setOpponent}
                vsData={vsData}
                vsFetch={vsFetch}
              />
            )}

            {activeTab === 'Match List' && (
              <>
                {resultsFetch.loading && <Spinner label="Loading match list…" />}
                {resultsFetch.error && (
                  <ErrorBanner
                    message={`Could not load match list: ${resultsFetch.error}`}
                    onRetry={resultsFetch.refetch}
                  />
                )}
                {!resultsFetch.loading && !resultsFetch.error && (
                  <DataTable columns={resultColumns} data={results}
                    rowKey={r => String(r.match_id)}
                    onRowClick={r => navigate(`/matches/${r.match_id}`)}
                    pagination={{ total: resultsTotal, limit: 50, offset: resultsOffset, onPage: setResultsOffset }} />
                )}
              </>
            )}

            {activeTab === 'Batting' && selected && (
              <BattingTab team={selected} filters={filters} filterDeps={filterDeps} />
            )}
            {activeTab === 'Bowling' && selected && (
              <BowlingTab team={selected} filters={filters} filterDeps={filterDeps} />
            )}
            {activeTab === 'Fielding' && selected && (
              <FieldingTab team={selected} filters={filters} filterDeps={filterDeps} keepers={summary.keepers} />
            )}
            {activeTab === 'Partnerships' && selected && (
              <PartnershipsTab team={selected} filters={filters} filterDeps={filterDeps} />
            )}
            {activeTab === 'Players' && selected && (
              <PlayersTab team={selected} filters={filters} filterDeps={filterDeps} />
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ============================================================
// Batting tab
// ============================================================

interface TabProps {
  team: string
  filters: FilterParams
  filterDeps: unknown[]
}

function BattingTab({ team, filters, filterDeps }: TabProps) {
  const summary = useFetch<TeamBattingSummary | null>(
    () => getTeamBattingSummary(team, filters),
    filterDeps,
  )
  const bySeason = useFetch<{ seasons: TeamBattingSeason[] } | null>(
    () => getTeamBattingBySeason(team, filters),
    filterDeps,
  )
  const byPhase = useFetch<{ phases: TeamBattingPhase[] } | null>(
    () => getTeamBattingByPhase(team, filters),
    filterDeps,
  )
  const topBatters = useFetch<{ top_batters: TeamTopBatter[] } | null>(
    () => getTeamTopBatters(team, { ...filters, limit: 5 }),
    filterDeps,
  )
  const phaseSeason = useFetch<BattingPhaseSeasonHeatmap | null>(
    () => getTeamBattingPhaseSeasonHeatmap(team, filters),
    filterDeps,
  )

  if (summary.loading) return <Spinner label="Loading batting…" />
  if (summary.error) return <ErrorBanner message={`Batting: ${summary.error}`} onRetry={summary.refetch} />
  const s = summary.data
  if (!s) return null

  const batterColumns: Column<TeamTopBatter>[] = [
    { key: 'name', label: 'Batter', format: (_v, r) => (
      <PlayerLink
        personId={r.person_id} name={r.name} role="batter" gender={filters.gender}
        contextLabel={`at ${team}`} contextParams={{ filter_team: team }}
      />
    ) as unknown as string },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'strike_rate', label: 'SR' },
    { key: 'fours', label: '4s' },
    { key: 'sixes', label: '6s' },
    { key: 'innings', label: 'Inns' },
  ]

  return (
    <div className="space-y-6">
      {/* All rows are 5-up so the cards stay the same width across rows
          and Dot % doesn't orphan. Same pattern as the player Batting
          page (Batting.tsx). Combined 50s/100s + Highest/Lowest cards
          let us pack 15 stats into 3 evenly-wide rows. */}
      <div className="wisden-statrow cols-5">
        <StatCard label="Innings" value={s.innings_batted} />
        <StatCard label="Runs" value={s.total_runs.toLocaleString()} />
        <StatCard label="Run rate" value={s.run_rate != null ? s.run_rate.toFixed(2) : '-'} />
        <StatCard label="Boundary %" value={s.boundary_pct != null ? `${s.boundary_pct}%` : '-'} />
        <StatCard label="Dot %" value={s.dot_pct != null ? `${s.dot_pct}%` : '-'} />
      </div>
      <div className="wisden-statrow cols-5">
        <StatCard label="4s" value={s.fours.toLocaleString()} />
        <StatCard label="6s" value={s.sixes.toLocaleString()} />
        <StatCard label="50s" value={s.fifties} />
        <StatCard label="100s" value={s.hundreds} />
        <StatCard label="50s / 100s per inn"
          value={s.innings_batted > 0
            ? `${((s.fifties + s.hundreds) / s.innings_batted).toFixed(2)}`
            : '-'} />
      </div>
      <div className="wisden-statrow cols-5">
        <StatCard label="Avg 1st-inn total"
          value={s.avg_1st_innings_total != null ? s.avg_1st_innings_total.toFixed(1) : '-'} />
        <StatCard label="Avg 2nd-inn total"
          value={s.avg_2nd_innings_total != null ? s.avg_2nd_innings_total.toFixed(1) : '-'} />
        <StatCard label="Highest total"
          value={s.highest_total ? String(s.highest_total.runs) : '-'} />
        <StatCard label="Lowest all-out"
          value={s.lowest_all_out_total ? String(s.lowest_all_out_total.runs) : '-'} />
        <StatCard label="Avg innings total"
          value={s.innings_batted > 0
            ? (s.total_runs / s.innings_batted).toFixed(1)
            : '-'} />
      </div>

      {/* Line charts only when there are 2+ seasons — one data point
          renders an empty chart. Filter collapsed → no charts. */}
      {bySeason.data && bySeason.data.seasons.length >= 2 && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="run_rate"
              title="Run rate by season" xLabel="Season" yLabel="RR" height={280} />
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="avg_innings_total"
              title="Avg innings total by season" xLabel="Season" yLabel="Runs" height={280} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BarChart data={bySeason.data.seasons} categoryAccessor="season" valueAccessor="fours"
              title="Fours by season" categoryLabel="Season" valueLabel="4s" height={280} />
            <BarChart data={bySeason.data.seasons} categoryAccessor="season" valueAccessor="sixes"
              title="Sixes by season" categoryLabel="Season" valueLabel="6s" height={280} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="boundary_pct"
              title="Boundary % by season" xLabel="Season" yLabel="%" height={280} />
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="dot_pct"
              title="Dot % by season" xLabel="Season" yLabel="%" height={280} />
          </div>
        </>
      )}

      {byPhase.data && byPhase.data.phases.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BarChart data={byPhase.data.phases} categoryAccessor="phase" valueAccessor="run_rate"
            title="Run rate by phase" categoryLabel="Phase" valueLabel="RR" height={280} />
          <BarChart
            data={byPhase.data.phases.map(p => ({
              ...p,
              wickets_per_innings: s.innings_batted > 0
                ? +(p.wickets_lost / s.innings_batted).toFixed(2)
                : 0,
            }))}
            categoryAccessor="phase" valueAccessor="wickets_per_innings"
            title="Wickets lost per innings — by phase" categoryLabel="Phase" valueLabel="wkts/inn"
            height={280} />
        </div>
      )}

      {phaseSeason.data && phaseSeason.data.seasons.length >= 2 && phaseSeason.data.cells.length > 0 && (
        <>
          <div>
            <h3 className="wisden-section-title">Run rate — phase × season</h3>
            <HeatmapChart
              cells={phaseSeason.data.cells.map(c => ({
                x: c.season, y: c.phase, value: c.run_rate, n: c.balls,
              }))}
              xCategories={phaseSeason.data.seasons}
              yCategories={phaseSeason.data.phases}
              formatYTick={y => String(y)}
              valueSuffix="RR"
              formatValue={v => v.toFixed(2)}
              nLabel="balls"
            />
          </div>
          <div>
            <h3 className="wisden-section-title">Wickets lost per innings — phase × season</h3>
            <HeatmapChart
              cells={phaseSeason.data.cells.map(c => ({
                x: c.season, y: c.phase, value: c.wickets_per_innings, n: c.innings,
              }))}
              xCategories={phaseSeason.data.seasons}
              yCategories={phaseSeason.data.phases}
              formatYTick={y => String(y)}
              valueSuffix="wkts/inn"
              formatValue={v => v.toFixed(2)}
              nLabel="innings"
            />
          </div>
        </>
      )}

      {topBatters.data && topBatters.data.top_batters.length > 0 && (
        <div>
          <h3 className="wisden-section-title">Top 5 Batters</h3>
          <DataTable columns={batterColumns} data={topBatters.data.top_batters}
            rowKey={r => r.person_id}
          />
        </div>
      )}
    </div>
  )
}

// ============================================================
// Bowling tab
// ============================================================

function BowlingTab({ team, filters, filterDeps }: TabProps) {
  const summary = useFetch<TeamBowlingSummary | null>(
    () => getTeamBowlingSummary(team, filters),
    filterDeps,
  )
  const bySeason = useFetch<{ seasons: TeamBowlingSeason[] } | null>(
    () => getTeamBowlingBySeason(team, filters),
    filterDeps,
  )
  const byPhase = useFetch<{ phases: TeamBowlingPhase[] } | null>(
    () => getTeamBowlingByPhase(team, filters),
    filterDeps,
  )
  const topBowlers = useFetch<{ top_bowlers: TeamTopBowler[] } | null>(
    () => getTeamTopBowlers(team, { ...filters, limit: 5 }),
    filterDeps,
  )
  const phaseSeason = useFetch<BowlingPhaseSeasonHeatmap | null>(
    () => getTeamBowlingPhaseSeasonHeatmap(team, filters),
    filterDeps,
  )

  if (summary.loading) return <Spinner label="Loading bowling…" />
  if (summary.error) return <ErrorBanner message={`Bowling: ${summary.error}`} onRetry={summary.refetch} />
  const s = summary.data
  if (!s) return null

  const bowlerColumns: Column<TeamTopBowler>[] = [
    { key: 'name', label: 'Bowler', format: (_v, r) => (
      <PlayerLink
        personId={r.person_id} name={r.name} role="bowler" gender={filters.gender}
        contextLabel={`at ${team}`} contextParams={{ filter_team: team }}
      />
    ) as unknown as string },
    { key: 'wickets', label: 'Wkts', sortable: true },
    { key: 'runs_conceded', label: 'Runs' },
    { key: 'overs', label: 'Overs' },
    { key: 'economy', label: 'Econ' },
    { key: 'average', label: 'Avg' },
    { key: 'strike_rate', label: 'SR' },
  ]

  return (
    <div className="space-y-6">
      <div className="wisden-statrow">
        <StatCard label="Innings" value={s.innings_bowled} />
        <StatCard label="Overs" value={s.overs.toFixed(1)} />
        <StatCard label="Wickets" value={s.wickets.toLocaleString()} />
        <StatCard label="Runs conceded" value={s.runs_conceded.toLocaleString()} />
      </div>
      <div className="wisden-statrow">
        <StatCard label="Economy" value={s.economy != null ? s.economy.toFixed(2) : '-'} />
        <StatCard label="Average" value={s.average != null ? s.average.toFixed(2) : '-'} />
        <StatCard label="Strike rate" value={s.strike_rate != null ? s.strike_rate.toFixed(2) : '-'} />
        <StatCard label="Dot %" value={s.dot_pct != null ? `${s.dot_pct}%` : '-'} />
      </div>
      <div className="wisden-statrow">
        <StatCard label="Avg opp total"
          value={s.avg_opposition_total != null ? s.avg_opposition_total.toFixed(1) : '-'} />
        <StatCard label="Worst conceded"
          value={s.worst_conceded ? String(s.worst_conceded.runs) : '-'} />
        <StatCard label="Best defence"
          value={s.best_defence ? String(s.best_defence.runs) : '-'} />
        <StatCard label="Wides/match"
          value={s.wides_per_match != null ? s.wides_per_match.toFixed(1) : '-'} />
      </div>

      {bySeason.data && bySeason.data.seasons.length >= 2 && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="economy"
              title="Economy by season" xLabel="Season" yLabel="Econ" height={280} />
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="avg_opposition_total"
              title="Avg opposition total by season" xLabel="Season" yLabel="Runs" height={280} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BarChart data={bySeason.data.seasons} categoryAccessor="season" valueAccessor="wickets"
              title="Wickets by season" categoryLabel="Season" valueLabel="Wickets" height={280} />
            <BarChart data={bySeason.data.seasons} categoryAccessor="season" valueAccessor="runs_conceded"
              title="Runs conceded by season" categoryLabel="Season" valueLabel="Runs" height={280} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="dot_pct"
              title="Dot % by season" xLabel="Season" yLabel="%" height={280} />
            <BarChart data={bySeason.data.seasons} categoryAccessor="season" valueAccessor="boundaries_conceded"
              title="Boundaries conceded by season" categoryLabel="Season" valueLabel="4s+6s" height={280} />
          </div>
        </>
      )}

      {byPhase.data && byPhase.data.phases.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <BarChart data={byPhase.data.phases} categoryAccessor="phase" valueAccessor="economy"
            title="Economy by phase" categoryLabel="Phase" valueLabel="Econ" height={280} />
          <BarChart
            data={byPhase.data.phases.map(p => ({
              ...p,
              wickets_per_innings: s.innings_bowled > 0
                ? +(p.wickets / s.innings_bowled).toFixed(2)
                : 0,
            }))}
            categoryAccessor="phase" valueAccessor="wickets_per_innings"
            title="Wickets taken per innings — by phase" categoryLabel="Phase" valueLabel="wkts/inn"
            height={280} />
        </div>
      )}

      {phaseSeason.data && phaseSeason.data.seasons.length >= 2 && phaseSeason.data.cells.length > 0 && (
        <>
          <div>
            <h3 className="wisden-section-title">Economy — phase × season (low = good)</h3>
            <HeatmapChart
              cells={phaseSeason.data.cells.map(c => ({
                x: c.season, y: c.phase, value: c.economy, n: c.balls,
              }))}
              xCategories={phaseSeason.data.seasons}
              yCategories={phaseSeason.data.phases}
              invert
              formatYTick={y => String(y)}
              valueSuffix="econ"
              formatValue={v => v.toFixed(2)}
              nLabel="balls"
            />
          </div>
          <div>
            <h3 className="wisden-section-title">Wickets taken per innings — phase × season</h3>
            <HeatmapChart
              cells={phaseSeason.data.cells.map(c => ({
                x: c.season, y: c.phase, value: c.wickets_per_innings, n: c.innings,
              }))}
              xCategories={phaseSeason.data.seasons}
              yCategories={phaseSeason.data.phases}
              formatYTick={y => String(y)}
              valueSuffix="wkts/inn"
              formatValue={v => v.toFixed(2)}
              nLabel="innings"
            />
          </div>
        </>
      )}

      {topBowlers.data && topBowlers.data.top_bowlers.length > 0 && (
        <div>
          <h3 className="wisden-section-title">Top 5 Bowlers</h3>
          <DataTable columns={bowlerColumns} data={topBowlers.data.top_bowlers}
            rowKey={r => r.person_id}
          />
        </div>
      )}
    </div>
  )
}

// ============================================================
// Fielding tab
// ============================================================

interface FieldingTabProps extends TabProps {
  keepers: TeamSummary['keepers']
}

function FieldingTab({ team, filters, filterDeps, keepers }: FieldingTabProps) {
  const summary = useFetch<TeamFieldingSummary | null>(
    () => getTeamFieldingSummary(team, filters),
    filterDeps,
  )
  const bySeason = useFetch<{ seasons: TeamFieldingSeason[] } | null>(
    () => getTeamFieldingBySeason(team, filters),
    filterDeps,
  )
  const topFielders = useFetch<{ top_fielders: TeamTopFielder[] } | null>(
    () => getTeamTopFielders(team, { ...filters, limit: 5 }),
    filterDeps,
  )

  if (summary.loading) return <Spinner label="Loading fielding…" />
  if (summary.error) return <ErrorBanner message={`Fielding: ${summary.error}`} onRetry={summary.refetch} />
  const s = summary.data
  if (!s) return null

  const fielderColumns: Column<TeamTopFielder>[] = [
    { key: 'name', label: 'Fielder', format: (_v, r) => (
      <PlayerLink
        personId={r.person_id} name={r.name} role="fielder" gender={filters.gender}
        contextLabel={`at ${team}`} contextParams={{ filter_team: team }}
      />
    ) as unknown as string },
    { key: 'catches', label: 'Catches', sortable: true },
    { key: 'caught_and_bowled', label: 'C&B' },
    { key: 'stumpings', label: 'Stmp' },
    { key: 'run_outs', label: 'RO' },
    { key: 'total', label: 'Total', sortable: true },
  ]

  return (
    <div className="space-y-6">
      <div className="wisden-statrow">
        <StatCard label="Matches" value={s.matches} />
        <StatCard label="Catches" value={s.catches.toLocaleString()} />
        <StatCard label="Stumpings" value={s.stumpings} />
        <StatCard label="Run-outs" value={s.run_outs} />
      </div>
      <div className="wisden-statrow">
        <StatCard label="Catches/match"
          value={s.catches_per_match != null ? s.catches_per_match.toFixed(2) : '-'} />
        <StatCard label="Stumpings/match"
          value={s.stumpings_per_match != null ? s.stumpings_per_match.toFixed(2) : '-'} />
        <StatCard label="Run-outs/match"
          value={s.run_outs_per_match != null ? s.run_outs_per_match.toFixed(2) : '-'} />
        <StatCard label="C&B" value={s.caught_and_bowled} />
      </div>

      {bySeason.data && bySeason.data.seasons.length >= 2 && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="catches_per_match"
              title="Catches per match by season" xLabel="Season" yLabel="per match" height={280} />
            <LineChart data={bySeason.data.seasons} xAccessor="season" yAccessor="total_dismissals_contributed"
              title="Total dismissals contributed" xLabel="Season" yLabel="Dismissals" height={280} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BarChart data={bySeason.data.seasons} categoryAccessor="season" valueAccessor="catches"
              title="Catches by season" categoryLabel="Season" valueLabel="Catches" height={280} />
            <BarChart data={bySeason.data.seasons} categoryAccessor="season" valueAccessor="run_outs"
              title="Run-outs by season" categoryLabel="Season" valueLabel="RO" height={280} />
          </div>
        </>
      )}

      {topFielders.data && topFielders.data.top_fielders.length > 0 && (
        <div>
          <h3 className="wisden-section-title">Top 5 Fielders</h3>
          <DataTable columns={fielderColumns} data={topFielders.data.top_fielders}
            rowKey={r => r.person_id}
          />
        </div>
      )}

      {keepers && keepers.length > 0 && (
        <div>
          <h3 className="wisden-section-title">Wicketkeepers</h3>
          <p className="wisden-tab-help">
            Innings kept per player (Tier 2 attribution — see
            <Link to="/fielding" className="comp-link" style={{ marginLeft: 4 }}>Fielding page</Link>
            {' '}for confidence breakdown).
          </p>
          <DataTable
            columns={[
              { key: 'name', label: 'Keeper', format: (_v, r) => (
                <Link to={`/fielding?player=${encodeURIComponent(r.person_id)}&tab=Keeping`} className="comp-link">
                  {r.name}
                </Link>
              ) as unknown as string },
              { key: 'innings_kept', label: 'Innings kept', sortable: true },
            ]}
            data={keepers}
            rowKey={k => k.person_id}
          />
        </div>
      )}
    </div>
  )
}

// ============================================================
// vs Opponent tab
// ============================================================

interface VsOpponentTabProps extends TabProps {
  opponent: string
  setOpponent: (v: string) => void
  vsData: TeamVsOpponent | null | undefined
  vsFetch: { loading: boolean; error: string | null; refetch: () => void }
}

function VsOpponentTab({
  team, filters, filterDeps, opponent, setOpponent, vsData, vsFetch,
}: VsOpponentTabProps) {
  const matrix = useFetch<OpponentsMatrix | null>(
    () => getTeamOpponentsMatrix(team, { ...filters, top_n: 25 }),
    filterDeps,
  )

  const singleSeason = !!filters.season_from && filters.season_from === filters.season_to

  return (
    <div className="space-y-6">
      {/* Rollup table: opponents × record. Horizontal stacked bar per
          row makes it scannable — width = matches, fill = W/L/T split.
          Click an opponent name to drill down into the detail panel. */}
      {matrix.loading && !matrix.data && <Spinner label="Loading opponents matrix…" />}
      {matrix.error && <ErrorBanner message={`Opponents matrix: ${matrix.error}`} onRetry={matrix.refetch} />}

      {matrix.data && matrix.data.opponents.length > 0 && (
        <div>
          <h3 className="wisden-section-title">Record vs each opponent</h3>
          <OpponentStackedBars
            data={matrix.data.opponents}
            selected={opponent}
            onPick={setOpponent}
          />
        </div>
      )}

      {/* Drill-down comes RIGHT after the rollup so a click on the
          stacked bars surfaces the detail without scrolling past
          another chart. The volume-vs-time view goes at the bottom. */}
      {opponent && (
        <div className="wisden-drilldown">
          <h3 className="wisden-section-title">
            vs {opponent}
            {' '}
            <button
              onClick={() => setOpponent('')}
              className="comp-link"
              style={{
                fontSize: '0.8rem', fontStyle: 'italic',
                background: 'none', border: 'none', padding: 0, cursor: 'pointer',
              }}
            >clear</button>
            {' · '}
            <Link
              to={`/head-to-head?mode=team&team1=${encodeURIComponent(team)}&team2=${encodeURIComponent(opponent)}${filters.gender ? `&gender=${filters.gender}` : ''}${filters.team_type ? `&team_type=${filters.team_type}` : ''}`}
              className="comp-link"
              style={{ fontSize: '0.8rem', fontStyle: 'italic' }}
            >
              See full rivalry →
            </Link>
          </h3>
          {vsFetch.loading && <Spinner label={`Loading ${opponent} detail…`} />}
          {vsFetch.error && (
            <ErrorBanner message={`Head-to-head: ${vsFetch.error}`} onRetry={vsFetch.refetch} />
          )}
          {vsData && !vsFetch.loading && (
            <>
              <div className="wisden-statrow">
                <StatCard label="Matches" value={vsData.overall.matches} />
                <StatCard label="Wins" value={vsData.overall.wins} />
                <StatCard label="Losses" value={vsData.overall.losses} />
                <StatCard label="Ties" value={vsData.overall.ties} />
              </div>
              {vsData.by_season.length >= 2 && (
                <>
                  <h3 className="wisden-section-title">Wins vs {opponent} by Season</h3>
                  <BarChart
                    data={vsData.by_season.map(s => ({
                      ...s,
                      win_pct: s.matches > 0 ? Math.round((s.wins / s.matches) * 100) : null,
                    }))}
                    categoryAccessor="season" valueAccessor="wins"
                    categoryLabel="Season" valueLabel="Wins"
                    height={300}
                    topLabelFormat={(d) => d.win_pct != null ? `${d.win_pct}%` : null} />
                </>
              )}
              {vsData.matches.length > 0 && (
                <div>
                  <h4 className="wisden-section-title" style={{ marginTop: '2rem' }}>Matches</h4>
                  <DataTable
                    columns={[
                      { key: 'date', label: 'Date', format: (_, r) => (
                        <Link to={`/matches/${r.match_id}`} className="comp-link">
                          {r.date ?? '-'}
                        </Link>
                      ) as unknown as string },
                      { key: 'venue', label: 'Venue' },
                      { key: 'tournament', label: 'Tournament' },
                      { key: 'result', label: 'Result' },
                      { key: 'margin', label: 'Margin' },
                    ]}
                    data={vsData.matches}
                    rowKey={r => String(r.match_id)}
                  />
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Volume-vs-time view at the BOTTOM. Bubble area = matches that
          season; colour bucket = win-share band (lost-more / even /
          won-more). Crucially this encodes BOTH volume and outcome —
          a 50% win rate over 30 vs Delhi looks visibly different from
          50% over 4 vs Lucknow. Hidden when a single season is in
          scope (one column of bubbles is just a list). */}
      {!singleSeason && matrix.data && matrix.data.cells.length > 0
        && matrix.data.seasons.length >= 2 && (
        <div>
          <h3 className="wisden-section-title">Matches × outcome — opponent × season</h3>
          <BubbleMatrix
            cells={matrix.data.cells.map(c => ({
              x: c.season,
              y: c.opponent,
              size: c.matches,
              value: c.win_pct,
              meta: { wins: c.wins, losses: c.losses, ties: c.ties },
            }))}
            xCategories={matrix.data.seasons}
            yCategories={matrix.data.opponents.map(o => o.name)}
            onCellClick={cell => setOpponent(String(cell.y))}
            tooltipBody={c => {
              const m = c.meta as Record<string, number> | undefined
              const w = m?.wins ?? 0
              const l = m?.losses ?? 0
              const t = m?.ties ?? 0
              const pct = c.value != null ? `${Math.round(c.value)}%` : '—'
              return `${c.size} matches · ${w}–${l}${t > 0 ? `–${t}t` : ''} (${pct} won)`
            }}
          />
        </div>
      )}
    </div>
  )
}

// Inline HTML stacked-bar: one row per opponent, segments sized by the
// opponent's (wins, losses, ties, no_results) counts relative to the
// max-matches-seen in the dataset. Width-normalizes against the team's
// heaviest opponent so the rivalry lines up visually.
function OpponentStackedBars({
  data,
  selected,
  onPick,
}: {
  data: OpponentRollup[]
  selected?: string
  onPick: (name: string) => void
}) {
  const max = data.reduce((m, o) => Math.max(m, o.matches), 1)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {data.map(o => {
        const bar = (n: number, color: string, label: string) =>
          n > 0 ? (
            <div
              key={label}
              title={`${label}: ${n}`}
              style={{
                background: color,
                width: `${(n / max) * 100}%`,
                height: '100%',
              }}
            />
          ) : null
        const isSel = selected === o.name
        return (
          <button
            key={o.name}
            onClick={() => onPick(o.name)}
            style={{
              display: 'grid',
              gridTemplateColumns: '200px 1fr 80px',
              alignItems: 'center',
              gap: 12,
              padding: '4px 8px',
              background: isSel ? 'var(--bg-soft)' : 'transparent',
              border: isSel ? '1px solid var(--ink-faint)' : '1px solid transparent',
              cursor: 'pointer',
              textAlign: 'left',
              fontFamily: 'var(--serif)',
              color: 'var(--ink)',
            }}
          >
            <span style={{ fontSize: 14 }}>{o.name}</span>
            <span style={{ display: 'flex', height: 18, background: 'var(--bg-soft)' }}>
              {bar(o.wins,       '#2E6FB5', 'wins')}
              {bar(o.ties,       '#C9871F', 'ties')}
              {bar(o.no_results, '#8A7D70', 'no result')}
              {bar(o.losses,     '#7A1F1F', 'losses')}
            </span>
            <span className="num" style={{ fontSize: 13, color: 'var(--ink-faint)', textAlign: 'right' }}>
              {o.wins}–{o.losses}
              {o.ties > 0 ? `–${o.ties}t` : ''}
              {' '}
              <span style={{ fontStyle: 'italic' }}>
                ({o.win_pct != null ? `${o.win_pct}%` : '—'})
              </span>
            </span>
          </button>
        )
      })}
      <p className="wisden-tab-help" style={{ marginTop: 6 }}>
        <span style={{ color: '#2E6FB5' }}>■ wins</span>{' '}
        <span style={{ color: '#7A1F1F' }}>■ losses</span>{' '}
        <span style={{ color: '#C9871F' }}>■ ties</span>{' '}
        <span style={{ color: '#8A7D70' }}>■ no result</span>{' · '}
        bar width is proportional to the most-played opponent.
      </p>
    </div>
  )
}

// ============================================================
// Partnerships tab
// ============================================================

function PartnershipsTab({ team, filters, filterDeps }: TabProps) {
  const [side, setSide] = useUrlParam('partnership_side', 'batting')
  const safeSide = (side === 'bowling' ? 'bowling' : 'batting') as 'batting' | 'bowling'

  const byWicket = useFetch<{ by_wicket: PartnershipByWicket[] } | null>(
    () => getTeamPartnershipsByWicket(team, { ...filters, side: safeSide }),
    [...filterDeps, safeSide],
  )
  const bestPairs = useFetch<PartnershipBestPairsResponse | null>(
    () => getTeamPartnershipsBestPairs(team, { ...filters, side: safeSide, min_n: 2, top_n: 3 }),
    [...filterDeps, safeSide],
  )
  const heatmap = useFetch<PartnershipHeatmap | null>(
    () => getTeamPartnershipsHeatmap(team, { ...filters, side: safeSide }),
    [...filterDeps, safeSide],
  )
  const top = useFetch<{ partnerships: PartnershipTopEntry[] } | null>(
    () => getTeamPartnershipsTop(team, { ...filters, side: safeSide, limit: 10 }),
    [...filterDeps, safeSide],
  )

  const singleSeason = !!filters.season_from && filters.season_from === filters.season_to

  const wicketColumns: Column<PartnershipByWicket>[] = [
    { key: 'wicket_number', label: 'Wkt' },
    { key: 'n', label: 'n', sortable: true },
    { key: 'avg_runs', label: 'Avg runs' },
    { key: 'avg_balls', label: 'Avg balls' },
    { key: 'best_runs', label: 'Best', sortable: true },
    {
      key: 'best_partnership',
      label: 'Highest single partnership',
      format: (_, row) => {
        const bp = row.best_partnership
        if (!bp) return '—'
        const b1 = bp.batter1.person_id
          ? <Link to={`/batting?player=${encodeURIComponent(bp.batter1.person_id)}`} className="comp-link">{bp.batter1.name}</Link>
          : bp.batter1.name
        const b2 = bp.batter2.person_id
          ? <Link to={`/batting?player=${encodeURIComponent(bp.batter2.person_id)}`} className="comp-link">{bp.batter2.name}</Link>
          : bp.batter2.name
        const ids = [bp.batter1.person_id, bp.batter2.person_id].filter(Boolean).join(',')
        const qs = ids ? `?highlight_batter=${encodeURIComponent(ids)}` : ''
        return (
          <>
            {b1} + {b2}
            {' · vs '}{bp.opponent}{', '}{bp.season}{' '}
            <Link to={`/matches/${bp.match_id}${qs}`} className="comp-link">
              → match details
            </Link>
          </>
        ) as unknown as string
      },
    },
  ]

  // Flatten the top-N pairs per wicket into one row each. We show the
  // wicket number only on the rank-1 row to make the grouping readable
  // (rank-2 / rank-3 rows leave the cell blank).
  type FlatPair = PartnershipPairEntry & { wicket_number: number; isFirst: boolean }
  const flatPairs: FlatPair[] = (bestPairs.data?.by_wicket ?? []).flatMap(w =>
    w.pairs.map((p, i) => ({ ...p, wicket_number: w.wicket_number, isFirst: i === 0 }))
  )
  const bestPairColumns: Column<FlatPair>[] = [
    { key: 'wicket_number', label: 'Wkt', format: (_, r) => r.isFirst ? String(r.wicket_number) : '' },
    { key: 'rank', label: '#', format: (_, r) => String(r.rank) },
    { key: 'batter1', label: 'Pair', format: (_, r) => {
      const b1 = r.batter1.person_id
        ? <Link to={`/batting?player=${encodeURIComponent(r.batter1.person_id)}`} className="comp-link">{r.batter1.name}</Link>
        : r.batter1.name
      const b2 = r.batter2.person_id
        ? <Link to={`/batting?player=${encodeURIComponent(r.batter2.person_id)}`} className="comp-link">{r.batter2.name}</Link>
        : r.batter2.name
      return <>{b1} + {b2}</> as unknown as string
    } },
    { key: 'n', label: 'n' },
    { key: 'avg_runs', label: 'Avg runs', format: (v) => Number(v).toFixed(1) },
    { key: 'avg_balls', label: 'Avg balls', format: (v) => Number(v).toFixed(1) },
    { key: 'total_runs', label: 'Total runs (rank by)' },
    { key: 'best_runs', label: 'Best single' },
  ]

  return (
    <div className="space-y-6">
      <div className="wisden-filter-group">
        <span className="wisden-filter-label">View</span>
        <button
          onClick={() => setSide('batting')}
          className={`wisden-tab${safeSide === 'batting' ? ' is-active' : ''}`}
          style={{ marginRight: 8 }}
        >Our partnerships</button>
        <button
          onClick={() => setSide('bowling')}
          className={`wisden-tab${safeSide === 'bowling' ? ' is-active' : ''}`}
        >Partnerships conceded</button>
      </div>

      {byWicket.loading && <Spinner label="Loading partnerships…" />}
      {byWicket.error && <ErrorBanner message={`Partnerships: ${byWicket.error}`} onRetry={byWicket.refetch} />}

      {byWicket.data && byWicket.data.by_wicket.length > 0 && (
        <div>
          <h3 className="wisden-section-title">
            {safeSide === 'batting' ? 'By wicket — our partnerships' : 'By wicket — runs conceded'}
          </h3>
          <DataTable columns={wicketColumns} data={byWicket.data.by_wicket}
            rowKey={r => String(r.wicket_number)} />
        </div>
      )}

      {bestPairs.data && flatPairs.length > 0 && (
        <div>
          <h3 className="wisden-section-title">
            {safeSide === 'batting'
              ? 'Most prolific pairs — by wicket (top 3 by total runs together)'
              : 'Most prolific opposition pairs — by wicket (top 3 by total runs against us)'}
          </h3>
          <p className="wisden-tab-help" style={{ marginTop: '-0.5rem' }}>
            Top {bestPairs.data.top_n} pairs per wicket, ranked by{' '}
            <strong>total runs scored together</strong> (= n × average per
            partnership) — so the ordering rewards the volume of opportunities
            AND consistency, not a single big stand. Pairs need ≥{' '}
            {bestPairs.data.min_n} partnerships at that wicket to qualify. The{' '}
            <em>Avg runs</em> column lets you read quality alongside volume.
          </p>
          <DataTable columns={bestPairColumns} data={flatPairs}
            rowKey={r => `${r.wicket_number}-${r.rank}`} />
        </div>
      )}

      {!singleSeason && heatmap.data && heatmap.data.cells.length > 0 && (
        <div>
          <h3 className="wisden-section-title">Season × Wicket (avg runs)</h3>
          <HeatmapChart
            cells={heatmap.data.cells.map(c => ({
              x: c.season, y: c.wicket_number, value: c.avg_runs, n: c.n,
            }))}
            xCategories={heatmap.data.seasons}
            yCategories={heatmap.data.wickets}
            invert={safeSide === 'bowling' /* conceding less is better → low = good */}
            valueSuffix="runs"
            nLabel="partnerships"
          />
        </div>
      )}

      {top.data && top.data.partnerships.length > 0 && (
        <div>
          <h3 className="wisden-section-title">
            Top 10 {safeSide === 'batting' ? 'partnerships' : 'partnerships conceded'}
          </h3>
          <DataTable
            columns={[
              {
                key: 'runs',
                label: 'Runs',
                format: (_, r) => `${r.runs} (${r.balls})`,
              },
              { key: 'wicket_number', label: 'Wkt',
                format: (_, r) => r.unbroken ? 'unbk' : String(r.wicket_number ?? '-') },
              { key: 'batter1', label: 'Batter 1', format: (_, r) => (
                r.batter1.person_id ? (
                  <>
                    <Link to={`/batting?player=${encodeURIComponent(r.batter1.person_id)}`} className="comp-link">
                      {r.batter1.name}
                    </Link>
                    {' '}{r.batter1.runs}({r.batter1.balls})
                  </>
                ) : `${r.batter1.name} ${r.batter1.runs}(${r.batter1.balls})`
              ) as unknown as string },
              { key: 'batter2', label: 'Batter 2', format: (_, r) => (
                r.batter2.person_id ? (
                  <>
                    <Link to={`/batting?player=${encodeURIComponent(r.batter2.person_id)}`} className="comp-link">
                      {r.batter2.name}
                    </Link>
                    {' '}{r.batter2.runs}({r.batter2.balls})
                  </>
                ) : `${r.batter2.name} ${r.batter2.runs}(${r.batter2.balls})`
              ) as unknown as string },
              { key: 'opponent', label: 'Opponent' },
              { key: 'date', label: 'Date', format: (_, r) => {
                // Highlight both batters of the partnership on the scorecard.
                const ids = [r.batter1.person_id, r.batter2.person_id].filter(Boolean).join(',')
                const qs = ids ? `?highlight_batter=${encodeURIComponent(ids)}` : ''
                return (
                  <Link to={`/matches/${r.match_id}${qs}`} className="comp-link">
                    {r.date ?? '-'}
                  </Link>
                ) as unknown as string
              } },
              { key: 'season', label: 'Season' },
            ]}
            data={top.data.partnerships}
            rowKey={r => String(r.partnership_id)}
          />
        </div>
      )}
    </div>
  )
}

// ============================================================
// Players tab — all players per season, 3 per row, alphabetical.
// Each row: name (→ lifetime), bat avg (→ season batting),
// bowl SR (→ season bowling). Turnover printed beside each season
// heading from the second listed season onward.
// ============================================================

function PlayersTab({ team, filters, filterDeps }: TabProps) {
  const fetch = useFetch<TeamPlayersBySeason | null>(
    () => getTeamPlayersBySeason(team, filters),
    filterDeps,
  )
  if (fetch.loading && !fetch.data) return <Spinner label="Loading players…" />
  if (fetch.error) {
    return <ErrorBanner message={`Could not load players: ${fetch.error}`} onRetry={fetch.refetch} />
  }
  const seasons = fetch.data?.seasons ?? []
  if (seasons.length === 0) {
    return <div className="wisden-empty">No players found for the current filters.</div>
  }

  // Carry the current non-season filters through on stat links so
  // clicking into a player's season respects gender / team_type /
  // tournament.
  const carryFilters: Record<string, string> = {}
  if (filters.gender) carryFilters.gender = filters.gender
  if (filters.team_type) carryFilters.team_type = filters.team_type
  if (filters.tournament) carryFilters.tournament = filters.tournament

  const seasonLink = (path: string, personId: string, season: string) => {
    const qs = new URLSearchParams({
      player: personId,
      season_from: season,
      season_to: season,
      ...carryFilters,
    })
    return `${path}?${qs.toString()}`
  }

  return (
    <div>
      <div className="wisden-tab-help" style={{ marginTop: '-0.5rem', marginBottom: '1rem' }}>
        Players who appeared in the XI each season, alphabetical. A player who played in
        multiple seasons is listed under each.
        <div style={{ marginTop: '0.4rem', fontSize: '0.85em' }}>
          Format: <b>Name</b> <span className="num">avg</span> / <span className="num">SR</span> —
          {' '}<b>Name</b> links to lifetime stats;
          {' '}<span className="num">avg</span> = batting average that season (→ batting page for that season),
          {' '}<span className="num">SR</span> = bowling strike rate that season (→ bowling page for that season).
          <b> NA</b> means didn't bat / never out, or didn't bowl / took no wicket.
        </div>
      </div>
      {seasons.map(bucket => (
        <div key={bucket.season} style={{ marginBottom: '2rem' }}>
          <h3 className="wisden-section-title">
            {bucket.season}{' '}
            <span style={{ color: 'var(--ink-faint)', fontSize: '0.85em', fontWeight: 'normal' }}>
              ({bucket.players.length})
            </span>
            {bucket.turnover && (
              <span style={{ color: 'var(--ink-faint)', fontSize: '0.75em', fontWeight: 'normal', marginLeft: '0.75rem' }}>
                vs {bucket.turnover.prev_season} · +{bucket.turnover.new_count} new · −{bucket.turnover.left_count} left
              </span>
            )}
          </h3>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: '0.4rem 1.5rem',
          }}>
            {bucket.players.map(p => (
              <div key={p.person_id} style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
                <Link
                  to={`/batting?player=${encodeURIComponent(p.person_id)}`}
                  className="comp-link"
                >{p.name}</Link>
                <span className="num" style={{ color: 'var(--ink-faint)', fontSize: '0.85em', whiteSpace: 'nowrap' }}>
                  {p.bat_avg != null ? (
                    <Link to={seasonLink('/batting', p.person_id, bucket.season)} className="comp-link">
                      {p.bat_avg.toFixed(p.bat_avg % 1 === 0 ? 0 : 1)}
                    </Link>
                  ) : 'NA'}
                  {' / '}
                  {p.bowl_sr != null ? (
                    <Link to={seasonLink('/bowling', p.person_id, bucket.season)} className="comp-link">
                      {p.bowl_sr.toFixed(p.bowl_sr % 1 === 0 ? 0 : 1)}
                    </Link>
                  ) : 'NA'}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ============================================================
// Teams landing board — two-column directory shown below the
// search bar when no team is selected. Left: international teams
// split regular (ICC full members) vs associate. Right: clubs
// grouped by tournament. All counts respect the current FilterBar
// scope, so e.g. Pune Supergiants drop out of windows outside
// 2016–2017 naturally.
// ============================================================

interface TeamsLandingBoardProps {
  filters: FilterParams
  filterDeps: unknown[]
  onPick: (name: string) => void
}

function TeamsLandingBoard({ filters, filterDeps, onPick }: TeamsLandingBoardProps) {
  const fetch = useFetch<TeamsLanding | null>(
    () => getTeamsLanding(filters),
    filterDeps,
  )
  if (fetch.loading && !fetch.data) return <Spinner label="Loading teams…" />
  if (fetch.error) {
    return <ErrorBanner message={`Could not load teams: ${fetch.error}`} onRetry={fetch.refetch} />
  }
  const data = fetch.data
  if (!data) return null

  const menRegular = data.international.men.regular
  const menAssociate = data.international.men.associate
  const womenRegular = data.international.women.regular
  const womenAssociate = data.international.women.associate
  const clubFranchise = data.club.franchise_leagues
  const clubDomestic = data.club.domestic_leagues
  const clubWomen = data.club.women_franchise
  const clubOther = data.club.other
  const showMen = menRegular.length + menAssociate.length > 0
  const showWomen = womenRegular.length + womenAssociate.length > 0
  const showIntl = showMen || showWomen
  const hasDomestic = clubDomestic.length > 0
  const hasClubRight = clubFranchise.length + clubWomen.length + clubOther.length > 0
  const showLeft = showIntl || hasDomestic
  const showRight = hasClubRight
  if (!showLeft && !showRight) {
    return <div className="wisden-empty">No teams match the current filters.</div>
  }

  const showGenderBadge = !filters.gender

  // Click a team — pre-set the gender filter so the team page scopes
  // correctly. Without this, picking "India" with no gender shows
  // combined men+women stats which the user almost never wants.
  const handlePick = (name: string, gender?: string | null) => {
    if (gender && !filters.gender) {
      // Mutate URL gender then pick the team. handlePick is called
      // from within a button click so the parent's setSelected applies
      // after this microtask — set gender first for atomicity.
      const url = new URL(window.location.href)
      url.searchParams.set('gender', gender)
      window.history.replaceState({}, '', url)
    }
    onPick(name)
  }

  const renderTeam = (t: { name: string; matches: number; gender?: string | null }) => {
    const gLabel = showGenderBadge && t.gender
      ? (t.gender === 'female' ? "women's" : "men's")
      : null
    return (
      <button
        key={`${t.name}|${t.gender ?? ''}`}
        onClick={() => handlePick(t.name, t.gender)}
        className="comp-link"
        style={{
          background: 'none', border: 0, padding: 0, cursor: 'pointer',
          textAlign: 'left', font: 'inherit',
        }}
      >
        {t.name}
        {gLabel && (
          <span className="wisden-tile-faint" style={{ fontSize: '0.78em' }}>
            {' '}{gLabel}
          </span>
        )}
        {' '}
        <span className="num" style={{ color: 'var(--ink-faint)', fontSize: '0.85em' }}>
          ({t.matches})
        </span>
      </button>
    )
  }

  // <details> = built-in collapsible. Open by default for International;
  // Club tournaments collapsed by default since there are many of them.
  const Section = ({ title, count, defaultOpen, children }: {
    title: React.ReactNode
    count?: number
    defaultOpen: boolean
    children: React.ReactNode
  }) => (
    <details open={defaultOpen} className="wisden-collapse">
      <summary>
        <span className="wisden-collapse-title">{title}</span>
        {count !== undefined && (
          <span className="wisden-collapse-count num">{count}</span>
        )}
      </summary>
      <div className="wisden-collapse-body">
        {children}
      </div>
    </details>
  )

  return (
    <div>
      <div className="wisden-tab-help" style={{ marginBottom: '1rem' }}>
        Pick a team below, or search above. Match counts respect the filters at the
        top — change gender, type, tournament, or season to narrow.
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {showLeft && (
          <div>
            {showIntl && <h3 className="wisden-section-title">International</h3>}
            {showMen && (
              <>
                <div className="coverage-head" style={{ marginTop: '0.5rem', marginBottom: '0.25rem' }}>
                  Men's
                </div>
                {menRegular.length > 0 && (
                  <Section title="Full members" count={menRegular.length} defaultOpen={true}>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                      {menRegular.map(renderTeam)}
                    </div>
                  </Section>
                )}
                {menAssociate.length > 0 && (
                  <Section title="Associate" count={menAssociate.length} defaultOpen={false}>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                      {menAssociate.map(renderTeam)}
                    </div>
                  </Section>
                )}
              </>
            )}
            {showWomen && (
              <>
                <div className="coverage-head" style={{ marginTop: '1rem', marginBottom: '0.25rem' }}>
                  Women's
                </div>
                {womenRegular.length > 0 && (
                  <Section title="Full members" count={womenRegular.length} defaultOpen={true}>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                      {womenRegular.map(renderTeam)}
                    </div>
                  </Section>
                )}
                {womenAssociate.length > 0 && (
                  <Section title="Associate" count={womenAssociate.length} defaultOpen={false}>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                      {womenAssociate.map(renderTeam)}
                    </div>
                  </Section>
                )}
              </>
            )}
            {/* Domestic / national championships (SMAT, Vitality Blast,
                CSA T20 Challenge) sit here in the left column to balance
                the layout — conceptually closer to national cricket than
                to franchise leagues, and keeps the right column from
                dominating the page. */}
            {hasDomestic && (
              <>
                <h3
                  className="wisden-section-title"
                  style={{ marginTop: showIntl ? '2rem' : undefined }}
                >
                  Domestic / national championships
                </h3>
                {clubDomestic.map(g => (
                  <Section
                    key={g.tournament}
                    title={g.tournament}
                    count={g.matches}
                    defaultOpen={false}
                  >
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                      {g.teams.map(renderTeam)}
                    </div>
                  </Section>
                ))}
              </>
            )}
          </div>
        )}
        {showRight && (
          <div>
            <h3 className="wisden-section-title">Clubs</h3>
            {clubFranchise.length > 0 && (
              <>
                <div className="coverage-head" style={{ marginTop: '0.5rem', marginBottom: '0.25rem' }}>
                  Franchise leagues
                </div>
                {clubFranchise.map((g, i) => (
                  <Section
                    key={g.tournament}
                    title={g.tournament}
                    count={g.matches}
                    // Only the top franchise (IPL) open by default; BBL
                    // et al collapsed so the women's section below gets
                    // a fair share of above-the-fold real estate.
                    defaultOpen={i < 1}
                  >
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                      {g.teams.map(renderTeam)}
                    </div>
                  </Section>
                ))}
              </>
            )}
            {/* Domestic / national championships moved to the left
                column (under International) for page balance — they're
                national-level competitions, conceptually closer to
                International than to franchise leagues. */}
            {clubWomen.length > 0 && (
              <>
                <div className="coverage-head" style={{ marginTop: '1rem', marginBottom: '0.25rem' }}>
                  Women's franchise leagues
                </div>
                {clubWomen.map((g, i) => (
                  <Section
                    key={g.tournament}
                    title={g.tournament}
                    count={g.matches}
                    // Top women's franchise (WBBL) open by default,
                    // matching the one-open-per-subsection rule used
                    // for the men's franchise list above.
                    defaultOpen={i < 1}
                  >
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                      {g.teams.map(renderTeam)}
                    </div>
                  </Section>
                ))}
              </>
            )}
            {clubOther.length > 0 && (
              <>
                <div className="coverage-head" style={{ marginTop: '1rem', marginBottom: '0.25rem' }}>
                  Other tournaments
                </div>
                {clubOther.map(g => (
                  <Section
                    key={g.tournament}
                    title={g.tournament}
                    count={g.matches}
                    defaultOpen={false}
                  >
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                      {g.teams.map(renderTeam)}
                    </div>
                  </Section>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
