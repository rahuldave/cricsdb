import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch, type FetchState } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { useDefaultSeasonWindow } from '../hooks/useDefaultSeasonWindow'
import PlayerSearch from '../components/PlayerSearch'
import FlagBadge from '../components/FlagBadge'
import ScopeIndicator from '../components/ScopeIndicator'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import ScatterChart from '../components/charts/ScatterChart'
import DonutChart from '../components/charts/DonutChart'
import { WISDEN, WISDEN_PHASES } from '../components/charts/palette'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import {
  getBowlerSummary, getBowlerInnings, getBowlerVsBatters, getBowlerByOver,
  getBowlerByPhase, getBowlerBySeason, getBowlerWickets,
  getBowlingLeaders,
} from '../api'
import type {
  PlayerSearchResult, BowlingSummary, BowlingInnings, BatterMatchup,
  OverStats, PhaseStats, WicketAnalysis,
  BowlingLeaders, BowlingLeaderEntry, FilterParams,
} from '../types'

function TabState({ fetch }: { fetch: FetchState<unknown> }) {
  if (fetch.loading) return <Spinner label="Loading…" />
  if (fetch.error) return <ErrorBanner message={fetch.error} onRetry={fetch.refetch} />
  return null
}

const tabs = ['By Season', 'By Over', 'By Phase', 'vs Batters', 'Wickets', 'Innings List'] as const
const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

export default function Bowling() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const setUrlParams = useSetUrlParams()

  const [inningsOffset, setInningsOffset] = useState(0)
  const [selectedBatterId, setSelectedBatterId] = useState<string | null>(null)

  const handleSelect = (p: PlayerSearchResult) => {
    setUrlParams({ player: p.id, tab: 'By Season' })
  }

  const filterDeps = [
    playerId, filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_team, filters.filter_opponent,
  ]

  const summaryFetch = useFetch<BowlingSummary | null>(
    () => playerId ? getBowlerSummary(playerId, filters) : Promise.resolve(null),
    filterDeps,
  )
  const summary = summaryFetch.data
  useDocumentTitle(summary ? `${summary.name} — Bowling` : playerId ? null : 'Bowling')

  // Self-correcting deep link — see Batting.tsx for the rationale.
  useEffect(() => {
    if (!summary || filters.gender) return
    const g = summary.nationalities?.[0]?.gender
    const allSameGender = summary.nationalities?.every(n => n.gender === g)
    if (g && allSameGender) setUrlParams({ gender: g })
  }, [summary, filters.gender])

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seasonFetch = useFetch<{ by_season: any[] } | null>(
    () => playerId && activeTab === 'By Season'
      ? getBowlerBySeason(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const seasonData = seasonFetch.data?.by_season ?? []

  const overFetch = useFetch<{ by_over: OverStats[] } | null>(
    () => playerId && activeTab === 'By Over'
      ? getBowlerByOver(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const overData = overFetch.data?.by_over ?? []

  const phaseFetch = useFetch<{ by_phase: PhaseStats[] } | null>(
    () => playerId && activeTab === 'By Phase'
      ? getBowlerByPhase(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const phaseData = phaseFetch.data?.by_phase ?? []

  const matchupsFetch = useFetch<{ matchups: BatterMatchup[] } | null>(
    () => playerId && activeTab === 'vs Batters'
      ? getBowlerVsBatters(playerId, { ...filters, min_balls: 6 })
      : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const batterMatchups = matchupsFetch.data?.matchups ?? []

  const wicketsFetch = useFetch<WicketAnalysis | null>(
    () => playerId && activeTab === 'Wickets'
      ? getBowlerWickets(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const wicketData = wicketsFetch.data

  const inningsFetch = useFetch<{ innings: BowlingInnings[]; total: number } | null>(
    () => playerId && activeTab === 'Innings List'
      ? getBowlerInnings(playerId, { ...filters, limit: 50, offset: inningsOffset })
      : Promise.resolve(null),
    [...filterDeps, activeTab, inningsOffset],
  )
  const innings = inningsFetch.data?.innings ?? []
  const inningsTotal = inningsFetch.data?.total ?? 0

  const inningsColumns: Column<BowlingInnings>[] = [
    { key: 'date', label: 'Date', sortable: true, format: (v: any, r: any) => (
      <Link to={`/matches/${r.match_id}?highlight_bowler=${encodeURIComponent(playerId || '')}`}
        className="comp-link" onClick={e => e.stopPropagation()}>{v || '-'}</Link>
    ) as unknown as string },
    { key: 'opponent', label: 'Opponent', sortable: true },
    { key: 'tournament', label: 'Tournament' },
    { key: 'overs', label: 'Overs' },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'wickets', label: 'Wkts', sortable: true },
    { key: 'economy', label: 'Econ', sortable: true, format: (v: any) => fmt(v) },
    { key: 'dots', label: 'Dots' },
  ]

  const batterColumns: Column<BatterMatchup>[] = [
    { key: 'batter_name', label: 'Batter', sortable: true, format: (_v: any, r: any) => (
      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: '0.5em' }}>
        <span>{r.batter_name}</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--ink-faint)' }}>
          (<Link to={`/batting?player=${encodeURIComponent(r.batter_id)}`}
            className="comp-link" onClick={e => e.stopPropagation()}>stats</Link>
          {' · '}
          <Link to={`/head-to-head?batter=${encodeURIComponent(r.batter_id)}&bowler=${encodeURIComponent(playerId || '')}`}
            className="comp-link" onClick={e => e.stopPropagation()}>h2h</Link>)
        </span>
      </span>
    ) as unknown as string },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'runs_conceded', label: 'Runs', sortable: true },
    { key: 'wickets', label: 'Wkts', sortable: true },
    { key: 'economy', label: 'Econ', sortable: true, format: (v: any) => fmt(v) },
    { key: 'average', label: 'Avg', sortable: true, format: (v: any) => fmt(v) },
    { key: 'balls_per_boundary', label: 'B/Bnd', sortable: true, format: (v: any) => fmt(v) },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <PlayerSearch role="bowler" onSelect={handleSelect} placeholder="Search for a bowler…" />
      </div>

      {!playerId && <BowlingLandingBoard filters={filters} filterDeps={filterDeps} />}

      {playerId && summaryFetch.loading && <Spinner label="Loading bowler…" size="lg" />}

      {playerId && summaryFetch.error && (
        <ErrorBanner
          message={`Could not load bowler: ${summaryFetch.error}`}
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
          <ScopeIndicator filters={filters} />
          <div className="wisden-statrow cols-5">
            <StatCard label="Matches" value={summary.matches} />
            <StatCard label="Innings" value={summary.innings} />
            <StatCard label="Wickets" value={summary.wickets} />
            <StatCard label="Average" value={fmt(summary.average)} />
            <StatCard label="Economy" value={fmt(summary.economy)} />
          </div>
          <div className="wisden-statrow cols-5">
            <StatCard label="Overs" value={summary.overs} />
            <StatCard label="Strike Rate" value={fmt(summary.strike_rate)} />
            <StatCard label="Best Figures" value={summary.best_figures || '-'} />
            <StatCard label="Dot %" value={summary.dot_pct != null ? `${summary.dot_pct}%` : '-'} />
            <StatCard label="B/Boundary" value={fmt(summary.balls_per_boundary)} />
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
                      <BarChart data={seasonData} categoryAccessor="season" valueAccessor={(d: Record<string, any>) => (d.wickets as number) ?? (d.dismissals as number) ?? 0}
                        title="Wickets by Season" categoryLabel="Season" valueLabel="Wickets"
                        height={350} colorScheme={[WISDEN.oxblood]} />
                      <BarChart data={seasonData.filter(s => s.strike_rate != null)}
                        categoryAccessor="season" valueAccessor={(d: Record<string, any>) => d.strike_rate ?? 0}
                        title="Bowling Strike Rate by Season" categoryLabel="Season" valueLabel="SR"
                        height={350} />
                    </div>
                    {seasonData.some((s: Record<string, any>) => String(s.season).includes('/')) && (
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
                    categoryAccessor="over"
                    valueAccessor={(d: Record<string, any>) => (d.economy as number) ?? 0}
                    title="Economy by Over" categoryLabel="Over" valueLabel="Economy"
                    colorBy="phase" colorScheme={WISDEN_PHASES}
                    height={350} />
                )}
              </>
            )}

            {activeTab === 'By Phase' && (
              <>
                <TabState fetch={phaseFetch as FetchState<unknown>} />
                {!phaseFetch.loading && !phaseFetch.error && phaseData.length > 0 && (() => {
                  const pp = phaseData.find((p: any) => p.phase === 'powerplay')
                  const ppEarly = phaseData.find((p: any) => p.phase === 'pp_early')
                  const ppLate = phaseData.find((p: any) => p.phase === 'pp_late')
                  const middle = phaseData.find((p: any) => p.phase === 'middle')
                  const death = phaseData.find((p: any) => p.phase === 'death')

                  const PhaseBlock = ({ p, label, hideSubtitle, small }: { p: any; label?: string; hideSubtitle?: boolean; small?: boolean }) => (
                    <div className="wisden-phaseblock" style={small ? { padding: '0.6rem 0.4rem' } : undefined}>
                      <h3 style={small ? { fontSize: '0.95rem' } : undefined}>{label || p.phase}</h3>
                      {!hideSubtitle && <div className="wisden-phaseblock-overs">Overs {p.overs_range || p.overs}</div>}
                      <div className="wisden-phaseblock-grid">
                        <div><span className="lbl">Balls</span></div><div className="num">{p.balls}</div>
                        <div><span className="lbl">Runs</span></div><div className="num">{p.runs_conceded ?? p.runs}</div>
                        <div><span className="lbl">Wkts</span></div><div className="num">{p.wickets ?? 0}</div>
                        <div><span className="lbl">Econ</span></div><div className="num">{fmt(p.economy)}</div>
                        <div><span className="lbl">SR</span></div><div className="num">{fmt(p.strike_rate)}</div>
                        <div><span className="lbl">Dots</span></div><div className="num">{fmt(p.dot_pct)}%</div>
                      </div>
                    </div>
                  )

                  return (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-0 wisden-phase-first">
                      {/* Powerplay column: main block + nested sub-phase splits */}
                      <div>
                        {pp && <PhaseBlock p={pp} label="Powerplay" />}
                        {(ppEarly || ppLate) && (
                          <div className="grid grid-cols-2 gap-0" style={{ borderTop: '1px solid var(--rule-soft)' }}>
                            {ppEarly && <PhaseBlock p={ppEarly} label="1–3" hideSubtitle small />}
                            {ppLate && <PhaseBlock p={ppLate} label="4–6" hideSubtitle small />}
                          </div>
                        )}
                      </div>
                      {middle && <PhaseBlock p={middle} label="Middle" />}
                      {death && <PhaseBlock p={death} label="Death" />}
                    </div>
                  )
                })()}
              </>
            )}

            {activeTab === 'vs Batters' && (
              <>
                <TabState fetch={matchupsFetch as FetchState<unknown>} />
                {!matchupsFetch.loading && !matchupsFetch.error && batterMatchups.length > 0 && (() => {
                  // Switched Y axis from strike_rate (balls/wicket) to average
                  // (runs/wicket) — average is the more familiar bowling stat
                  // and "balls per wicket" was confusingly framed.
                  //
                  // Also FLIPPED the Y axis via frameProps.yExtent so low
                  // values appear at the TOP of the chart. With the flip,
                  // both axes have "good for bowler" toward the top-left:
                  //   left  = low economy = cheap
                  //   top   = low average = wickets cost few runs
                  // The visually prominent top-left corner is now the
                  // "dominant bowler" zone, fixing the previous problem
                  // where high values (bad for bowler) were on top.
                  const valid = batterMatchups.filter(m => m.economy != null && m.average != null)
                  const maxAvg = Math.max(...valid.map(m => m.average ?? 0), 30)
                  const topByBalls = [...valid].sort((a, b) => (b.balls ?? 0) - (a.balls ?? 0)).slice(0, 8)
                  const annotations: Record<string, any>[] = topByBalls.map(m => ({
                    type: 'widget',
                    economy: m.economy,
                    average: m.average,
                    dy: -12,
                    content: (
                      <span style={{
                        fontSize: 11, fontFamily: 'var(--serif)', fontStyle: 'italic',
                        color: 'var(--ink)',
                        background: 'rgba(250,247,240,0.7)', padding: '0 3px',
                        whiteSpace: 'nowrap',
                        textShadow: '0 0 2px rgba(250,247,240,0.95)',
                      }}>{m.batter_name}</span>
                    ),
                  }))
                  const selected = selectedBatterId
                    ? valid.find(m => m.batter_id === selectedBatterId)
                    : null
                  if (selected) {
                    annotations.push({
                      type: 'highlight',
                      field: 'batter_id',
                      value: selectedBatterId,
                      color: 'var(--accent)',
                      r: 14,
                    })
                    annotations.push({
                      type: 'label',
                      economy: selected.economy,
                      average: selected.average,
                      label: selected.batter_name,
                      dx: 24, dy: -28,
                      color: 'var(--accent)',
                    })
                  }
                  return (
                    <div>
                      <p className="wisden-tab-help">
                        Hover any dot to see the batter. Top 8 by balls bowled are labelled.
                        Click a row in the table to find that batter on the chart.
                        <span style={{ opacity: 0.7 }}> Top-left corner = bowler dominated (low econ + low avg).</span>
                      </p>
                      <ScatterChart
                        data={valid}
                        xAccessor="economy"
                        yAccessor="average"
                        sizeBy="balls"
                        title="Economy vs Average (dot size = balls bowled)"
                        xLabel="Economy" yLabel="Average (runs / wicket)" height={400}
                        tooltip={{
                          title: 'batter_name',
                          fields: ['balls', 'runs_conceded', 'wickets', 'economy', 'average'],
                        }}
                        annotations={annotations}
                        pointIdAccessor="batter_id"
                        // Reverse Y so low average (good for bowler) sits at the top.
                        frameProps={{ yExtent: [maxAvg * 1.05, 0] }}
                      />
                      <div className="mt-4">
                        <DataTable
                          columns={batterColumns}
                          data={batterMatchups}
                          rowKey={(r: Record<string, any>) => r.batter_id}
                          highlightKey={selectedBatterId}
                          onRowClick={(r: Record<string, any>) => setSelectedBatterId(r.batter_id)}
                        />
                      </div>
                    </div>
                  )
                })()}
              </>
            )}

            {activeTab === 'Wickets' && (
              <>
                <TabState fetch={wicketsFetch as FetchState<unknown>} />
                {!wicketsFetch.loading && !wicketsFetch.error && wicketData && (
                  <div className="grid grid-cols-1 lg:grid-cols-[350px_minmax(0,1fr)] gap-6 items-start">
                    <DonutChart
                      data={Object.entries(wicketData.by_kind).map(([label, value]) => ({ label, value }))}
                      categoryAccessor="label" valueAccessor="value"
                      title={`Wicket Types (${wicketData.total_wickets})`} width={350} height={350} />
                    <BarChart
                      data={Object.entries(wicketData.by_phase).map(([phase, wkts]) => ({ phase, wickets: wkts }))}
                      categoryAccessor="phase" valueAccessor="wickets"
                      title="Wickets by Phase" categoryLabel="Phase" valueLabel="Wickets"
                      height={300} colorScheme={[WISDEN.oxblood]} />
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
// Bowling landing — top 10 by strike rate + top 10 by economy,
// shown below the search bar when no bowler is selected.
// ============================================================

interface BowlingLandingBoardProps {
  filters: FilterParams
  filterDeps: unknown[]
}

function BowlingLandingBoard({ filters, filterDeps }: BowlingLandingBoardProps) {
  useDefaultSeasonWindow(filters, true)

  const board = useFetch<BowlingLeaders | null>(
    () => getBowlingLeaders({ ...filters, limit: 10 }),
    filterDeps,
  )
  if (board.loading && !board.data) return <Spinner label="Loading leaders…" />
  if (board.error) {
    return <ErrorBanner message={`Could not load leaders: ${board.error}`} onRetry={board.refetch} />
  }
  const data = board.data
  if (!data) return null
  const bothEmpty = data.by_strike_rate.length === 0 && data.by_economy.length === 0
  if (bothEmpty) {
    return <div className="wisden-empty">No bowlers meet the minimum-sample thresholds for the current filters.</div>
  }

  const carry: Record<string, string> = {}
  if (filters.gender) carry.gender = filters.gender
  if (filters.team_type) carry.team_type = filters.team_type
  if (filters.tournament) carry.tournament = filters.tournament
  if (filters.season_from) carry.season_from = filters.season_from
  if (filters.season_to) carry.season_to = filters.season_to
  const playerLink = (id: string) => {
    const qs = new URLSearchParams({ player: id, ...carry })
    return `/bowling?${qs.toString()}`
  }

  const renderTable = (title: string, metric: 'strike_rate' | 'economy', rows: BowlingLeaderEntry[]) => (
    <div>
      <h3 className="wisden-section-title">{title}</h3>
      {rows.length === 0 ? (
        <div className="wisden-tab-help" style={{ fontStyle: 'italic' }}>
          No bowlers meet the threshold.
        </div>
      ) : (
        <table className="wisden-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Bowler</th>
              <th style={{ textAlign: 'right' }}>{metric === 'strike_rate' ? 'SR' : 'Econ'}</th>
              <th style={{ textAlign: 'right' }}>Wkts</th>
              <th style={{ textAlign: 'right' }}>Balls</th>
              <th style={{ textAlign: 'right' }}>Runs</th>
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
                  {metric === 'strike_rate' ? r.strike_rate?.toFixed(2) : r.economy?.toFixed(2)}
                </td>
                <td className="num" style={{ textAlign: 'right' }}>{r.wickets}</td>
                <td className="num" style={{ textAlign: 'right' }}>{r.balls}</td>
                <td className="num" style={{ textAlign: 'right' }}>{r.runs_conceded}</td>
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
        Top 10 bowlers in the current filter scope. Lower is better for both metrics:
        strike rate counts balls per wicket; economy is runs conceded per over.
        Thresholds: at least <span className="num">{data.thresholds.min_balls}</span> legal balls;
        strike-rate list additionally requires{' '}
        <span className="num">{data.thresholds.min_wickets}</span> wickets.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2.5rem', alignItems: 'start' }}>
        {renderTable('Top by strike rate', 'strike_rate', data.by_strike_rate)}
        {renderTable('Top by economy', 'economy', data.by_economy)}
      </div>
    </div>
  )
}
