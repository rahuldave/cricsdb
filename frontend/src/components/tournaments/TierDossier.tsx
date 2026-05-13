/**
 * TierDossier — above-tournament match-set dossier.
 *
 * Renders on /series when the FilterBar narrows to a scope broader
 * than any single tournament — "men's club," "women's international,"
 * "men's primary-tier clubs," etc. Mirrors TournamentDossier's tab
 * layout so every narrowing reads "identically to a series":
 *
 *   Overview / Batting / Bowling / Fielding / Partnerships / Records / Matches
 *
 * (Editions / Points are tournament-specific and hidden here.)
 *
 * Uses the lean /league/* composite endpoints for the Overview tab
 * (the heavy /series/summary endpoint scans the whole pool — 20s at
 * broad scope; /league/overview is ~3s by skipping the deep
 * sub-queries). Records / Partnerships / Matches tabs reuse the same
 * /series/{records,partnerships/*,matches} endpoints TournamentDossier
 * uses — every one of those already accepts tournament=null.
 *
 * The H2 title comes from `scopeToProse(filters)` rather than the
 * dot-separated abbreviation used on subject-pages — the scope IS
 * the page subject, so the abbreviation becomes the title and the
 * right-side italic abbreviation would be redundant.
 *
 * Spec: internal_docs/spec-league-pages.md (originally /league;
 * merged into /series per user feedback 2026-05-13).
 */
import { useEffect, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../../hooks/useFilters'
import { useUrlParam } from '../../hooks/useUrlState'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useFetch } from '../../hooks/useFetch'
import { useFilterDeps } from '../../hooks/useFilterDeps'
import {
  getLeagueOverview, getLeagueChampions, getTournamentsLanding,
  getLeagueBattersLeaders, getLeagueBowlersLeaders, getLeagueFieldersLeaders,
  getScopeBattingSummary, getScopeBattingBySeason,
  getScopeBowlingSummary, getScopeBowlingBySeason,
  getScopeFieldingSummary, getScopeFieldingBySeason,
  getTournamentRecords, getMatches,
  getTournamentPartnershipsByWicket, getTournamentPartnershipsTop,
  getTournamentPartnershipsTopByWicket,
} from '../../api'
import { scopeToProse } from '../scopeLinks'
import InningToggle from '../InningToggle'
import StatCard from '../StatCard'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import { SectionHeader } from '../ChartHeader'
import DataTable, { type Column } from '../DataTable'
import TeamLink from '../TeamLink'
import Score from '../Score'
import PlayerLink from '../PlayerLink'
import TournamentTile, { tileAmbientFromFilters } from './TournamentTile'
import {
  SeriesBattingTileRow, SeriesBattingChartStrip,
  SeriesBowlingTileRow, SeriesBowlingChartStrip,
  SeriesFieldingTileRow, SeriesFieldingChartStrip,
  RecordsTab, PartnershipsTab, MatchesTab,
} from './TournamentDossier'
import type {
  LeagueOverview, LeagueChampionRow, LeagueTopTeamRow,
  TournamentsLanding, TournamentLandingEntry,
  ScopeBattingSummary, ScopeBattingSeason,
  BattingLeaders, BattingLeaderEntry,
  ScopeBowlingSummary, ScopeBowlingSeason,
  BowlingLeaders, BowlingLeaderEntry,
  ScopeFieldingSummary, ScopeFieldingSeason,
  FieldingLeaders, FieldingLeaderEntry,
  TournamentRecords, MatchListItem,
  TournamentPartnershipsByWicket, TournamentPartnershipsTop,
  TournamentPartnershipsTopByWicket,
} from '../../types'

type TabName =
  | 'Overview' | 'Batting' | 'Bowling' | 'Fielding'
  | 'Partnerships' | 'Records' | 'Matches'
const TABS: TabName[] = [
  'Overview', 'Batting', 'Bowling', 'Fielding',
  'Partnerships', 'Records', 'Matches',
]

export default function TierDossier() {
  const filters = useFilters()
  const [activeTab, setActiveTab] = useUrlParam('tab', 'Overview')
  const currentTab: TabName = TABS.includes(activeTab as TabName)
    ? (activeTab as TabName)
    : 'Overview'

  const docTitle = scopeToProse(filters)
  useDocumentTitle(docTitle)

  const filterDeps = useFilterDeps()
  const apiFilters = filters

  // ── Overview tab data (lean /league/overview composite) ───────
  const overviewFetch = useFetch<LeagueOverview | null>(
    () => currentTab === 'Overview'
      ? getLeagueOverview(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Overview'],
  )
  const championsFetch = useFetch<{ rows: LeagueChampionRow[] } | null>(
    () => currentTab === 'Overview'
      ? getLeagueChampions(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Overview'],
  )
  const landingFetch = useFetch<TournamentsLanding | null>(
    () => currentTab === 'Overview'
      ? getTournamentsLanding(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Overview'],
  )

  // ── Batting / Bowling / Fielding tab data ─────────────────────
  const battingSummaryFetch = useFetch<ScopeBattingSummary | null>(
    () => currentTab === 'Batting'
      ? getScopeBattingSummary(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Batting'],
  )
  const battingBySeasonFetch = useFetch<{ by_season: ScopeBattingSeason[] } | null>(
    () => currentTab === 'Batting'
      ? getScopeBattingBySeason(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Batting'],
  )
  const battingLeadersFetch = useFetch<BattingLeaders | null>(
    () => currentTab === 'Batting'
      ? getLeagueBattersLeaders({ ...filters, limit: 50 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Batting'],
  )

  const bowlingSummaryFetch = useFetch<ScopeBowlingSummary | null>(
    () => currentTab === 'Bowling'
      ? getScopeBowlingSummary(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Bowling'],
  )
  const bowlingBySeasonFetch = useFetch<{ by_season: ScopeBowlingSeason[] } | null>(
    () => currentTab === 'Bowling'
      ? getScopeBowlingBySeason(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Bowling'],
  )
  const bowlingLeadersFetch = useFetch<BowlingLeaders | null>(
    () => currentTab === 'Bowling'
      ? getLeagueBowlersLeaders({ ...filters, limit: 50 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Bowling'],
  )

  const fieldingSummaryFetch = useFetch<ScopeFieldingSummary | null>(
    () => currentTab === 'Fielding'
      ? getScopeFieldingSummary(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Fielding'],
  )
  const fieldingBySeasonFetch = useFetch<{ by_season: ScopeFieldingSeason[] } | null>(
    () => currentTab === 'Fielding'
      ? getScopeFieldingBySeason(filters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Fielding'],
  )
  const fieldingLeadersFetch = useFetch<FieldingLeaders | null>(
    () => currentTab === 'Fielding'
      ? getLeagueFieldersLeaders({ ...filters, limit: 50 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Fielding'],
  )

  // ── Records / Partnerships / Matches tab data — reuse existing
  //    /series/* endpoints (already accept tournament=null). ─────
  const recordsFetch = useFetch<TournamentRecords | null>(
    () => currentTab === 'Records'
      ? getTournamentRecords(null, { ...apiFilters, limit: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Records'],
  )

  const partnershipsByWicketFetch = useFetch<TournamentPartnershipsByWicket | null>(
    () => currentTab === 'Partnerships'
      ? getTournamentPartnershipsByWicket(null, { ...apiFilters, side: 'batting' })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Partnerships'],
  )
  const partnershipsTopFetch = useFetch<TournamentPartnershipsTop | null>(
    () => currentTab === 'Partnerships'
      ? getTournamentPartnershipsTop(null, { ...apiFilters, side: 'batting', limit: 20 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Partnerships'],
  )
  const partnershipsTopByWicketFetch = useFetch<TournamentPartnershipsTopByWicket | null>(
    () => currentTab === 'Partnerships'
      ? getTournamentPartnershipsTopByWicket(null, { ...apiFilters, side: 'batting', per_wicket: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Partnerships'],
  )

  const MATCHES_PAGE_SIZE = 50
  const [pageParam, setPageParam] = useUrlParam('page', '1')
  const matchesPage = Math.max(1, parseInt(pageParam, 10) || 1)
  const matchesOffset = (matchesPage - 1) * MATCHES_PAGE_SIZE
  // Reset pagination when filter scope changes; preserve deep-linked
  // ?tab=Matches&page=3. Mirror the prevFilterKey ref pattern from
  // TournamentDossier.
  const prevFilterKey = useRef<string | null>(null)
  useEffect(() => {
    const key = filterDeps.map(v => String(v ?? '')).join('|')
    if (prevFilterKey.current === null) { prevFilterKey.current = key; return }
    if (prevFilterKey.current !== key) {
      prevFilterKey.current = key
      if (pageParam && pageParam !== '1') setPageParam('', { replace: true })
    }
  }, filterDeps)

  const matchesFetch = useFetch<{ matches: MatchListItem[]; total: number } | null>(
    () => currentTab === 'Matches'
      ? getMatches({
          ...filters,
          limit: MATCHES_PAGE_SIZE, offset: matchesOffset,
        })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Matches', matchesOffset],
  )

  return (
    <div>
      <h2 className="wisden-page-title" style={{ margin: 0 }}>
        {docTitle}
      </h2>

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

      {(currentTab === 'Batting' || currentTab === 'Bowling'
        || currentTab === 'Fielding' || currentTab === 'Partnerships'
        || currentTab === 'Records') && <InningToggle />}

      {currentTab === 'Overview' && (
        <OverviewTab
          overview={overviewFetch.data}
          overviewLoading={overviewFetch.loading}
          overviewError={overviewFetch.error}
          overviewRefetch={overviewFetch.refetch}
          champions={championsFetch.data?.rows ?? null}
          championsLoading={championsFetch.loading}
          landing={landingFetch.data}
          landingLoading={landingFetch.loading}
        />
      )}
      {currentTab === 'Batting' && (
        <BattingSubtab
          summary={battingSummaryFetch.data}
          seasons={battingBySeasonFetch.data?.by_season ?? null}
          leaders={battingLeadersFetch.data}
          loading={
            battingSummaryFetch.loading
            || battingBySeasonFetch.loading
            || battingLeadersFetch.loading
          }
          error={
            battingSummaryFetch.error
            || battingBySeasonFetch.error
            || battingLeadersFetch.error
          }
          refetch={() => {
            battingSummaryFetch.refetch()
            battingBySeasonFetch.refetch()
            battingLeadersFetch.refetch()
          }}
        />
      )}
      {currentTab === 'Bowling' && (
        <BowlingSubtab
          summary={bowlingSummaryFetch.data}
          seasons={bowlingBySeasonFetch.data?.by_season ?? null}
          leaders={bowlingLeadersFetch.data}
          loading={
            bowlingSummaryFetch.loading
            || bowlingBySeasonFetch.loading
            || bowlingLeadersFetch.loading
          }
          error={
            bowlingSummaryFetch.error
            || bowlingBySeasonFetch.error
            || bowlingLeadersFetch.error
          }
          refetch={() => {
            bowlingSummaryFetch.refetch()
            bowlingBySeasonFetch.refetch()
            bowlingLeadersFetch.refetch()
          }}
        />
      )}
      {currentTab === 'Fielding' && (
        <FieldingSubtab
          summary={fieldingSummaryFetch.data}
          seasons={fieldingBySeasonFetch.data?.by_season ?? null}
          leaders={fieldingLeadersFetch.data}
          loading={
            fieldingSummaryFetch.loading
            || fieldingBySeasonFetch.loading
            || fieldingLeadersFetch.loading
          }
          error={
            fieldingSummaryFetch.error
            || fieldingBySeasonFetch.error
            || fieldingLeadersFetch.error
          }
          refetch={() => {
            fieldingSummaryFetch.refetch()
            fieldingBySeasonFetch.refetch()
            fieldingLeadersFetch.refetch()
          }}
        />
      )}
      {currentTab === 'Partnerships' && (
        <PartnershipsTab
          byWicket={partnershipsByWicketFetch.data}
          byWicketLoading={partnershipsByWicketFetch.loading}
          top={partnershipsTopFetch.data}
          topLoading={partnershipsTopFetch.loading}
          topByWicket={partnershipsTopByWicketFetch.data}
          topByWicketLoading={partnershipsTopByWicketFetch.loading}
          filterTeam={filters.team}
          tournament={null}
          gender={filters.gender}
          teamType={filters.team_type}
        />
      )}
      {currentTab === 'Records' && (
        <RecordsTab
          loading={recordsFetch.loading}
          error={recordsFetch.error}
          data={recordsFetch.data}
          refetch={recordsFetch.refetch}
          tournament={null}
          gender={filters.gender}
          team_type={filters.team_type}
        />
      )}
      {currentTab === 'Matches' && (
        <MatchesTab
          loading={matchesFetch.loading}
          error={matchesFetch.error}
          matches={matchesFetch.data?.matches ?? []}
          total={matchesFetch.data?.total ?? 0}
          refetch={matchesFetch.refetch}
          tournament={null}
          gender={filters.gender}
          team_type={filters.team_type}
          pageSize={MATCHES_PAGE_SIZE}
          offset={matchesOffset}
          onPageChange={(p) => setPageParam(p > 1 ? String(p) : '')}
        />
      )}
    </div>
  )
}


// ─── Overview tab ──────────────────────────────────────────────────────

function OverviewTab({
  overview, overviewLoading, overviewError, overviewRefetch,
  champions, championsLoading,
  landing, landingLoading,
}: {
  overview: LeagueOverview | null
  overviewLoading: boolean
  overviewError: string | null
  overviewRefetch: () => void
  champions: LeagueChampionRow[] | null
  championsLoading: boolean
  landing: TournamentsLanding | null
  landingLoading: boolean
}) {
  const filters = useFilters()
  const ambient = tileAmbientFromFilters(filters)

  const tournamentTiles = useMemo<TournamentLandingEntry[]>(() => {
    if (!landing) return []
    const all = [
      ...landing.international.icc_events,
      ...landing.international.other_international,
      ...landing.club.franchise_leagues,
      ...landing.club.domestic_leagues,
      ...landing.club.women_franchise,
      ...landing.club.other,
    ]
    return all.sort((a, b) => b.matches - a.matches)
  }, [landing])

  if (overviewLoading && !overview) {
    return <Spinner label="Loading scope…" size="lg" />
  }
  if (overviewError) {
    return <ErrorBanner
      message={`Could not load: ${overviewError}`}
      onRetry={overviewRefetch} />
  }
  if (!overview) return null

  return (
    <div className="mt-4 space-y-8">
      <div className="wisden-statrow cols-4">
        <StatCard label="Matches" value={overview.matches.toLocaleString()} />
        <StatCard label="Innings" value={overview.innings.toLocaleString()} />
        <StatCard label="Teams" value={overview.teams_count.toLocaleString()} />
        <StatCard label="Tournaments" value={overview.tournaments_count.toLocaleString()} />
      </div>

      {(landingLoading || tournamentTiles.length > 0) && (
        <section>
          <SectionHeader title={
            <>Tournaments in scope ({tournamentTiles.length})</>
          } />
          {landingLoading && !landing ? (
            <Spinner label="Loading tournaments…" />
          ) : (
            <div className="wisden-tile-grid mt-2">
              {tournamentTiles.map(entry => (
                <TournamentTile
                  key={entry.canonical}
                  entry={entry}
                  ambient={ambient}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {champions !== null && champions.length > 0 && (
        <section>
          <SectionHeader title="Champions in scope" />
          <ChampionsTable rows={champions} />
        </section>
      )}
      {championsLoading && champions === null && (
        <Spinner label="Loading champions…" />
      )}

      {overview.top_teams.length > 0 && (
        <section>
          <SectionHeader title="Top teams by win %" />
          <TopTeamsTable rows={overview.top_teams} />
        </section>
      )}

      {hasAnyBestMoment(overview.best_moments) && (
        <section>
          <SectionHeader title="Best moments" />
          <BestMomentsCards moments={overview.best_moments} />
        </section>
      )}
    </div>
  )
}


function hasAnyBestMoment(m: LeagueOverview['best_moments']) {
  return !!(m.highest_total || m.lowest_all_out
    || m.biggest_win_runs || m.biggest_win_wickets
    || m.most_sixes_match)
}


function ChampionsTable({ rows }: { rows: LeagueChampionRow[] }) {
  const filters = useFilters()
  const gender = filters.gender ?? null
  const team_type = filters.team_type ?? null

  const teamCell = (team: string, row: LeagueChampionRow) => (
    <TeamLink
      teamName={team}
      gender={gender}
      team_type={team_type}
      subscriptSource={{
        tournament: row.tournament,
        season: row.season,
        team1: null,
        team2: null,
      }}
      maxTiers={1}
      phraseLabel="ed"
      phraseClassName="scope-phrase-ed"
    />
  ) as unknown as string

  const finalCell = (row: LeagueChampionRow) => (
    <Score
      team1Score={row.final_team1_score}
      team2Score={row.final_team2_score}
      matchId={row.final_match_id}
      title={`Final scorecard — ${row.final_team1} v ${row.final_team2}`}
    />
  ) as unknown as string

  const cols: Column<LeagueChampionRow>[] = [
    { key: 'season', label: 'Season', sortable: true },
    { key: 'tournament', label: 'Tournament', sortable: true },
    { key: 'champion', label: 'Champion',
      format: (v: string, r: LeagueChampionRow) => teamCell(v, r) },
    { key: 'runner_up', label: 'Runner-up',
      format: (v: string, r: LeagueChampionRow) => teamCell(v, r) },
    { key: 'final_match_id', label: 'Final',
      format: (_v, r: LeagueChampionRow) => finalCell(r) },
  ]
  return (
    <DataTable
      columns={cols}
      data={rows}
      rowKey={(r) => `${r.season}-${r.tournament}`}
    />
  )
}


function TopTeamsTable({ rows }: { rows: LeagueTopTeamRow[] }) {
  const filters = useFilters()
  const gender = filters.gender ?? null
  const team_type = filters.team_type ?? null

  const teamCell = (team: string) => (
    <TeamLink
      teamName={team}
      gender={gender}
      team_type={team_type}
      compact
    />
  ) as unknown as string

  const cols: Column<LeagueTopTeamRow>[] = [
    { key: 'team', label: 'Team',
      format: (v: string) => teamCell(v) },
    { key: 'played', label: 'P', sortable: true },
    { key: 'wins', label: 'W' },
    { key: 'losses', label: 'L' },
    { key: 'win_pct', label: 'Win %', sortable: true,
      format: (v: number | null) => v != null ? `${v.toFixed(1)}%` : '-' },
  ]
  return <DataTable columns={cols} data={rows} rowKey={(r) => r.team} />
}


function BestMomentsCards({
  moments,
}: {
  moments: LeagueOverview['best_moments']
}) {
  const filters = useFilters()
  const gender = filters.gender ?? null
  const team_type = filters.team_type ?? null

  const teamChip = (team: string) => (
    <TeamLink teamName={team} compact gender={gender} team_type={team_type} />
  )

  const tournamentSeason = (
    tournament: string | null,
    season: string | null,
  ) => {
    if (!tournament && !season) return null
    if (tournament && season) return ` · ${tournament}, ${season}`
    return ` · ${tournament ?? season}`
  }

  const matchLink = (matchId: number, label: string | number) => (
    <Link to={`/matches/${matchId}`} className="comp-link">{label}</Link>
  )

  return (
    <div className="wisden-tile-line mt-2 space-y-2">
      {moments.highest_total && (
        <div>
          <span className="wisden-tile-faint">Highest total: </span>
          <span className="wisden-tile-em">{moments.highest_total.runs}</span>
          <span className="wisden-tile-faint">
            {' ('}
            {teamChip(moments.highest_total.team)}
            {' v '}
            {teamChip(moments.highest_total.opponent)}
            {')'}
            {moments.highest_total.date && (
              <> · {matchLink(moments.highest_total.match_id, moments.highest_total.date)}</>
            )}
            {tournamentSeason(moments.highest_total.tournament, moments.highest_total.season)}
          </span>
        </div>
      )}
      {moments.lowest_all_out && (
        <div>
          <span className="wisden-tile-faint">Lowest all-out: </span>
          <span className="wisden-tile-em">{moments.lowest_all_out.runs}</span>
          <span className="wisden-tile-faint">
            {' ('}
            {teamChip(moments.lowest_all_out.team)}
            {' v '}
            {teamChip(moments.lowest_all_out.opponent)}
            {')'}
            {moments.lowest_all_out.date && (
              <> · {matchLink(moments.lowest_all_out.match_id, moments.lowest_all_out.date)}</>
            )}
            {tournamentSeason(moments.lowest_all_out.tournament, moments.lowest_all_out.season)}
          </span>
        </div>
      )}
      {moments.biggest_win_runs && (
        <div>
          <span className="wisden-tile-faint">Biggest win by runs: </span>
          {teamChip(moments.biggest_win_runs.winner)}
          <span className="wisden-tile-faint"> beat </span>
          {teamChip(moments.biggest_win_runs.loser)}
          <span className="wisden-tile-faint">
            {' by '}
            <span className="wisden-tile-em">{moments.biggest_win_runs.margin} runs</span>
            {moments.biggest_win_runs.date && (
              <> · {matchLink(moments.biggest_win_runs.match_id, moments.biggest_win_runs.date)}</>
            )}
            {tournamentSeason(moments.biggest_win_runs.tournament, moments.biggest_win_runs.season)}
          </span>
        </div>
      )}
      {moments.biggest_win_wickets && (
        <div>
          <span className="wisden-tile-faint">Biggest win by wickets: </span>
          {teamChip(moments.biggest_win_wickets.winner)}
          <span className="wisden-tile-faint"> beat </span>
          {teamChip(moments.biggest_win_wickets.loser)}
          <span className="wisden-tile-faint">
            {' by '}
            <span className="wisden-tile-em">{moments.biggest_win_wickets.margin} wickets</span>
            {moments.biggest_win_wickets.date && (
              <> · {matchLink(moments.biggest_win_wickets.match_id, moments.biggest_win_wickets.date)}</>
            )}
            {tournamentSeason(moments.biggest_win_wickets.tournament, moments.biggest_win_wickets.season)}
          </span>
        </div>
      )}
      {moments.most_sixes_match && (
        <div>
          <span className="wisden-tile-faint">Most sixes in a match: </span>
          <span className="wisden-tile-em">{moments.most_sixes_match.sixes} sixes</span>
          <span className="wisden-tile-faint">
            {' ('}
            {teamChip(moments.most_sixes_match.team1)}
            {' v '}
            {teamChip(moments.most_sixes_match.team2)}
            {')'}
            {moments.most_sixes_match.date && (
              <> · {matchLink(moments.most_sixes_match.match_id, moments.most_sixes_match.date)}</>
            )}
            {tournamentSeason(moments.most_sixes_match.tournament, moments.most_sixes_match.season)}
          </span>
        </div>
      )}
    </div>
  )
}


// ─── Batting subtab ───────────────────────────────────────────────────

function BattingSubtab({
  summary, seasons, leaders, loading, error, refetch,
}: {
  summary: ScopeBattingSummary | null
  seasons: ScopeBattingSeason[] | null
  leaders: BattingLeaders | null
  loading: boolean
  error: string | null
  refetch: () => void
}) {
  const filters = useFilters()
  const gender = filters.gender ?? null

  if (loading && !summary) return <Spinner label="Loading batters…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />

  const fmt = (v: number | null | undefined, d = 2) =>
    v == null ? '-' : v.toFixed(d)

  const batterCell = (r: BattingLeaderEntry) => (
    <PlayerLink
      personId={r.person_id}
      name={r.name}
      role="batter"
      gender={gender}
    />
  ) as unknown as string

  return (
    <div className="mt-4 space-y-6">
      <SeriesBattingTileRow summary={summary} seasons={seasons} />
      <SeriesBattingChartStrip seasons={seasons} />
      {leaders && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div>
            <SectionHeader title="Top batters by runs" />
            <DataTable
              columns={[
                { key: 'name', label: 'Batter',
                  format: (_v, r: BattingLeaderEntry) => batterCell(r) },
                { key: 'runs', label: 'Runs', sortable: true },
                { key: 'balls', label: 'Balls' },
                { key: 'strike_rate', label: 'SR',
                  format: (v: number | null) => fmt(v) },
              ] as Column<BattingLeaderEntry>[]}
              data={leaders.by_runs}
              rowKey={(r) => `bruns-${r.person_id}`}
            />
          </div>
          <div>
            <SectionHeader title="Top batters by average" />
            <DataTable
              columns={[
                { key: 'name', label: 'Batter',
                  format: (_v, r: BattingLeaderEntry) => batterCell(r) },
                { key: 'average', label: 'Avg', sortable: true,
                  format: (v: number | null) => fmt(v) },
                { key: 'runs', label: 'Runs' },
                { key: 'dismissals', label: 'Out' },
              ] as Column<BattingLeaderEntry>[]}
              data={leaders.by_average}
              rowKey={(r) => `bavg-${r.person_id}`}
            />
          </div>
          <div>
            <SectionHeader title="Top batters by strike rate" />
            <DataTable
              columns={[
                { key: 'name', label: 'Batter',
                  format: (_v, r: BattingLeaderEntry) => batterCell(r) },
                { key: 'strike_rate', label: 'SR', sortable: true,
                  format: (v: number | null) => fmt(v) },
                { key: 'runs', label: 'Runs' },
                { key: 'balls', label: 'Balls' },
              ] as Column<BattingLeaderEntry>[]}
              data={leaders.by_strike_rate}
              rowKey={(r) => `bsr-${r.person_id}`}
            />
          </div>
        </div>
      )}
    </div>
  )
}


// ─── Bowling subtab ───────────────────────────────────────────────────

function BowlingSubtab({
  summary, seasons, leaders, loading, error, refetch,
}: {
  summary: ScopeBowlingSummary | null
  seasons: ScopeBowlingSeason[] | null
  leaders: BowlingLeaders | null
  loading: boolean
  error: string | null
  refetch: () => void
}) {
  const filters = useFilters()
  const gender = filters.gender ?? null

  if (loading && !summary) return <Spinner label="Loading bowlers…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />

  const fmt = (v: number | null | undefined, d = 2) =>
    v == null ? '-' : v.toFixed(d)

  const bowlerCell = (r: BowlingLeaderEntry) => (
    <PlayerLink
      personId={r.person_id}
      name={r.name}
      role="bowler"
      gender={gender}
    />
  ) as unknown as string

  return (
    <div className="mt-4 space-y-6">
      <SeriesBowlingTileRow summary={summary} seasons={seasons} />
      <SeriesBowlingChartStrip seasons={seasons} />
      {leaders && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div>
            <SectionHeader title="Top bowlers by wickets" />
            <DataTable
              columns={[
                { key: 'name', label: 'Bowler',
                  format: (_v, r: BowlingLeaderEntry) => bowlerCell(r) },
                { key: 'wickets', label: 'W', sortable: true },
                { key: 'balls', label: 'Balls' },
                { key: 'economy', label: 'Econ',
                  format: (v: number | null) => fmt(v) },
              ] as Column<BowlingLeaderEntry>[]}
              data={leaders.by_wickets}
              rowKey={(r) => `bwkts-${r.person_id}`}
            />
          </div>
          <div>
            <SectionHeader title="Top bowlers by economy" />
            <DataTable
              columns={[
                { key: 'name', label: 'Bowler',
                  format: (_v, r: BowlingLeaderEntry) => bowlerCell(r) },
                { key: 'economy', label: 'Econ', sortable: true,
                  format: (v: number | null) => fmt(v) },
                { key: 'wickets', label: 'W' },
                { key: 'balls', label: 'Balls' },
              ] as Column<BowlingLeaderEntry>[]}
              data={leaders.by_economy}
              rowKey={(r) => `becon-${r.person_id}`}
            />
          </div>
          <div>
            <SectionHeader title="Top bowlers by strike rate" />
            <DataTable
              columns={[
                { key: 'name', label: 'Bowler',
                  format: (_v, r: BowlingLeaderEntry) => bowlerCell(r) },
                { key: 'strike_rate', label: 'SR', sortable: true,
                  format: (v: number | null) => fmt(v) },
                { key: 'wickets', label: 'W' },
                { key: 'balls', label: 'Balls' },
              ] as Column<BowlingLeaderEntry>[]}
              data={leaders.by_strike_rate}
              rowKey={(r) => `bsr-${r.person_id}`}
            />
          </div>
        </div>
      )}
    </div>
  )
}


// ─── Fielding subtab ──────────────────────────────────────────────────

function FieldingSubtab({
  summary, seasons, leaders, loading, error, refetch,
}: {
  summary: ScopeFieldingSummary | null
  seasons: ScopeFieldingSeason[] | null
  leaders: FieldingLeaders | null
  loading: boolean
  error: string | null
  refetch: () => void
}) {
  const filters = useFilters()
  const gender = filters.gender ?? null

  if (loading && !summary) return <Spinner label="Loading fielders…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />

  const fielderCell = (r: FieldingLeaderEntry) => (
    <PlayerLink
      personId={r.person_id}
      name={r.name}
      role="fielder"
      gender={gender}
    />
  ) as unknown as string

  return (
    <div className="mt-4 space-y-6">
      <SeriesFieldingTileRow summary={summary} seasons={seasons} />
      <SeriesFieldingChartStrip seasons={seasons} />
      {leaders && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div>
            <SectionHeader title="Top fielders by dismissals" />
            <DataTable
              columns={[
                { key: 'name', label: 'Fielder',
                  format: (_v, r: FieldingLeaderEntry) => fielderCell(r) },
                { key: 'total', label: 'Total', sortable: true },
                { key: 'catches', label: 'C' },
                { key: 'stumpings', label: 'St' },
                { key: 'run_outs', label: 'RO' },
              ] as Column<FieldingLeaderEntry>[]}
              data={leaders.by_dismissals}
              rowKey={(r) => `fall-${r.person_id}`}
            />
          </div>
          <div>
            <SectionHeader title="Top keepers" />
            <DataTable
              columns={[
                { key: 'name', label: 'Keeper',
                  format: (_v, r: FieldingLeaderEntry) => fielderCell(r) },
                { key: 'total', label: 'Total', sortable: true },
                { key: 'catches', label: 'C' },
                { key: 'stumpings', label: 'St' },
              ] as Column<FieldingLeaderEntry>[]}
              data={leaders.by_keeper_dismissals}
              rowKey={(r) => `fkep-${r.person_id}`}
            />
          </div>
          <div>
            <SectionHeader title="Top fielders by run-outs" />
            <DataTable
              columns={[
                { key: 'name', label: 'Fielder',
                  format: (_v, r: FieldingLeaderEntry) => fielderCell(r) },
                { key: 'run_outs', label: 'RO', sortable: true },
                { key: 'total', label: 'Total' },
                { key: 'catches', label: 'C' },
              ] as Column<FieldingLeaderEntry>[]}
              data={leaders.by_run_outs ?? []}
              rowKey={(r) => `fro-${r.person_id}`}
            />
          </div>
        </div>
      )}
    </div>
  )
}
