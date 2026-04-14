import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch, type FetchState } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import PlayerSearch from '../components/PlayerSearch'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import DonutChart from '../components/charts/DonutChart'
import { WISDEN_PHASES } from '../components/charts/palette'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import {
  getFielderSummary, getFielderBySeason, getFielderByPhase, getFielderByOver,
  getFielderDismissalTypes, getFielderVictims, getFielderInnings,
} from '../api'
import type {
  PlayerSearchResult, FieldingSummary, FieldingSeason, FieldingPhase,
  FieldingVictim, FieldingInnings,
} from '../types'

function TabState({ fetch }: { fetch: FetchState<unknown> }) {
  if (fetch.loading) return <Spinner label="Loading…" />
  if (fetch.error) return <ErrorBanner message={fetch.error} onRetry={fetch.refetch} />
  return null
}

const tabs = ['By Season', 'By Over', 'By Phase', 'Dismissal Types', 'Victims', 'Innings List'] as const
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
  ]

  const summaryFetch = useFetch<FieldingSummary | null>(
    () => playerId ? getFielderSummary(playerId, filters) : Promise.resolve(null),
    filterDeps,
  )
  const summary = summaryFetch.data
  useDocumentTitle(summary ? `${summary.name} — Fielding` : playerId ? null : 'Fielding')

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

      {!playerId && <div className="wisden-empty">Search for a fielder to view stats</div>}

      {playerId && summaryFetch.loading && <Spinner label="Loading fielder…" size="lg" />}

      {playerId && summaryFetch.error && (
        <ErrorBanner
          message={`Could not load fielder: ${summaryFetch.error}`}
          onRetry={summaryFetch.refetch}
        />
      )}

      {playerId && summary && !summaryFetch.loading && (
        <>
          <h2 className="wisden-page-title">{summary.name}</h2>
          <div className="wisden-statrow cols-6">
            <StatCard label="Catches" value={summary.catches} />
            <StatCard label="Stumpings" value={summary.stumpings} />
            <StatCard label="Run Outs" value={summary.run_outs} />
            <StatCard label="Total" value={summary.total_dismissals} />
            <StatCard label="Matches" value={summary.matches} />
            <StatCard label="Dis/Match" value={fmt(summary.dismissals_per_match)} />
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
          </div>
        </>
      )}
    </div>
  )
}
