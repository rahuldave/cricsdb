import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../../hooks/useFilters'
import { useUrlParam } from '../../hooks/useUrlState'
import { useFetch } from '../../hooks/useFetch'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import {
  getVenueSummary, getBattingLeaders, getBowlingLeaders, getFieldingLeaders,
  getMatches, getTournamentRecords,
} from '../../api'
import type {
  VenueSummary, BattingLeaders, BattingLeaderEntry,
  BowlingLeaders, BowlingLeaderEntry,
  FieldingLeaders, FieldingLeaderEntry,
  MatchListItem, TournamentRecords,
  TournamentRecordTeamTotal, TournamentRecordWin,
  TournamentRecordPartnership, TournamentRecordBowling, TournamentRecordMatchSixes,
} from '../../types'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import DataTable from '../DataTable'
import PlayerLink from '../PlayerLink'
import VenueOverviewPanel from './VenueOverviewPanel'

const TABS = ['Overview', 'Batters', 'Bowlers', 'Fielders', 'Matches', 'Records'] as const
type TabName = typeof TABS[number]

const fmt = (v: number | null | undefined, d = 2) =>
  v == null ? '-' : v.toFixed(d)

const matchLink = (matchId: number, label: string | number) => (
  <Link to={`/matches/${matchId}`} className="comp-link">{label}</Link>
)

const teamLink = (team: string) => (
  <Link to={`/teams?team=${encodeURIComponent(team)}`} className="comp-link">{team}</Link>
)

export default function VenueDossier({ venue }: { venue: string }) {
  const filters = useFilters()
  const [activeTab, setActiveTab] = useUrlParam('tab', 'Overview')
  const currentTab = (TABS as readonly string[]).includes(activeTab)
    ? (activeTab as TabName)
    : 'Overview'

  useDocumentTitle(venue)

  const filterDeps = [
    venue,
    filters.gender, filters.team_type, filters.tournament,
    filters.season_from, filters.season_to,
    filters.filter_team, filters.filter_opponent,
  ]

  const scopedFilters = { ...filters, filter_venue: venue }

  const summaryFetch = useFetch<VenueSummary>(
    () => getVenueSummary(venue, filters),
    filterDeps,
  )

  const battersFetch = useFetch<BattingLeaders | null>(
    () => currentTab === 'Batters'
      ? getBattingLeaders({ ...scopedFilters, limit: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Batters'],
  )
  const bowlersFetch = useFetch<BowlingLeaders | null>(
    () => currentTab === 'Bowlers'
      ? getBowlingLeaders({ ...scopedFilters, limit: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Bowlers'],
  )
  const fieldersFetch = useFetch<FieldingLeaders | null>(
    () => currentTab === 'Fielders'
      ? getFieldingLeaders({ ...scopedFilters, limit: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Fielders'],
  )
  const MATCHES_PAGE_SIZE = 50
  const [matchesOffset, setMatchesOffset] = useState(0)
  useEffect(() => { setMatchesOffset(0) }, filterDeps)

  const matchesFetch = useFetch<{ matches: MatchListItem[]; total: number } | null>(
    () => currentTab === 'Matches'
      ? getMatches({ ...scopedFilters, limit: MATCHES_PAGE_SIZE, offset: matchesOffset })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Matches', matchesOffset],
  )
  // Tournament records endpoint works with a null tournament when other
  // filters (filter_venue here) are set — confirmed during planning.
  const recordsFetch = useFetch<TournamentRecords | null>(
    () => currentTab === 'Records'
      ? getTournamentRecords(null, { ...scopedFilters, limit: 5 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Records'],
  )

  if (summaryFetch.loading && !summaryFetch.data) {
    return <Spinner label={`Loading ${venue}…`} size="lg" />
  }
  if (summaryFetch.error || !summaryFetch.data) {
    return (
      <ErrorBanner
        message={`Could not load venue: ${summaryFetch.error || 'no data'}`}
        onRetry={summaryFetch.refetch}
      />
    )
  }
  const summary = summaryFetch.data

  return (
    <div>
      {/* Breadcrumb + back link */}
      <div className="wisden-breadcrumb mb-2">
        <Link to="/venues" className="comp-link">← All venues</Link>
      </div>
      <h2 className="wisden-page-title">
        {summary.venue}
        {summary.city && summary.city !== summary.venue && (
          <span className="wisden-tile-faint">{' · '}{summary.city}</span>
        )}
      </h2>
      <div className="wisden-page-subtitle">
        {summary.country && <>{summary.country}{' · '}</>}
        {summary.matches.toLocaleString()} matches in scope
        {' · '}
        <Link
          to={`/matches?filter_venue=${encodeURIComponent(venue)}`}
          className="comp-link"
        >view all matches →</Link>
      </div>

      <div className="wisden-tabs mt-4">
        {TABS.map(tab => (
          <button
            key={tab}
            type="button"
            className={`wisden-tab${currentTab === tab ? ' is-active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {currentTab === 'Overview' && <VenueOverviewPanel summary={summary} />}
      {currentTab === 'Batters' && (
        <BattersTab
          loading={battersFetch.loading}
          error={battersFetch.error}
          data={battersFetch.data}
          refetch={battersFetch.refetch}
          gender={filters.gender}
          venue={venue}
        />
      )}
      {currentTab === 'Bowlers' && (
        <BowlersTab
          loading={bowlersFetch.loading}
          error={bowlersFetch.error}
          data={bowlersFetch.data}
          refetch={bowlersFetch.refetch}
          gender={filters.gender}
          venue={venue}
        />
      )}
      {currentTab === 'Fielders' && (
        <FieldersTab
          loading={fieldersFetch.loading}
          error={fieldersFetch.error}
          data={fieldersFetch.data}
          refetch={fieldersFetch.refetch}
          gender={filters.gender}
          venue={venue}
        />
      )}
      {currentTab === 'Matches' && (
        <MatchesTab
          loading={matchesFetch.loading}
          error={matchesFetch.error}
          matches={matchesFetch.data?.matches ?? []}
          total={matchesFetch.data?.total ?? 0}
          refetch={matchesFetch.refetch}
          pageSize={MATCHES_PAGE_SIZE}
          offset={matchesOffset}
          onOffsetChange={setMatchesOffset}
        />
      )}
      {currentTab === 'Records' && (
        <RecordsTab
          loading={recordsFetch.loading}
          error={recordsFetch.error}
          data={recordsFetch.data}
          refetch={recordsFetch.refetch}
        />
      )}
    </div>
  )
}

// ─── Tabs ─────────────────────────────────────────────────────────────

function BattersTab({
  loading, error, data, refetch, gender,
}: {
  loading: boolean; error: string | null
  data: BattingLeaders | null; refetch: () => void
  gender: string | null | undefined
  venue: string
}) {
  if (loading) return <Spinner label="Loading batters…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By average</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Batter',
              format: (_v, r: BattingLeaderEntry) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="batter" gender={gender}
                />
              ) as unknown as string,
            },
            { key: 'runs', label: 'Runs', sortable: true },
            { key: 'balls', label: 'Balls' },
            { key: 'average', label: 'Avg', sortable: true, format: (v) => fmt(v, 2) },
            { key: 'strike_rate', label: 'SR', format: (v) => fmt(v, 2) },
          ]}
          data={data.by_average}
          rowKey={(r) => r.person_id}
        />
      </div>
      <div>
        <h3 className="wisden-section-title">By strike rate</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Batter',
              format: (_v, r: BattingLeaderEntry) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="batter" gender={gender}
                />
              ) as unknown as string,
            },
            { key: 'strike_rate', label: 'SR', sortable: true, format: (v) => fmt(v, 2) },
            { key: 'runs', label: 'Runs' },
            { key: 'balls', label: 'Balls' },
          ]}
          data={data.by_strike_rate}
          rowKey={(r) => r.person_id}
        />
      </div>
    </div>
  )
}

function BowlersTab({
  loading, error, data, refetch, gender,
}: {
  loading: boolean; error: string | null
  data: BowlingLeaders | null; refetch: () => void
  gender: string | null | undefined
  venue: string
}) {
  if (loading) return <Spinner label="Loading bowlers…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By strike rate</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Bowler',
              format: (_v, r: BowlingLeaderEntry) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="bowler" gender={gender}
                />
              ) as unknown as string,
            },
            { key: 'strike_rate', label: 'SR', sortable: true, format: (v) => fmt(v, 2) },
            { key: 'wickets', label: 'W' },
            { key: 'balls', label: 'Balls' },
          ]}
          data={data.by_strike_rate}
          rowKey={(r) => r.person_id}
        />
      </div>
      <div>
        <h3 className="wisden-section-title">By economy</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Bowler',
              format: (_v, r: BowlingLeaderEntry) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="bowler" gender={gender}
                />
              ) as unknown as string,
            },
            { key: 'economy', label: 'Econ', sortable: true, format: (v) => fmt(v, 2) },
            { key: 'wickets', label: 'W' },
            { key: 'balls', label: 'Balls' },
          ]}
          data={data.by_economy}
          rowKey={(r) => r.person_id}
        />
      </div>
    </div>
  )
}

function FieldersTab({
  loading, error, data, refetch, gender,
}: {
  loading: boolean; error: string | null
  data: FieldingLeaders | null; refetch: () => void
  gender: string | null | undefined
  venue: string
}) {
  if (loading) return <Spinner label="Loading fielders…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By dismissals (all)</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Fielder',
              format: (_v, r: FieldingLeaderEntry) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="fielder" gender={gender}
                />
              ) as unknown as string,
            },
            { key: 'total', label: 'Total', sortable: true },
            { key: 'catches', label: 'C' },
            { key: 'stumpings', label: 'St' },
            { key: 'run_outs', label: 'RO' },
          ]}
          data={data.by_dismissals}
          rowKey={(r) => r.person_id}
        />
      </div>
      <div>
        <h3 className="wisden-section-title">By keeper dismissals</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Keeper',
              format: (_v, r: FieldingLeaderEntry) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="fielder" gender={gender}
                />
              ) as unknown as string,
            },
            { key: 'total', label: 'Total', sortable: true },
            { key: 'catches', label: 'C' },
            { key: 'stumpings', label: 'St' },
          ]}
          data={data.by_keeper_dismissals}
          rowKey={(r) => r.person_id}
        />
      </div>
    </div>
  )
}

function MatchesTab({
  loading, error, matches, total, refetch,
  pageSize, offset, onOffsetChange,
}: {
  loading: boolean; error: string | null
  matches: MatchListItem[]; total: number; refetch: () => void
  pageSize: number
  offset: number
  onOffsetChange: (o: number) => void
}) {
  if (loading) return <Spinner label="Loading matches…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!matches.length) return <div className="wisden-empty">No matches in scope.</div>
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.floor(offset / pageSize) + 1
  const rangeStart = offset + 1
  const rangeEnd = Math.min(offset + matches.length, total)
  return (
    <div className="mt-4">
      <div className="wisden-tab-help">
        Showing {rangeStart.toLocaleString()}–{rangeEnd.toLocaleString()} of {total.toLocaleString()} matches at this venue
        in the current filter scope.
      </div>
      <DataTable
        columns={[
          {
            key: 'date', label: 'Date', sortable: true,
            format: (v: string | null, r) => v
              ? (matchLink(r.match_id, v) as unknown as string)
              : '-',
          },
          { key: 'tournament', label: 'Tournament' },
          { key: 'season', label: 'Season' },
          {
            key: 'team1', label: 'Match',
            format: (_v, r) => (
              <>{teamLink(r.team1)}{' v '}{teamLink(r.team2)}</>
            ) as unknown as string,
          },
          {
            key: 'winner', label: 'Winner',
            format: (v: string | null, r) => v
              ? (teamLink(v) as unknown as string)
              : (r.result_text || '—'),
          },
          {
            key: 'team1_score', label: 'Score',
            format: (_v, r) => `${r.team1_score ?? '-'} / ${r.team2_score ?? '-'}`,
          },
        ]}
        data={matches}
        rowKey={(r) => `m-${r.match_id}`}
      />
      {totalPages > 1 && (
        <div className="wisden-pagination">
          <div className="wisden-pagination-buttons">
            <button
              onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
              disabled={offset === 0}>
              ← Previous
            </button>
          </div>
          <span>Page <span className="num">{currentPage}</span> of <span className="num">{totalPages}</span></span>
          <div className="wisden-pagination-buttons">
            <button
              onClick={() => onOffsetChange(offset + pageSize)}
              disabled={offset + pageSize >= total}>
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function RecordsTab({
  loading, error, data, refetch,
}: {
  loading: boolean; error: string | null
  data: TournamentRecords | null; refetch: () => void
}) {
  if (loading) return <Spinner label="Loading records…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">Highest team totals</h3>
        <DataTable
          columns={[
            { key: 'runs', label: 'Runs', sortable: true },
            { key: 'team', label: 'Team', format: (v: string) => teamLink(v) as unknown as string },
            { key: 'opponent', label: 'vs', format: (v: string) => teamLink(v) as unknown as string },
            {
              key: 'date', label: 'Date',
              format: (_v, r: TournamentRecordTeamTotal) =>
                r.date ? (matchLink(r.match_id, r.date) as unknown as string) : '-',
            },
          ]}
          data={data.highest_team_totals}
          rowKey={(r) => `ht-${r.match_id}-${r.team}`}
        />
      </div>
      <div>
        <h3 className="wisden-section-title">Lowest all-out totals</h3>
        <DataTable
          columns={[
            { key: 'runs', label: 'Runs', sortable: true },
            { key: 'team', label: 'Team', format: (v: string) => teamLink(v) as unknown as string },
            { key: 'opponent', label: 'vs', format: (v: string) => teamLink(v) as unknown as string },
            {
              key: 'date', label: 'Date',
              format: (_v, r: TournamentRecordTeamTotal) =>
                r.date ? (matchLink(r.match_id, r.date) as unknown as string) : '-',
            },
          ]}
          data={data.lowest_all_out_totals}
          rowKey={(r) => `lo-${r.match_id}-${r.team}`}
        />
      </div>
      <div>
        <h3 className="wisden-section-title">Biggest wins by runs</h3>
        <DataTable
          columns={[
            { key: 'margin', label: 'Runs', sortable: true },
            { key: 'winner', label: 'Winner', format: (v: string) => teamLink(v) as unknown as string },
            { key: 'loser', label: 'Loser', format: (v: string) => teamLink(v) as unknown as string },
            {
              key: 'date', label: 'Date',
              format: (_v, r: TournamentRecordWin) =>
                r.date ? (matchLink(r.match_id, r.date) as unknown as string) : '-',
            },
          ]}
          data={data.biggest_wins_by_runs}
          rowKey={(r) => `br-${r.match_id}`}
        />
      </div>
      <div>
        <h3 className="wisden-section-title">Biggest wins by wickets</h3>
        <DataTable
          columns={[
            { key: 'margin', label: 'Wkts', sortable: true },
            { key: 'winner', label: 'Winner', format: (v: string) => teamLink(v) as unknown as string },
            { key: 'loser', label: 'Loser', format: (v: string) => teamLink(v) as unknown as string },
            {
              key: 'date', label: 'Date',
              format: (_v, r: TournamentRecordWin) =>
                r.date ? (matchLink(r.match_id, r.date) as unknown as string) : '-',
            },
          ]}
          data={data.biggest_wins_by_wickets}
          rowKey={(r) => `bw-${r.match_id}`}
        />
      </div>
      <div>
        <h3 className="wisden-section-title">Largest partnerships</h3>
        <DataTable
          columns={[
            { key: 'runs', label: 'Runs', sortable: true },
            {
              key: 'batter1', label: 'Batters',
              format: (_v, r: TournamentRecordPartnership) => (
                <>
                  {r.batter1 && <PlayerLink personId={r.batter1.person_id} name={r.batter1.name} role="batter" />}
                  {' & '}
                  {r.batter2 && <PlayerLink personId={r.batter2.person_id} name={r.batter2.name} role="batter" />}
                </>
              ) as unknown as string,
            },
            {
              key: 'date', label: 'Date',
              format: (_v, r: TournamentRecordPartnership) =>
                r.date ? (matchLink(r.match_id, r.date) as unknown as string) : '-',
            },
          ]}
          data={data.largest_partnerships}
          rowKey={(r) => `lp-${r.match_id}-${r.batting_team}`}
        />
      </div>
      <div>
        <h3 className="wisden-section-title">Best bowling figures</h3>
        <DataTable
          columns={[
            { key: 'figures', label: 'Figures', sortable: true },
            {
              key: 'name', label: 'Bowler',
              format: (_v, r: TournamentRecordBowling) => (
                <PlayerLink personId={r.person_id} name={r.name} role="bowler" />
              ) as unknown as string,
            },
            {
              key: 'date', label: 'Date',
              format: (_v, r: TournamentRecordBowling) =>
                r.date ? (matchLink(r.match_id, r.date) as unknown as string) : '-',
            },
          ]}
          data={data.best_bowling_figures}
          rowKey={(r) => `bb-${r.match_id}-${r.person_id}`}
        />
      </div>
      <div className="lg:col-span-2">
        <h3 className="wisden-section-title">Most sixes in a match</h3>
        <DataTable
          columns={[
            { key: 'sixes', label: 'Sixes', sortable: true },
            { key: 'teams', label: 'Teams' },
            {
              key: 'date', label: 'Date',
              format: (_v, r: TournamentRecordMatchSixes) =>
                r.date ? (matchLink(r.match_id, r.date) as unknown as string) : '-',
            },
          ]}
          data={data.most_sixes_in_a_match}
          rowKey={(r) => `ms-${r.match_id}`}
        />
      </div>
    </div>
  )
}
