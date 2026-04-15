import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch, type FetchState } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { useDefaultSeasonWindow } from '../hooks/useDefaultSeasonWindow'
import PlayerSearch from '../components/PlayerSearch'
import FlagBadge from '../components/FlagBadge'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import LineChart from '../components/charts/LineChart'
import ScatterChart from '../components/charts/ScatterChart'
import DonutChart from '../components/charts/DonutChart'
import { WISDEN, WISDEN_PHASES } from '../components/charts/palette'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import {
  getBatterSummary, getBatterInnings, getBatterVsBowlers, getBatterByOver,
  getBatterByPhase, getBatterBySeason, getBatterDismissals, getBatterInterWicket,
  getBattingLeaders,
} from '../api'
import type {
  PlayerSearchResult, BattingSummary, BattingInnings, BowlerMatchup,
  OverStats, PhaseStats, SeasonBattingStats, DismissalAnalysis, InterWicketStats,
  BattingLeaders, BattingLeaderEntry, FilterParams,
} from '../types'

// Small helper for the consistent loading/error pattern in each tab.
function TabState({ fetch }: { fetch: FetchState<unknown> }) {
  if (fetch.loading) return <Spinner label="Loading…" />
  if (fetch.error) return <ErrorBanner message={fetch.error} onRetry={fetch.refetch} />
  return null
}

const tabs = ['By Season', 'By Over', 'By Phase', 'vs Bowlers', 'Dismissals', 'Inter-Wicket', 'Innings List'] as const
const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

export default function Batting() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const setUrlParams = useSetUrlParams()

  const [inningsOffset, setInningsOffset] = useState(0)
  const [selectedBowlerId, setSelectedBowlerId] = useState<string | null>(null)

  const handleSelect = (p: PlayerSearchResult) => {
    setUrlParams({ player: p.id, tab: 'By Season' })
  }

  const filterDeps = [
    playerId, filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
  ]

  // Summary drives the page header — page-level state
  const summaryFetch = useFetch<BattingSummary | null>(
    () => playerId ? getBatterSummary(playerId, filters) : Promise.resolve(null),
    filterDeps,
  )
  const summary = summaryFetch.data
  useDocumentTitle(summary ? `${summary.name} — Batting` : playerId ? null : 'Batting')

  // Per-tab fetches: each is gated on `activeTab === '...'` so only the
  // visible tab does network work. Switching tabs re-runs the gated fetch.
  const seasonFetch = useFetch<{ by_season: SeasonBattingStats[] } | null>(
    () => playerId && activeTab === 'By Season'
      ? getBatterBySeason(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const seasonData = seasonFetch.data?.by_season ?? []

  const overFetch = useFetch<{ by_over: OverStats[] } | null>(
    () => playerId && activeTab === 'By Over'
      ? getBatterByOver(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const overData = overFetch.data?.by_over ?? []

  const phaseFetch = useFetch<{ by_phase: PhaseStats[] } | null>(
    () => playerId && activeTab === 'By Phase'
      ? getBatterByPhase(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const phaseData = phaseFetch.data?.by_phase ?? []

  const matchupsFetch = useFetch<{ matchups: BowlerMatchup[] } | null>(
    () => playerId && activeTab === 'vs Bowlers'
      ? getBatterVsBowlers(playerId, { ...filters, min_balls: 6 })
      : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const bowlerMatchups = matchupsFetch.data?.matchups ?? []

  const dismissalsFetch = useFetch<DismissalAnalysis | null>(
    () => playerId && activeTab === 'Dismissals'
      ? getBatterDismissals(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const dismissals = dismissalsFetch.data

  const interWicketFetch = useFetch<{ inter_wicket: InterWicketStats[] } | null>(
    () => playerId && activeTab === 'Inter-Wicket'
      ? getBatterInterWicket(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const interWicket = interWicketFetch.data?.inter_wicket ?? []

  const inningsFetch = useFetch<{ innings: BattingInnings[]; total: number } | null>(
    () => playerId && activeTab === 'Innings List'
      ? getBatterInnings(playerId, { ...filters, limit: 50, offset: inningsOffset })
      : Promise.resolve(null),
    [...filterDeps, activeTab, inningsOffset],
  )
  const innings = inningsFetch.data?.innings ?? []
  const inningsTotal = inningsFetch.data?.total ?? 0

  const inningsColumns: Column<BattingInnings>[] = [
    { key: 'date', label: 'Date', sortable: true, format: (v: any, r: any) => (
      <Link to={`/matches/${r.match_id}?highlight_batter=${encodeURIComponent(playerId || '')}`}
        className="comp-link" onClick={e => e.stopPropagation()}>{v || '-'}</Link>
    ) as unknown as string },
    { key: 'opponent', label: 'Opponent', sortable: true },
    { key: 'tournament', label: 'Tournament' },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'fours', label: '4s' },
    { key: 'sixes', label: '6s' },
    { key: 'strike_rate', label: 'SR', sortable: true, format: (v: any) => fmt(v) },
    { key: 'how_out', label: 'Dismissal', format: (_: any, r: any) => r.not_out ? 'not out' : String(r.how_out || '-') },
  ]

  const bowlerColumns: Column<BowlerMatchup>[] = [
    { key: 'bowler_name', label: 'Bowler', sortable: true, format: (_v: any, r: any) => (
      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: '0.5em' }}>
        <span>{r.bowler_name}</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--ink-faint)' }}>
          (<Link to={`/bowling?player=${encodeURIComponent(r.bowler_id)}`}
            className="comp-link" onClick={e => e.stopPropagation()}>stats</Link>
          {' · '}
          <Link to={`/head-to-head?batter=${encodeURIComponent(playerId || '')}&bowler=${encodeURIComponent(r.bowler_id)}`}
            className="comp-link" onClick={e => e.stopPropagation()}>h2h</Link>)
        </span>
      </span>
    ) as unknown as string },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'dismissals', label: 'Outs', sortable: true },
    { key: 'strike_rate', label: 'SR', sortable: true, format: (v: any) => fmt(v) },
    { key: 'average', label: 'Avg', sortable: true, format: (v: any) => fmt(v) },
    { key: 'balls_per_boundary', label: 'B/Bnd', sortable: true, format: (v: any) => fmt(v) },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <PlayerSearch role="batter" onSelect={handleSelect} placeholder="Search for a batter…" />
      </div>

      {!playerId && <BattingLandingBoard filters={filters} filterDeps={filterDeps} />}

      {playerId && summaryFetch.loading && <Spinner label="Loading batter…" size="lg" />}

      {playerId && summaryFetch.error && (
        <ErrorBanner
          message={`Could not load batter: ${summaryFetch.error}`}
          onRetry={summaryFetch.refetch}
        />
      )}

      {playerId && summary && !summaryFetch.loading && (
        <>
          <h2 className="wisden-page-title">
            {summary.name}
            {summary.nationalities?.length > 0 && (
              <span style={{ marginLeft: '0.6rem', display: 'inline-flex', gap: '0.35rem', alignItems: 'center' }}>
                {summary.nationalities.map(n => (
                  <FlagBadge key={`${n.team}-${n.gender}`} team={n.team} gender={n.gender} size="lg" linkTo />
                ))}
              </span>
            )}
          </h2>
          <div className="wisden-statrow cols-5">
            <StatCard label="Matches" value={summary.matches} />
            <StatCard label="Innings" value={summary.innings} />
            <StatCard label="Runs" value={summary.runs} />
            <StatCard label="Average" value={fmt(summary.average)} />
            <StatCard label="Strike Rate" value={fmt(summary.strike_rate)} />
          </div>
          <div className="wisden-statrow cols-5">
            <StatCard label="Boundaries" value={summary.boundaries} subtitle={`${summary.fours} 4s, ${summary.sixes} 6s`} />
            <StatCard label="B/Four" value={fmt(summary.balls_per_four)} />
            <StatCard label="B/Boundary" value={fmt(summary.balls_per_boundary)} />
            <StatCard label="Dot %" value={summary.dot_pct != null ? `${summary.dot_pct}%` : '-'} />
            <StatCard label="50s / 100s" value={`${summary.fifties} / ${summary.hundreds}`} />
          </div>

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
                <TabState fetch={seasonFetch as FetchState<unknown>} />
                {!seasonFetch.loading && !seasonFetch.error && seasonData.length > 0 && (
                  <>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <BarChart data={seasonData} categoryAccessor="season" valueAccessor="runs"
                        title="Runs by Season" categoryLabel="Season" valueLabel="Runs"
                        height={350} />
                      <BarChart data={seasonData.filter(s => s.strike_rate != null)}
                        categoryAccessor="season" valueAccessor={(d: Record<string, any>) => d.strike_rate ?? 0}
                        title="Strike Rate by Season" categoryLabel="Season" valueLabel="Strike Rate"
                        height={350} />
                    </div>
                    {seasonData.some(s => s.season.includes('/')) && (
                      <p className="wisden-tab-help">
                        Seasons like 2025/26 are Oct–Mar tournaments (BBL, Super Smash, SA20,
                        internationals, T20 World Cups). Plain years like 2025 are tournaments
                        within one calendar year (e.g. IPL, which runs Mar–May and never spans
                        two calendar years except the COVID-disrupted 2020/21).
                      </p>
                    )}
                  </>
                )}
              </>
            )}

            {activeTab === 'By Over' && (
              <>
                <TabState fetch={overFetch as FetchState<unknown>} />
                {!overFetch.loading && !overFetch.error && overData.length > 0 && (
                  <BarChart
                    data={overData.map(o => ({
                      ...o, over: `${o.over_number}`,
                      phase: o.over_number <= 6 ? 'Powerplay' : o.over_number <= 15 ? 'Middle' : 'Death',
                    }))}
                    categoryAccessor="over" valueAccessor={(d: Record<string, any>) => (d.strike_rate as number) ?? 0}
                    title="Strike Rate by Over" categoryLabel="Over" valueLabel="Strike Rate"
                    colorBy="phase" colorScheme={WISDEN_PHASES}
                    height={350} />
                )}
              </>
            )}

            {activeTab === 'By Phase' && (
              <>
                <TabState fetch={phaseFetch as FetchState<unknown>} />
                {!phaseFetch.loading && !phaseFetch.error && phaseData.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-0 wisden-phase-first">
                    {phaseData.map(p => (
                      <div key={p.phase} className="wisden-phaseblock">
                        <h3>{p.phase}</h3>
                        <div className="wisden-phaseblock-overs">Overs {p.overs}</div>
                        <div className="wisden-phaseblock-grid">
                          <div><span className="lbl">Runs</span></div><div className="num">{p.runs}</div>
                          <div><span className="lbl">Balls</span></div><div className="num">{p.balls}</div>
                          <div><span className="lbl">SR</span></div><div className="num">{fmt(p.strike_rate)}</div>
                          <div><span className="lbl">Dots</span></div><div className="num">{fmt(p.dot_pct)}%</div>
                          <div><span className="lbl">4s</span></div><div className="num">{p.fours}</div>
                          <div><span className="lbl">6s</span></div><div className="num">{p.sixes}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {activeTab === 'vs Bowlers' && (
              <>
                <TabState fetch={matchupsFetch as FetchState<unknown>} />
                {!matchupsFetch.loading && !matchupsFetch.error && bowlerMatchups.length > 0 && (() => {
                  const valid = bowlerMatchups.filter(m => m.strike_rate != null && m.average != null)
                  // Top 8 by balls faced get a name label directly on the chart.
                  // Semiotic v3 uses `widget` annotations anchored via the same field
                  // names as the chart's accessors (here: strike_rate and average).
                  const topByBalls = [...valid].sort((a, b) => (b.balls ?? 0) - (a.balls ?? 0)).slice(0, 8)
                  const annotations: Record<string, any>[] = topByBalls.map(m => ({
                    type: 'widget',
                    strike_rate: m.strike_rate,
                    average: m.average,
                    dy: -12,
                    content: (
                      <span style={{
                        fontSize: 11, fontFamily: 'var(--serif)', fontStyle: 'italic',
                        color: 'var(--ink)',
                        background: 'rgba(250,247,240,0.7)', padding: '0 3px',
                        whiteSpace: 'nowrap',
                        textShadow: '0 0 2px rgba(250,247,240,0.95)',
                      }}>{m.bowler_name}</span>
                    ),
                  }))
                  // If a row is selected, draw a highlight ring around it.
                  // Semiotic v3's `enclose` needs >= 2 coordinates (it uses
                  // d3.packEnclose for a hull), so for a single-point ring
                  // use `highlight` which filters chart data by field/value.
                  const selected = selectedBowlerId
                    ? valid.find(m => m.bowler_id === selectedBowlerId)
                    : null
                  if (selected) {
                    annotations.push({
                      type: 'highlight',
                      field: 'bowler_id',
                      value: selectedBowlerId,
                      color: 'var(--accent)',
                      r: 14,
                    })
                    // Use `label` (pure SVG text via d3-annotation) rather
                    // than `widget` (foreignObject + HTML span). Safari has
                    // long-standing bugs reusing foreignObject contents
                    // when React props change with the same key, so the
                    // selected name pill stays stale. The top-N labels
                    // above don't change, so they can stay as widgets.
                    annotations.push({
                      type: 'label',
                      strike_rate: selected.strike_rate,
                      average: selected.average,
                      label: selected.bowler_name,
                      dx: 24, dy: -28,
                      color: 'var(--accent)',
                    })
                  }
                  return (
                    <div>
                      <p className="wisden-tab-help">
                        Hover any dot to see the bowler. Top 8 by balls faced are labelled.
                        Click a row in the table to find that bowler on the chart.
                      </p>
                      <ScatterChart
                        data={valid}
                        xAccessor="strike_rate"
                        yAccessor="average"
                        sizeBy="balls"
                        title="SR vs Average (dot size = balls faced)"
                        xLabel="Strike Rate" yLabel="Average" height={400}
                        tooltip={{
                          title: 'bowler_name',
                          fields: ['balls', 'runs', 'dismissals', 'strike_rate', 'average'],
                        }}
                        annotations={annotations}
                        pointIdAccessor="bowler_id"
                      />
                      <div className="mt-4">
                        <DataTable
                          columns={bowlerColumns}
                          data={bowlerMatchups}
                          rowKey={(r: Record<string, any>) => r.bowler_id}
                          highlightKey={selectedBowlerId}
                          onRowClick={(r: Record<string, any>) => setSelectedBowlerId(r.bowler_id)}
                        />
                      </div>
                    </div>
                  )
                })()}
              </>
            )}

            {activeTab === 'Dismissals' && (
              <>
                <TabState fetch={dismissalsFetch as FetchState<unknown>} />
                {!dismissalsFetch.loading && !dismissalsFetch.error && dismissals && (
                  <div className="grid grid-cols-1 lg:grid-cols-[350px_minmax(0,1fr)] gap-6 items-start">
                    <DonutChart
                      data={Object.entries(dismissals.by_kind).map(([label, value]) => ({ label, value }))}
                      categoryAccessor="label" valueAccessor="value"
                      title={`Dismissals (${dismissals.total_dismissals})`} width={350} height={350} />
                    <BarChart
                      data={dismissals.by_over.filter(o => o.dismissals > 0)}
                      categoryAccessor={(d: Record<string, any>) => String(d.over_number)}
                      valueAccessor="dismissals"
                      title="Dismissals by Over" categoryLabel="Over" valueLabel="Dismissals"
                      height={300} colorScheme={[WISDEN.oxblood]} />
                  </div>
                )}
              </>
            )}

            {activeTab === 'Inter-Wicket' && (
              <>
                <TabState fetch={interWicketFetch as FetchState<unknown>} />
                {!interWicketFetch.loading && !interWicketFetch.error && interWicket.length > 0 && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <LineChart
                      data={interWicket.map(iw => ({ x: iw.wickets_down, y: iw.strike_rate ?? 0 }))}
                      xAccessor="x" yAccessor="y"
                      title="Strike Rate by Wickets Down" xLabel="Wickets Down" yLabel="Strike Rate"
                      height={350} showPoints />
                    <BarChart
                      data={interWicket} categoryAccessor={(d: Record<string, any>) => String(d.wickets_down)}
                      valueAccessor="runs"
                      title="Total Runs by Wickets Down" categoryLabel="Wickets Down" valueLabel="Runs"
                      height={350} />
                  </div>
                )}
              </>
            )}

            {activeTab === 'Innings List' && (
              <>
                <TabState fetch={inningsFetch as FetchState<unknown>} />
                {!inningsFetch.loading && !inningsFetch.error && (
                  <DataTable columns={inningsColumns} data={innings}
                    pagination={{ total: inningsTotal, limit: 50, offset: inningsOffset, onPage: setInningsOffset }} />
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ============================================================
// Batting landing — top 10 by average + top 10 by strike rate,
// shown below the search bar when no batter is selected. Counts
// reflect the current FilterBar scope. Each row links to that
// batter's page with the same filters carried through.
// ============================================================

interface BattingLandingBoardProps {
  filters: FilterParams
  filterDeps: unknown[]
}

function BattingLandingBoard({ filters, filterDeps }: BattingLandingBoardProps) {
  // Default to last 3 seasons when no season filter is set. Writes to
  // URL so FilterBar reflects the scope. One-shot per mount — user can
  // clear via FilterBar reset buttons without re-triggering.
  useDefaultSeasonWindow(filters, true)

  const board = useFetch<BattingLeaders | null>(
    () => getBattingLeaders({ ...filters, limit: 10 }),
    filterDeps,
  )
  if (board.loading && !board.data) return <Spinner label="Loading leaders…" />
  if (board.error) {
    return <ErrorBanner message={`Could not load leaders: ${board.error}`} onRetry={board.refetch} />
  }
  const data = board.data
  if (!data) return null
  const bothEmpty = data.by_average.length === 0 && data.by_strike_rate.length === 0
  if (bothEmpty) {
    return <div className="wisden-empty">No batters meet the minimum-sample thresholds for the current filters.</div>
  }

  // Carry current filters through on player links so clicking into a
  // batter preserves the tournament/season scope the user is exploring.
  const carry: Record<string, string> = {}
  if (filters.gender) carry.gender = filters.gender
  if (filters.team_type) carry.team_type = filters.team_type
  if (filters.tournament) carry.tournament = filters.tournament
  if (filters.season_from) carry.season_from = filters.season_from
  if (filters.season_to) carry.season_to = filters.season_to
  const playerLink = (id: string) => {
    const qs = new URLSearchParams({ player: id, ...carry })
    return `/batting?${qs.toString()}`
  }

  const renderTable = (title: string, metric: 'average' | 'strike_rate', rows: BattingLeaderEntry[]) => (
    <div>
      <h3 className="wisden-section-title">{title}</h3>
      {rows.length === 0 ? (
        <div className="wisden-tab-help" style={{ fontStyle: 'italic' }}>
          No batters meet the threshold.
        </div>
      ) : (
        <table className="wisden-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Batter</th>
              <th style={{ textAlign: 'right' }}>{metric === 'average' ? 'Avg' : 'SR'}</th>
              <th style={{ textAlign: 'right' }}>Runs</th>
              <th style={{ textAlign: 'right' }}>Balls</th>
              {metric === 'average' && <th style={{ textAlign: 'right' }}>Outs</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.person_id}>
                <td>
                  <span style={{ color: 'var(--ink-faint)', marginRight: '0.5rem' }}>{i + 1}.</span>
                  <Link to={playerLink(r.person_id)} className="comp-link">{r.name}</Link>
                </td>
                <td className="num" style={{ textAlign: 'right', fontWeight: 600 }}>
                  {metric === 'average' ? r.average?.toFixed(2) : r.strike_rate?.toFixed(2)}
                </td>
                <td className="num" style={{ textAlign: 'right' }}>{r.runs}</td>
                <td className="num" style={{ textAlign: 'right' }}>{r.balls}</td>
                {metric === 'average' && (
                  <td className="num" style={{ textAlign: 'right' }}>{r.dismissals}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )

  return (
    <div>
      <div className="wisden-tab-help" style={{ marginBottom: '1.5rem' }}>
        Top 10 batters in the current filter scope. Change gender, type, tournament, or season
        to narrow the leaderboards. Thresholds: at least{' '}
        <span className="num">{data.thresholds.min_balls}</span> legal balls faced; averages
        additionally require at least <span className="num">{data.thresholds.min_dismissals}</span> dismissals
        so a single not-out innings doesn't top the list.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2.5rem', alignItems: 'start' }}>
        {renderTable('Top by average', 'average', data.by_average)}
        {renderTable('Top by strike rate', 'strike_rate', data.by_strike_rate)}
      </div>
    </div>
  )
}
