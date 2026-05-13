/**
 * League page — above-tournament scope dossier.
 *
 * The destination for FilterBar configurations broader than a single
 * tournament: "men's club cricket," "men's primary-tier clubs,"
 * "women's international ICC tournaments," etc. Mirrors the
 * Tournament dossier shape (Overview / Batting / Bowling / Fielding
 * tabs) but the subject IS the scope itself.
 *
 * The H2 title renders the scope in prose English (Men's club
 * Twenty20 cricket) via `scopeToProse` rather than the dot-separated
 * abbreviation used elsewhere — there's no separate page subject to
 * pair the abbreviation with, so the abbreviation becomes the title.
 * Spec: internal_docs/spec-league-pages.md §D8 + user 2026-05-13.
 *
 * URL normalisation (Spec §D6 + UX §Empty/sparse):
 *  - Zero scope params → redirect to ?gender=male&team_type=club.
 *  - tournament=X set  → redirect to /series?tournament=X (the more
 *    specific destination; /league shouldn't duplicate Series).
 */
import { useEffect, useMemo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useFilters } from '../hooks/useFilters'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { useFetch } from '../hooks/useFetch'
import { useFilterDeps } from '../hooks/useFilterDeps'
import {
  getLeagueOverview, getLeagueChampions, getTournamentsLanding,
  getLeagueBattersLeaders,
  getScopeBattingSummary, getScopeBattingBySeason,
} from '../api'
import { scopeToProse } from '../components/scopeLinks'
import InningToggle from '../components/InningToggle'
import StatCard from '../components/StatCard'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { SectionHeader } from '../components/ChartHeader'
import DataTable, { type Column } from '../components/DataTable'
import TeamLink from '../components/TeamLink'
import Score from '../components/Score'
import TournamentTile, {
  tileAmbientFromFilters,
} from '../components/tournaments/TournamentTile'
import {
  SeriesBattingTileRow, SeriesBattingChartStrip,
} from '../components/tournaments/TournamentDossier'
import PlayerLink from '../components/PlayerLink'
import type {
  LeagueOverview, LeagueChampionRow, LeagueTopTeamRow,
  TournamentsLanding, TournamentLandingEntry,
  ScopeBattingSummary, ScopeBattingSeason,
  BattingLeaders, BattingLeaderEntry,
} from '../types'

type TabName = 'Overview' | 'Batting' | 'Bowling' | 'Fielding'
const TABS: TabName[] = ['Overview', 'Batting', 'Bowling', 'Fielding']

export default function League() {
  const filters = useFilters()
  const setUrlParams = useSetUrlParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [activeTab, setActiveTab] = useUrlParam('tab', 'Overview')
  const currentTab: TabName = TABS.includes(activeTab as TabName)
    ? (activeTab as TabName)
    : 'Overview'

  // D6: deep-link /league with no scope params lands on the broadest
  // tier (men's club). URL-clean rule exception: /league with no
  // params is non-canonical by construction; the replace lands a
  // canonical URL the user can share.
  useEffect(() => {
    if (!filters.gender && !filters.team_type && !filters.tournament) {
      setUrlParams({ gender: 'male', team_type: 'club' }, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Single-tournament redirect: /league?tournament=IPL → /series?tournament=IPL.
  useEffect(() => {
    if (filters.tournament) {
      navigate(`/series${location.search}`, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.tournament])

  const docTitle = scopeToProse(filters)
  useDocumentTitle(docTitle)

  const filterDeps = useFilterDeps()

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

  // ── Batting subtab data ───────────────────────────────────────
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

      {currentTab !== 'Overview' && <InningToggle />}

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
        <div className="wisden-tab-help mt-4">Bowling content lands in step 8.</div>
      )}
      {currentTab === 'Fielding' && (
        <div className="wisden-tab-help mt-4">Fielding content lands in step 9.</div>
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

  // Flatten the sectioned landing payload into a single tile list,
  // sorted by match count (the natural "biggest leagues first" order
  // a reader expects on a league-scope page).
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
    return <Spinner label="Loading league…" size="lg" />
  }
  if (overviewError) {
    return <ErrorBanner
      message={`Could not load league overview: ${overviewError}`}
      onRetry={overviewRefetch} />
  }
  if (!overview) return null

  return (
    <div className="mt-4 space-y-8">
      {/* Headline strip — match-set identity counts, no σ/Δ.*/}
      <div className="wisden-statrow cols-4">
        <StatCard label="Matches" value={overview.matches.toLocaleString()} />
        <StatCard label="Innings" value={overview.innings.toLocaleString()} />
        <StatCard label="Teams" value={overview.teams_count.toLocaleString()} />
        <StatCard label="Tournaments" value={overview.tournaments_count.toLocaleString()} />
      </div>

      {/* Tournaments tile grid — full reuse of TournamentTile from
          TournamentsLanding. Each card links to the all-editions
          dossier for that tournament. */}
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

      {/* Champions DataTable — cross-tournament finals in scope. */}
      {champions !== null && champions.length > 0 && (
        <section>
          <SectionHeader title="Champions in scope" />
          <ChampionsTable rows={champions} />
        </section>
      )}
      {championsLoading && champions === null && (
        <Spinner label="Loading champions…" />
      )}

      {/* Top teams by win % */}
      {overview.top_teams.length > 0 && (
        <section>
          <SectionHeader title="Top teams by win %" />
          <TopTeamsTable rows={overview.top_teams} />
        </section>
      )}

      {/* Best moments */}
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

  // teamCell wires per-row TeamLink with (ed) phrase pinning to the
  // row's (tournament, season). Same pattern as the Records/Matches
  // tabs on TournamentDossier.
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
