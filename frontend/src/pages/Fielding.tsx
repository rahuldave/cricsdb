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
import DonutChart from '../components/charts/DonutChart'
import { WISDEN, WISDEN_PHASES } from '../components/charts/palette'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import {
  getFielderSummary, getFielderBySeason, getFielderByPhase, getFielderByOver,
  getFielderDismissalTypes, getFielderVictims, getFielderInnings,
  getFielderKeepingSummary, getFielderKeepingBySeason, getFielderKeepingInnings,
  getFieldingLeaders,
} from '../api'
import type {
  PlayerSearchResult, FieldingSummary, FieldingSeason, FieldingPhase,
  FieldingVictim, FieldingInnings,
  KeepingSummary, KeepingSeason, KeepingInnings,
  FieldingLeaders, FilterParams,
} from '../types'

function TabState({ fetch }: { fetch: FetchState<unknown> }) {
  if (fetch.loading) return <Spinner label="Loading…" />
  if (fetch.error) return <ErrorBanner message={fetch.error} onRetry={fetch.refetch} />
  return null
}

// Tabs are filtered at render based on innings_kept (Keeping hidden when 0)
const BASE_TABS = ['By Season', 'By Over', 'By Phase', 'Dismissal Types', 'Victims', 'Innings List'] as const
const KEEPING_TAB = 'Keeping' as const
const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

export default function Fielding() {
  const filters = useFilters()
  const [playerId] = useUrlParam('player')
  const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
  const setUrlParams = useSetUrlParams()

  const [inningsOffset, setInningsOffset] = useState(0)

  const handleSelect = (p: PlayerSearchResult) => {
    setUrlParams({ player: p.id, tab: 'By Season' })
  }

  const filterDeps = [
    playerId, filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_team, filters.filter_opponent,
    filters.filter_venue,
  ]

  const summaryFetch = useFetch<FieldingSummary | null>(
    () => playerId ? getFielderSummary(playerId, filters) : Promise.resolve(null),
    filterDeps,
  )
  const summary = summaryFetch.data
  useDocumentTitle(summary ? `${summary.name} — Fielding` : playerId ? null : 'Fielding')

  // Self-correcting deep link — see Batting.tsx for the rationale.
  useEffect(() => {
    if (!summary || filters.gender) return
    const g = summary.nationalities?.[0]?.gender
    const allSameGender = summary.nationalities?.every(n => n.gender === g)
    if (g && allSameGender) setUrlParams({ gender: g }, { replace: true })
  }, [summary, filters.gender])

  const seasonFetch = useFetch<{ by_season: FieldingSeason[] } | null>(
    () => playerId && activeTab === 'By Season'
      ? getFielderBySeason(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const seasonData = seasonFetch.data?.by_season ?? []

  const overFetch = useFetch<{ by_over: { over_number: number; dismissals: number }[] } | null>(
    () => playerId && activeTab === 'By Over'
      ? getFielderByOver(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const overData = overFetch.data?.by_over ?? []

  const phaseFetch = useFetch<{ by_phase: FieldingPhase[] } | null>(
    () => playerId && activeTab === 'By Phase'
      ? getFielderByPhase(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const phaseData = phaseFetch.data?.by_phase ?? []

  const dismissalTypesFetch = useFetch<{ total: number; by_kind: Record<string, number> } | null>(
    () => playerId && activeTab === 'Dismissal Types'
      ? getFielderDismissalTypes(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const dismissalTypes = dismissalTypesFetch.data

  const victimsFetch = useFetch<{ victims: FieldingVictim[] } | null>(
    () => playerId && activeTab === 'Victims'
      ? getFielderVictims(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const victims = victimsFetch.data?.victims ?? []

  const inningsFetch = useFetch<{ innings: FieldingInnings[]; total: number } | null>(
    () => playerId && activeTab === 'Innings List'
      ? getFielderInnings(playerId, { ...filters, limit: 50, offset: inningsOffset })
      : Promise.resolve(null),
    [...filterDeps, activeTab, inningsOffset],
  )
  const innings = inningsFetch.data?.innings ?? []
  const inningsTotal = inningsFetch.data?.total ?? 0

  // --- Keeping (Tier 2) ---
  const [keepOffset, setKeepOffset] = useState(0)
  const keepSummaryFetch = useFetch<KeepingSummary | null>(
    () => playerId && activeTab === 'Keeping'
      ? getFielderKeepingSummary(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const keepSummary = keepSummaryFetch.data

  const keepSeasonFetch = useFetch<{ by_season: KeepingSeason[] } | null>(
    () => playerId && activeTab === 'Keeping'
      ? getFielderKeepingBySeason(playerId, filters) : Promise.resolve(null),
    [...filterDeps, activeTab],
  )
  const keepSeasonData = keepSeasonFetch.data?.by_season ?? []

  const keepInningsFetch = useFetch<{ innings: KeepingInnings[]; total: number } | null>(
    () => playerId && activeTab === 'Keeping'
      ? getFielderKeepingInnings(playerId, { ...filters, limit: 50, offset: keepOffset })
      : Promise.resolve(null),
    [...filterDeps, activeTab, keepOffset],
  )
  const keepInnings = keepInningsFetch.data?.innings ?? []
  const keepInningsTotal = keepInningsFetch.data?.total ?? 0

  const KIND_LABELS: Record<string, string> = {
    caught: 'Catches',
    stumped: 'Stumpings',
    run_out: 'Run Outs',
    caught_and_bowled: 'Caught & Bowled',
  }

  const victimColumns: Column<FieldingVictim>[] = [
    { key: 'batter_name', label: 'Batter', sortable: true, format: (_v: any, r: any) => (
      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: '0.5em' }}>
        <span>{r.batter_name}</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--ink-faint)' }}>
          (<Link to={`/batting?player=${encodeURIComponent(r.batter_id)}`}
            className="comp-link" onClick={e => e.stopPropagation()}>stats</Link>
          {' · '}
          <Link to={`/head-to-head?batter=${encodeURIComponent(r.batter_id)}&bowler=`}
            className="comp-link" onClick={e => e.stopPropagation()}>h2h</Link>)
        </span>
      </span>
    ) as unknown as string },
    { key: 'catches', label: 'Catches', sortable: true },
    { key: 'stumpings', label: 'Stumpings', sortable: true },
    { key: 'run_outs', label: 'Run Outs', sortable: true },
    { key: 'total', label: 'Total', sortable: true },
  ]

  const keepingInningsColumns: Column<KeepingInnings>[] = [
    { key: 'date', label: 'Date', sortable: true, format: (v: any, r: any) => (
      <Link to={`/matches/${r.match_id}?highlight_fielder=${encodeURIComponent(playerId || '')}`}
        className="comp-link" onClick={e => e.stopPropagation()}>{v || '-'}</Link>
    ) as unknown as string },
    { key: 'opponent', label: 'Opponent', sortable: true },
    { key: 'tournament', label: 'Tournament' },
    { key: 'stumpings', label: 'St', sortable: true },
    { key: 'catches', label: 'Ct', sortable: true },
    { key: 'run_outs', label: 'RO', sortable: true },
    { key: 'byes', label: 'B' },
    { key: 'total_dismissals', label: 'Total', sortable: true },
    { key: 'confidence', label: 'Conf', format: (v: any) => (
      <span style={{
        fontSize: '0.7rem', fontStyle: 'italic',
        color: v === 'definitive' ? 'var(--ink)'
             : v === 'high' ? 'var(--accent)'
             : 'var(--ink-faint)',
      }}>{v}</span>
    ) as unknown as string },
  ]

  const inningsColumns: Column<FieldingInnings>[] = [
    { key: 'date', label: 'Date', sortable: true, format: (v: any, r: any) => (
      <Link to={`/matches/${r.match_id}?highlight_fielder=${encodeURIComponent(playerId || '')}`}
        className="comp-link" onClick={e => e.stopPropagation()}>{v || '-'}</Link>
    ) as unknown as string },
    { key: 'opponent', label: 'Opponent', sortable: true },
    { key: 'tournament', label: 'Tournament' },
    { key: 'catches', label: 'Catches' },
    { key: 'stumpings', label: 'Stumpings' },
    { key: 'run_outs', label: 'Run Outs' },
    { key: 'total', label: 'Total', sortable: true },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <PlayerSearch role="fielder" onSelect={handleSelect} placeholder="Search for a fielder…" />
      </div>

      {!playerId && <FieldingLandingBoard filters={filters} filterDeps={filterDeps} />}

      {playerId && summaryFetch.loading && <Spinner label="Loading fielder…" size="lg" />}

      {playerId && summaryFetch.error && (
        <ErrorBanner
          message={`Could not load fielder: ${summaryFetch.error}`}
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
          <div className="wisden-statrow cols-6">
            <StatCard label="Catches" value={summary.catches} />
            <StatCard label="Stumpings" value={summary.stumpings} />
            <StatCard label="Run Outs" value={summary.run_outs} />
            <StatCard label="Total" value={summary.total_dismissals} />
            <StatCard label="Matches" value={summary.matches} />
            <StatCard label="Dis/Match" value={fmt(summary.dismissals_per_match)} />
          </div>

          <div className="wisden-tabs">
            {(summary.innings_kept > 0
              ? [...BASE_TABS, KEEPING_TAB] as const
              : BASE_TABS
            ).map(tab => (
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
                    <BarChart data={seasonData} categoryAccessor="season" valueAccessor="total"
                      title="Dismissals by Season" categoryLabel="Season" valueLabel="Dismissals"
                      height={350} />
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
                    categoryAccessor="over" valueAccessor="dismissals"
                    title="Dismissals by Over" categoryLabel="Over" valueLabel="Dismissals"
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
                          <div><span className="lbl">Catches</span></div><div className="num">{p.catches}</div>
                          <div><span className="lbl">Stumpings</span></div><div className="num">{p.stumpings}</div>
                          <div><span className="lbl">Run Outs</span></div><div className="num">{p.run_outs}</div>
                          <div><span className="lbl">C&B</span></div><div className="num">{p.caught_and_bowled}</div>
                          <div><span className="lbl">Total</span></div><div className="num">{p.total}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {activeTab === 'Dismissal Types' && (
              <>
                <TabState fetch={dismissalTypesFetch as FetchState<unknown>} />
                {!dismissalTypesFetch.loading && !dismissalTypesFetch.error && dismissalTypes && (
                  <DonutChart
                    data={Object.entries(dismissalTypes.by_kind).map(([label, value]) => ({
                      label: KIND_LABELS[label] || label, value,
                    }))}
                    categoryAccessor="label" valueAccessor="value"
                    title={`Dismissal Types (${dismissalTypes.total})`} width={350} height={350} />
                )}
              </>
            )}

            {activeTab === 'Victims' && (
              <>
                <TabState fetch={victimsFetch as FetchState<unknown>} />
                {!victimsFetch.loading && !victimsFetch.error && victims.length > 0 && (
                  <DataTable
                    columns={victimColumns}
                    data={victims}
                    rowKey={(r: Record<string, any>) => r.batter_id}
                  />
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

            {activeTab === 'Keeping' && (
              <>
                <TabState fetch={keepSummaryFetch as FetchState<unknown>} />
                {!keepSummaryFetch.loading && !keepSummaryFetch.error && keepSummary && (
                  <>
                    <div className="wisden-statrow cols-4">
                      <StatCard label="Stumpings" value={keepSummary.stumpings} />
                      <StatCard label="Keep Catches" value={keepSummary.keeping_catches} />
                      <StatCard label="Byes Conceded" value={keepSummary.byes_conceded}
                        subtitle={keepSummary.byes_per_innings != null ? `${fmt(keepSummary.byes_per_innings)}/inn` : undefined} />
                      <StatCard label="Innings Kept" value={keepSummary.innings_kept} />
                    </div>

                    {/* Confidence breakdown — transparency about how we identified the keeper */}
                    <p className="wisden-tab-help">
                      Of {keepSummary.innings_kept} keeping innings:{' '}
                      <span style={{ color: 'var(--ink)' }}>{keepSummary.innings_kept_by_confidence.definitive} definitive</span>
                      {' · '}
                      {keepSummary.innings_kept_by_confidence.high} high
                      {' · '}
                      {keepSummary.innings_kept_by_confidence.medium} medium
                      {' · '}
                      {keepSummary.innings_kept_by_confidence.low} low confidence
                      {keepSummary.ambiguous_innings > 0 && (
                        <>. {keepSummary.ambiguous_innings} additional innings ambiguous.</>
                      )}
                      {' '}
                      <span style={{ opacity: 0.7 }}>
                        Cricsheet has no keeper designation — identification via stumpings + XI inference.
                      </span>
                    </p>

                    <TabState fetch={keepSeasonFetch as FetchState<unknown>} />
                    {!keepSeasonFetch.loading && !keepSeasonFetch.error && keepSeasonData.length > 0 && (
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <BarChart data={keepSeasonData} categoryAccessor="season" valueAccessor="total_dismissals"
                          title="Dismissals by Season (as keeper)" categoryLabel="Season" valueLabel="Dismissals"
                          height={350} />
                        <BarChart data={keepSeasonData} categoryAccessor="season" valueAccessor="byes_conceded"
                          title="Byes Conceded by Season" categoryLabel="Season" valueLabel="Byes"
                          height={350} colorScheme={[WISDEN.oxblood]} />
                      </div>
                    )}

                    <TabState fetch={keepInningsFetch as FetchState<unknown>} />
                    {!keepInningsFetch.loading && !keepInningsFetch.error && (
                      <div className="mt-6">
                        <DataTable
                          columns={keepingInningsColumns}
                          data={keepInnings}
                          pagination={{ total: keepInningsTotal, limit: 50, offset: keepOffset, onPage: setKeepOffset }}
                        />
                      </div>
                    )}
                  </>
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
// Fielding landing — top 10 fielders by total dismissals + top 10
// keepers (by catches + stumpings as the designated keeper). Volume-
// based, no thresholds. Shown below the search bar when no fielder
// is selected.
// ============================================================

interface FieldingLandingBoardProps {
  filters: FilterParams
  filterDeps: unknown[]
}

function FieldingLandingBoard({ filters, filterDeps }: FieldingLandingBoardProps) {
  useDefaultSeasonWindow(filters, true)

  const board = useFetch<FieldingLeaders | null>(
    () => getFieldingLeaders({ ...filters, limit: 10 }),
    filterDeps,
  )
  if (board.loading && !board.data) return <Spinner label="Loading leaders…" />
  if (board.error) {
    return <ErrorBanner message={`Could not load leaders: ${board.error}`} onRetry={board.refetch} />
  }
  const data = board.data
  if (!data) return null
  const bothEmpty = data.by_dismissals.length === 0 && data.by_keeper_dismissals.length === 0
  if (bothEmpty) {
    return <div className="wisden-empty">No fielding activity for the current filters.</div>
  }

  const carry: Record<string, string> = {}
  if (filters.gender) carry.gender = filters.gender
  if (filters.team_type) carry.team_type = filters.team_type
  if (filters.tournament) carry.tournament = filters.tournament
  if (filters.season_from) carry.season_from = filters.season_from
  if (filters.season_to) carry.season_to = filters.season_to
  if (filters.filter_venue) carry.filter_venue = filters.filter_venue
  const fielderLink = (id: string) => {
    const qs = new URLSearchParams({ player: id, ...carry })
    return `/fielding?${qs.toString()}`
  }
  const keeperLink = (id: string) => {
    const qs = new URLSearchParams({ player: id, tab: 'Keeping', ...carry })
    return `/fielding?${qs.toString()}`
  }

  const fielderTable = (
    <div>
      <h3 className="wisden-section-title">Top by dismissals</h3>
      {data.by_dismissals.length === 0 ? (
        <div className="wisden-tab-help" style={{ fontStyle: 'italic' }}>No fielders.</div>
      ) : (
        <table className="wisden-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Fielder</th>
              <th style={{ textAlign: 'right' }}>Total</th>
              <th style={{ textAlign: 'right' }}>Ct</th>
              <th style={{ textAlign: 'right' }}>St</th>
              <th style={{ textAlign: 'right' }}>RO</th>
            </tr>
          </thead>
          <tbody>
            {data.by_dismissals.map((r, i) => (
              <tr key={r.person_id}>
                <td>
                  <span style={{ color: 'var(--ink-faint)', marginRight: '0.5rem' }}>{i + 1}.</span>
                  <Link to={fielderLink(r.person_id)} className="comp-link">{r.name}</Link>
                </td>
                <td className="num" style={{ textAlign: 'right', fontWeight: 600 }}>{r.total}</td>
                <td className="num" style={{ textAlign: 'right' }}>{r.catches + (r.c_and_b ?? 0)}</td>
                <td className="num" style={{ textAlign: 'right' }}>{r.stumpings}</td>
                <td className="num" style={{ textAlign: 'right' }}>{r.run_outs ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )

  const keeperTable = (
    <div>
      <h3 className="wisden-section-title">Top keepers</h3>
      {data.by_keeper_dismissals.length === 0 ? (
        <div className="wisden-tab-help" style={{ fontStyle: 'italic' }}>
          No designated-keeper dismissals in scope.
        </div>
      ) : (
        <table className="wisden-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Keeper</th>
              <th style={{ textAlign: 'right' }}>Total</th>
              <th style={{ textAlign: 'right' }}>Ct</th>
              <th style={{ textAlign: 'right' }}>St</th>
            </tr>
          </thead>
          <tbody>
            {data.by_keeper_dismissals.map((r, i) => (
              <tr key={r.person_id}>
                <td>
                  <span style={{ color: 'var(--ink-faint)', marginRight: '0.5rem' }}>{i + 1}.</span>
                  <Link to={keeperLink(r.person_id)} className="comp-link">{r.name}</Link>
                </td>
                <td className="num" style={{ textAlign: 'right', fontWeight: 600 }}>{r.total}</td>
                <td className="num" style={{ textAlign: 'right' }}>{r.catches}</td>
                <td className="num" style={{ textAlign: 'right' }}>{r.stumpings}</td>
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
        Top 10 fielders in the current filter scope. Fielding is ranked by volume, not rate —
        catches-per-match is mostly a position / opportunity stat, not a skill stat, so the raw
        count is the honest measure. <b>Ct</b> = catches (includes caught-and-bowled),
        {' '}<b>St</b> = stumpings, <b>RO</b> = run-outs. The keeper column filters to catches
        and stumpings taken while the player was the designated wicketkeeper
        (via our Tier-2 keeper inference).
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2.5rem', alignItems: 'start' }}>
        {fielderTable}
        {keeperTable}
      </div>
    </div>
  )
}
