import { Link } from 'react-router-dom'
import { useFilters } from '../FilterBar'
import { useUrlParam, useSetUrlParams } from '../../hooks/useUrlState'
import { useFetch } from '../../hooks/useFetch'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import {
  getTournamentSummary, getTournamentBySeason, getTournamentPointsTable,
  getTournamentRecords,
  getTournamentBattersLeaders, getTournamentBowlersLeaders, getTournamentFieldersLeaders,
  getTournamentPartnershipsByWicket, getTournamentPartnershipsTop,
  getMatches,
} from '../../api'
import StatCard from '../StatCard'
import PlayerLink from '../PlayerLink'
import DataTable, { type Column } from '../DataTable'
import LineChart from '../charts/LineChart'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import type {
  TournamentSummary, TournamentSeason, TournamentPointsTableResponse,
  PointsTableRow, TournamentRecords,
  TournamentRecordTeamTotal, TournamentRecordWin,
  TournamentRecordPartnership, TournamentRecordBowling, TournamentRecordMatchSixes,
  BattingLeaders, BowlingLeaders, FieldingLeaders,
  MatchListItem,
  TournamentPartnershipsByWicket, TournamentPartnershipsTop,
  TournamentPartnershipTopEntry,
} from '../../types'

const fmt = (v: number | null | undefined, d = 2) =>
  v == null ? '-' : typeof v === 'number' ? v.toFixed(d) : v

const matchLink = (matchId: number, label: string | number) => (
  <Link to={`/matches/${matchId}`} className="comp-link">{label}</Link>
)

const partnershipMatchLink = (
  matchId: number, label: string | number,
  batter1Id: string | null | undefined,
  batter2Id: string | null | undefined,
) => {
  const ids = [batter1Id, batter2Id].filter(Boolean).join(',')
  const qs = ids ? `?highlight_batter=${encodeURIComponent(ids)}` : ''
  return (
    <Link to={`/matches/${matchId}${qs}`} className="comp-link">{label}</Link>
  )
}

/** Team-name link with the dossier's scope preserved. Teams are
 *  identity-bound to a tournament for clubs and narrow naturally via
 *  FilterBar on the team page, so one link (no name/context split) is
 *  sufficient. */
function teamLinkHref(team: string, scope: {
  tournament: string | null
  gender: string | null | undefined
}): string {
  const p = new URLSearchParams({ team })
  if (scope.tournament) p.set('tournament', scope.tournament)
  if (scope.gender) p.set('gender', scope.gender)
  return `/teams?${p.toString()}`
}

// Tab list — Points only included when single-season is in scope; rendered
// conditionally so it doesn't flash on/off during filter changes.
const BASE_TABS = ['Overview', 'Editions', 'Batters', 'Bowlers', 'Fielders', 'Partnerships', 'Records', 'Matches'] as const
type TabName = typeof BASE_TABS[number] | 'Points'

export default function TournamentDossier({
  tournament, filterTeam, filterOpponent,
}: {
  tournament: string | null
  filterTeam?: string | null
  filterOpponent?: string | null
}) {
  const filters = useFilters()
  const setUrlParams = useSetUrlParams()
  const [seriesType, setSeriesType] = useUrlParam('series_type', 'all')
  const isRivalryMode = !!(filterTeam && filterOpponent)
  const isSingleTournament = !!tournament

  // Build filters object with rivalry + series_type passthrough so all
  // endpoint calls pick up the same scope. URL is the source of truth.
  const apiFilters = {
    ...filters,
    filter_team: filterTeam || undefined,
    filter_opponent: filterOpponent || undefined,
    series_type: seriesType === 'all' ? undefined : seriesType,
  }

  const docTitle = isRivalryMode
    ? (isSingleTournament
        ? `${filterTeam} v ${filterOpponent} · ${tournament}`
        : `${filterTeam} v ${filterOpponent}`)
    : (tournament || 'Match-set')
  useDocumentTitle(docTitle)

  const singleSeason = !!(filters.season_from && filters.season_to
    && filters.season_from === filters.season_to)
  // Editions / Points only make sense in a tournament context.
  const tabs: TabName[] = (() => {
    const base: TabName[] = ['Overview']
    if (isSingleTournament) base.push('Editions')
    if (isSingleTournament && singleSeason) base.push('Points')
    base.push('Batters', 'Bowlers', 'Fielders', 'Partnerships', 'Records', 'Matches')
    return base
  })()

  const [activeTab, setActiveTab] = useUrlParam('tab', 'Overview')
  const currentTab = tabs.includes(activeTab as TabName) ? (activeTab as TabName) : 'Overview'

  const filterDeps = [
    tournament, filterTeam, filterOpponent, seriesType,
    filters.gender, filters.team_type,
    filters.season_from, filters.season_to,
  ]

  const summaryFetch = useFetch<TournamentSummary>(
    () => getTournamentSummary(tournament, apiFilters),
    filterDeps,
  )

  const bySeasonFetch = useFetch<{ tournament: string; seasons: TournamentSeason[] } | null>(
    () => isSingleTournament && (currentTab === 'Editions' || currentTab === 'Overview')
      ? getTournamentBySeason(tournament, apiFilters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Editions' || currentTab === 'Overview'],
  )

  const pointsFetch = useFetch<TournamentPointsTableResponse | null>(
    () => currentTab === 'Points' && singleSeason && tournament
      ? getTournamentPointsTable(tournament, apiFilters)
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Points'],
  )

  const battingFetch = useFetch<BattingLeaders | null>(
    () => currentTab === 'Batters'
      ? getTournamentBattersLeaders(tournament, { ...apiFilters, limit: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Batters'],
  )
  const bowlingFetch = useFetch<BowlingLeaders | null>(
    () => currentTab === 'Bowlers'
      ? getTournamentBowlersLeaders(tournament, { ...apiFilters, limit: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Bowlers'],
  )
  const fieldingFetch = useFetch<FieldingLeaders | null>(
    () => currentTab === 'Fielders'
      ? getTournamentFieldersLeaders(tournament, { ...apiFilters, limit: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Fielders'],
  )

  const recordsFetch = useFetch<TournamentRecords | null>(
    () => currentTab === 'Records'
      ? getTournamentRecords(tournament, { ...apiFilters, limit: 5 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Records'],
  )

  const matchesFetch = useFetch<{ matches: MatchListItem[]; total: number } | null>(
    () => currentTab === 'Matches'
      ? getMatches({
          ...filters,
          team: filterTeam || undefined,
          tournament: tournament || undefined,
          limit: 50, offset: 0,
        })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Matches'],
  )

  const partnershipsByWicketFetch = useFetch<TournamentPartnershipsByWicket | null>(
    () => currentTab === 'Partnerships'
      ? getTournamentPartnershipsByWicket(tournament, { ...apiFilters, side: 'batting' })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Partnerships'],
  )
  const partnershipsTopFetch = useFetch<TournamentPartnershipsTop | null>(
    () => currentTab === 'Partnerships'
      ? getTournamentPartnershipsTop(tournament, { ...apiFilters, side: 'batting', limit: 10 })
      : Promise.resolve(null),
    [...filterDeps, currentTab === 'Partnerships'],
  )

  if (summaryFetch.loading) {
    const loadingFor = isRivalryMode
      ? `${filterTeam} v ${filterOpponent}`
      : (tournament || 'match-set')
    return <Spinner label={`Loading ${loadingFor}…`} size="lg" />
  }
  if (summaryFetch.error || !summaryFetch.data) {
    return (
      <ErrorBanner
        message={`Could not load: ${summaryFetch.error || 'no data'}`}
        onRetry={summaryFetch.refetch}
      />
    )
  }
  const summary = summaryFetch.data

  // Title composition — rivalry comes first (subject), tournament after (modifier).
  // Show gender suffix for rivalry views since the dossier itself can't
  // tell male v female apart from the team strings (cricsheet uses the
  // same "India" / "Australia" labels for both).
  const genderSuffix = isRivalryMode && filters.gender
    ? (filters.gender === 'female' ? " women's" : " men's")
    : ''
  const headlineTitle = isRivalryMode
    ? (
        <>
          {filterTeam} <span className="wisden-h2h-vs">v</span> {filterOpponent}
          {genderSuffix && (
            <span className="wisden-tile-faint" style={{ fontSize: '0.7em' }}>
              {genderSuffix}
            </span>
          )}
          {tournament && (
            <span className="wisden-tile-faint">
              {' · '}{tournament}
            </span>
          )}
        </>
      )
    : (tournament || summary.canonical || 'Match-set')

  return (
    <div>
      <h2 className="wisden-page-title">{headlineTitle}</h2>
      <div className="wisden-page-subtitle">
        {isSingleTournament && summary.editions > 0 && (
          <>
            {summary.editions} {summary.editions === 1 ? 'edition' : 'editions'}
            {' · '}
          </>
        )}
        {summary.matches.toLocaleString()} matches
        {summary.variants.length > 1 && (
          <span className="wisden-tile-faint">
            {' '}(merged: {summary.variants.join(', ')})
          </span>
        )}
      </div>

      {/* Series-type pill — hidden/relabeled based on FilterBar team_type
          so "All meetings" never misrepresents the scope. See the same
          logic in HeadToHead.tsx. */}
      {isRivalryMode && !isSingleTournament && (() => {
        const isClub = filters.team_type === 'club'
        const isIntl = filters.team_type === 'international'
        const opts = (['all', 'bilateral', 'icc', 'club'] as const).filter(s =>
          s === 'all'
            || (s === 'bilateral' && !isClub)
            || (s === 'icc' && !isClub)
            || (s === 'club' && !isIntl))
        if (seriesType && !opts.includes(seriesType as typeof opts[number])) {
          setSeriesType('')
        }
        if (isClub) {
          return (
            <div className="mt-3 wisden-tab-help">
              Showing: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Club tournaments</span>
            </div>
          )
        }
        const allLabel = isIntl ? 'All international' : 'All meetings'
        return (
          <div className="mt-3 flex items-center gap-2 wisden-tab-help flex-wrap">
            <span>Show:</span>
            {opts.map(s => (
              <button
                key={s}
                type="button"
                className={`wisden-clear${seriesType === s ? ' is-active' : ''}`}
                onClick={() => setSeriesType(s === 'all' ? '' : s)}
                style={{
                  color: seriesType === s ? 'var(--accent)' : 'var(--ink-faint)',
                  fontWeight: seriesType === s ? 600 : 400,
                }}
              >
                {s === 'all' ? allLabel
                  : s === 'bilateral' ? 'Bilateral T20Is'
                  : s === 'icc' ? 'ICC events'
                  : 'Club tournaments'}
              </button>
            ))}
          </div>
        )
      })()}

      <div className="wisden-tabs mt-4">
        {tabs.map(tab => (
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

      {currentTab === 'Overview' && (
        <OverviewTab
          summary={summary}
          seasons={bySeasonFetch.data?.seasons ?? []}
          tournament={tournament}
          gender={filters.gender}
        />
      )}
      {currentTab === 'Editions' && (
        <EditionsTab
          loading={bySeasonFetch.loading}
          error={bySeasonFetch.error}
          seasons={bySeasonFetch.data?.seasons ?? []}
          onPickSeason={(s) => setUrlParams({
            season_from: s, season_to: s, tab: 'Overview',
          })}
          refetch={bySeasonFetch.refetch}
        />
      )}
      {currentTab === 'Points' && (
        <PointsTab
          loading={pointsFetch.loading}
          error={pointsFetch.error}
          data={pointsFetch.data}
          refetch={pointsFetch.refetch}
        />
      )}
      {currentTab === 'Batters' && (
        <BattersTab
          loading={battingFetch.loading}
          error={battingFetch.error}
          data={battingFetch.data}
          refetch={battingFetch.refetch}
          tournament={tournament}
          filterTeam={filterTeam}
          filterOpponent={filterOpponent}
          gender={filters.gender}
        />
      )}
      {currentTab === 'Bowlers' && (
        <BowlersTab
          loading={bowlingFetch.loading}
          error={bowlingFetch.error}
          data={bowlingFetch.data}
          refetch={bowlingFetch.refetch}
          tournament={tournament}
          filterTeam={filterTeam}
          filterOpponent={filterOpponent}
          gender={filters.gender}
        />
      )}
      {currentTab === 'Fielders' && (
        <FieldersTab
          loading={fieldingFetch.loading}
          error={fieldingFetch.error}
          data={fieldingFetch.data}
          refetch={fieldingFetch.refetch}
          tournament={tournament}
          filterTeam={filterTeam}
          filterOpponent={filterOpponent}
          gender={filters.gender}
        />
      )}
      {currentTab === 'Records' && (
        <RecordsTab
          loading={recordsFetch.loading}
          error={recordsFetch.error}
          data={recordsFetch.data}
          refetch={recordsFetch.refetch}
          tournament={tournament}
          gender={filters.gender}
        />
      )}
      {currentTab === 'Matches' && (
        <MatchesTab
          loading={matchesFetch.loading}
          error={matchesFetch.error}
          matches={matchesFetch.data?.matches ?? []}
          total={matchesFetch.data?.total ?? 0}
          refetch={matchesFetch.refetch}
          tournament={tournament}
          gender={filters.gender}
        />
      )}
      {currentTab === 'Partnerships' && (
        <PartnershipsTab
          byWicket={partnershipsByWicketFetch.data}
          byWicketLoading={partnershipsByWicketFetch.loading}
          top={partnershipsTopFetch.data}
          topLoading={partnershipsTopFetch.loading}
          filterTeam={filters.team}
        />
      )}
    </div>
  )
}

// ─── Tabs ─────────────────────────────────────────────────────────────

// Convert cricsheet season strings to a numeric x-axis value.
// "2024" → 2024. "2022/23" → 2022.5. Keeps chronological ordering
// while staying numeric so Semiotic's linear scale treats each edition
// as a separate point.
const seasonNum = (s: string): number => {
  const [y] = s.split('/')
  const base = parseInt(y, 10)
  return s.includes('/') ? base + 0.5 : base
}

function OverviewTab({
  summary, seasons, tournament, gender,
}: {
  summary: TournamentSummary
  seasons: TournamentSeason[]
  tournament: string | null
  gender: string | null | undefined
}) {
  // Seasons come newest-first from backend — flip for chart reading left-to-right.
  const trend = [...seasons].reverse()
    .filter(s => s.run_rate != null)
    .map(s => ({ ...s, _x: seasonNum(s.season) }))
  const isRivalry = !!summary.by_team
  const teamNames = isRivalry && summary.by_team ? Object.keys(summary.by_team) : []

  const h2h = summary.head_to_head
  return (
    <div>
      {/* Rivalry-mode head-to-head stats up top — the basic
          "who won how much" answer that wasn't surfaced before. */}
      {h2h && (
        <div className="wisden-statrow cols-5 mt-4">
          <StatCard label="Matches" value={summary.matches.toLocaleString()} />
          <StatCard
            label={h2h.team1}
            value={h2h.team1_wins}
            subtitle={summary.matches > 0
              ? `${((h2h.team1_wins * 100) / summary.matches).toFixed(0)}%`
              : undefined}
          />
          <StatCard
            label={h2h.team2}
            value={h2h.team2_wins}
            subtitle={summary.matches > 0
              ? `${((h2h.team2_wins * 100) / summary.matches).toFixed(0)}%`
              : undefined}
          />
          <StatCard label="Ties" value={h2h.ties} />
          <StatCard label="No result" value={h2h.no_result} />
        </div>
      )}

      <div className="wisden-statrow cols-5 mt-4">
        {!h2h && <StatCard label="Matches" value={summary.matches.toLocaleString()} />}
        <StatCard label="Run rate" value={fmt(summary.run_rate, 2)} subtitle="per over" />
        <StatCard label="Boundary %" value={fmt(summary.boundary_pct, 1)} />
        <StatCard label="Dot %" value={fmt(summary.dot_pct, 1)} />
        <StatCard label="Sixes" value={summary.total_sixes.toLocaleString()} />
      </div>

      <div className="wisden-statrow mt-2">
        {summary.most_titles && (
          <StatCard
            label="Most titles"
            value={summary.most_titles.team}
            subtitle={`${summary.most_titles.titles} ${summary.most_titles.titles === 1 ? 'title' : 'titles'}`}
          />
        )}
        {summary.top_scorer_alltime && (
          <StatCard
            label="Top scorer"
            value={summary.top_scorer_alltime.name}
            subtitle={`${summary.top_scorer_alltime.runs.toLocaleString()} runs`}
          />
        )}
        {summary.top_wicket_taker_alltime && (
          <StatCard
            label="Top wicket-taker"
            value={summary.top_wicket_taker_alltime.name}
            subtitle={`${summary.top_wicket_taker_alltime.wickets} wickets`}
          />
        )}
        {summary.highest_team_total && (
          <StatCard
            label="Highest total"
            value={`${summary.highest_team_total.total}`}
            subtitle={`${summary.highest_team_total.team} v ${summary.highest_team_total.opponent}`}
          />
        )}
      </div>

      {trend.length > 1 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <LineChart
            data={trend}
            xAccessor="_x"
            yAccessor="run_rate"
            title="Run rate by season"
            xLabel="season"
            yLabel="runs/over"
            showPoints
            curve="monotoneX"
          />
          <LineChart
            data={trend.filter(s => s.boundary_pct != null)}
            xAccessor="_x"
            yAccessor="boundary_pct"
            title="Boundary % by season"
            xLabel="season"
            yLabel="% of balls"
            showPoints
            curve="monotoneX"
          />
        </div>
      )}

      {/* ── Per-team breakdown when in rivalry scope ── */}
      {isRivalry && summary.by_team && (
        <div className="mt-8">
          <h3 className="wisden-section-title">By team</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {teamNames.map(team => {
              const t = summary.by_team![team]
              // Context = "at <team>" so the second link lands the player
              // page narrowed to this team's matches within the rivalry.
              const ctxParams = { filter_team: team }
              const ctxLabel = `at ${team}`
              return (
                <div key={team} className="wisden-tile">
                  <div className="wisden-tile-title">
                    <Link
                      to={teamLinkHref(team, { tournament, gender })}
                      className="comp-link"
                      style={{ textDecoration: 'none' }}
                    >
                      {team}
                    </Link>
                  </div>
                  <div className="wisden-tile-line mt-2">
                    {t.top_scorer && (
                      <div>
                        <span className="wisden-tile-faint">Top scorer: </span>
                        <PlayerLink
                          personId={t.top_scorer.person_id} name={t.top_scorer.name}
                          role="batter" gender={gender}
                          contextLabel={ctxLabel} contextParams={ctxParams}
                        />
                        <span className="wisden-tile-faint"> · {t.top_scorer.runs} runs</span>
                      </div>
                    )}
                    {t.top_wicket_taker && (
                      <div>
                        <span className="wisden-tile-faint">Top wicket-taker: </span>
                        <PlayerLink
                          personId={t.top_wicket_taker.person_id} name={t.top_wicket_taker.name}
                          role="bowler" gender={gender}
                          contextLabel={ctxLabel} contextParams={ctxParams}
                        />
                        <span className="wisden-tile-faint"> · {t.top_wicket_taker.wickets} wkts</span>
                      </div>
                    )}
                    {t.highest_individual && (
                      <div>
                        <span className="wisden-tile-faint">Highest individual: </span>
                        <PlayerLink
                          personId={t.highest_individual.person_id} name={t.highest_individual.name}
                          role="batter" gender={gender}
                          contextLabel={ctxLabel} contextParams={ctxParams}
                        />
                        <span className="wisden-tile-faint"> · {t.highest_individual.runs}</span>
                        {t.highest_individual.date && (
                          <> {' '}{matchLink(t.highest_individual.match_id, `(${t.highest_individual.date})`)}</>
                        )}
                      </div>
                    )}
                    {t.largest_partnership && (
                      <div>
                        <span className="wisden-tile-faint">Largest partnership: </span>
                        <span className="wisden-tile-em">{t.largest_partnership.runs}</span>
                        <span className="wisden-tile-faint">
                          {' '}(
                          <PlayerLink
                            personId={t.largest_partnership.batter1?.person_id}
                            name={t.largest_partnership.batter1?.name ?? ''}
                            role="batter" gender={gender}
                          />
                          {' & '}
                          <PlayerLink
                            personId={t.largest_partnership.batter2?.person_id}
                            name={t.largest_partnership.batter2?.name ?? ''}
                            role="batter" gender={gender}
                          />
                          )
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Groups (only meaningful for a single edition with a tournament) ── */}
      {tournament && summary.editions === 1 && summary.groups.length > 0 && (
        <div className="mt-8">
          <h3 className="wisden-section-title">Groups</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {summary.groups.map(g => (
              <div key={`${g.season}-${g.group}`} className="wisden-tile">
                <div className="wisden-tile-title">Group {g.group}</div>
                <div className="wisden-tile-line mt-1">
                  {g.teams.map(t => (
                    <div key={t.team}>
                      {t.team} <span className="wisden-tile-faint">· {t.matches} m</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Knockouts (finals, semis, qualifiers) ── */}
      {summary.knockouts.length > 0 && (
        <div className="mt-8">
          <h3 className="wisden-section-title">Knockouts</h3>
          <DataTable
            columns={[
              { key: 'season', label: 'Season' },
              { key: 'stage', label: 'Stage' },
              {
                key: 'team1', label: 'Match',
                format: (_v, r) => (
                  <>
                    <Link to={teamLinkHref(r.team1, { tournament, gender })} className="comp-link">{r.team1}</Link>
                    {' v '}
                    <Link to={teamLinkHref(r.team2, { tournament, gender })} className="comp-link">{r.team2}</Link>
                  </>
                ) as unknown as string,
              },
              {
                key: 'winner', label: 'Winner',
                format: (v: string | null, r) => v
                  ? (
                      <>
                        <Link to={teamLinkHref(v, { tournament, gender })} className="comp-link">{v}</Link>
                        {` (${r.margin})`}
                      </>
                    ) as unknown as string
                  : (r.margin || '—'),
              },
              { key: 'venue', label: 'Venue' },
              {
                key: 'date', label: 'Date',
                format: (v: string | null, r) => v
                  ? (matchLink(r.match_id, v) as unknown as string)
                  : '-',
              },
            ]}
            data={summary.knockouts}
            rowKey={(r) => `ko-${r.match_id}`}
          />
        </div>
      )}

      {/* ── Participating teams (only meaningful for tournaments) ── */}
      {tournament && summary.teams.length > 0 && (
        <div className="mt-8">
          <h3 className="wisden-section-title">
            Participating teams ({summary.teams.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {summary.teams.map(t => (
              <Link
                key={t.name}
                to={teamLinkHref(t.name, { tournament, gender })}
                className="wisden-chip comp-link"
                style={{ textDecoration: 'none' }}
              >
                {t.name}
                <span className="wisden-tile-faint"> · {t.matches}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {tournament && summary.champions_by_season.length > 0 && (
        <div className="mt-8">
          <h3 className="wisden-section-title">Champions by season</h3>
          <DataTable
            columns={[
              { key: 'season', label: 'Season', sortable: true },
              {
                key: 'champion', label: 'Champion', sortable: true,
                format: (v: string) => (
                  <Link to={teamLinkHref(v, { tournament, gender })} className="comp-link">{v}</Link>
                ) as unknown as string,
              },
              {
                key: 'match_id', label: 'Final',
                format: (v: number) => matchLink(v, 'scorecard →') as unknown as string,
              },
            ]}
            data={summary.champions_by_season}
          />
        </div>
      )}
    </div>
  )
}

function PartnershipsTab({
  byWicket, byWicketLoading, top, topLoading, filterTeam,
}: {
  byWicket: TournamentPartnershipsByWicket | null
  byWicketLoading: boolean
  top: TournamentPartnershipsTop | null
  topLoading: boolean
  filterTeam: string | null | undefined
}) {
  return (
    <div className="mt-4">
      {filterTeam ? (
        <div className="wisden-tab-help">
          Partnerships scoped to <strong>{filterTeam}</strong>. Remove the
          team filter for tournament-wide baseline.
        </div>
      ) : (
        <div className="wisden-tab-help">
          Tournament-wide averages across all teams in scope — the
          baseline any single team's partnerships get compared against.
        </div>
      )}

      {/* ── By-wicket averages ── */}
      <div className="mt-4">
        <h3 className="wisden-section-title">By wicket — averages</h3>
        <div className="wisden-tab-help">
          N is the sample count — how many partnerships of that wicket
          number were aggregated in scope. Best stand disambiguates the
          single best partnership in the current filter.
        </div>
        {byWicketLoading ? (
          <Spinner label="Loading by-wicket…" />
        ) : !byWicket?.by_wicket?.length ? (
          <div className="wisden-empty">No partnerships in scope.</div>
        ) : (
          <DataTable
            columns={[
              { key: 'wicket_number', label: 'Wkt', sortable: true },
              { key: 'n', label: 'N', sortable: true },
              {
                key: 'avg_runs', label: 'Avg', sortable: true,
                format: (v: number | null) => fmt(v, 1),
              },
              {
                key: 'avg_balls', label: 'Balls',
                format: (v: number | null) => fmt(v, 1),
              },
              { key: 'best_runs', label: 'Best', sortable: true },
              {
                key: 'best_partnership', label: 'Best stand',
                format: (_v, r) => r.best_partnership
                  ? `${r.best_partnership.batter1.name} & ${r.best_partnership.batter2.name}`
                  : '-',
              },
              {
                key: 'best_partnership', label: 'Match',
                format: (_v, r) => r.best_partnership
                  ? `${r.best_partnership.batting_team} v ${r.best_partnership.opponent}`
                  : '-',
              },
              {
                key: 'best_partnership', label: 'Season',
                format: (_v, r) => r.best_partnership?.season ?? '-',
              },
              {
                key: 'best_partnership', label: 'Date',
                format: (_v, r) => r.best_partnership && r.best_partnership.date
                  ? (partnershipMatchLink(
                      r.best_partnership.match_id,
                      r.best_partnership.date,
                      r.best_partnership.batter1.person_id,
                      r.best_partnership.batter2.person_id,
                    ) as unknown as string)
                  : '-',
              },
            ]}
            data={byWicket.by_wicket}
            rowKey={(r) => `w-${r.wicket_number}`}
          />
        )}
      </div>

      {/* ── Top partnerships ── */}
      <div className="mt-8">
        <h3 className="wisden-section-title">
          Top partnerships{filterTeam ? ` (${filterTeam})` : ''}
        </h3>
        {topLoading ? (
          <Spinner label="Loading top…" />
        ) : !top?.partnerships?.length ? (
          <div className="wisden-empty">No partnerships in scope.</div>
        ) : (
          <DataTable
            columns={[
              { key: 'runs', label: 'Runs', sortable: true },
              { key: 'wicket_number', label: 'Wkt' },
              {
                key: 'batter1', label: 'Batters',
                format: (_v, r: TournamentPartnershipTopEntry) =>
                  `${r.batter1.name} & ${r.batter2.name}`,
              },
              {
                key: 'batting_team', label: 'Match',
                format: (_v, r: TournamentPartnershipTopEntry) =>
                  `${r.batting_team} v ${r.opponent}`,
              },
              { key: 'season', label: 'Season' },
              {
                key: 'date', label: 'Date',
                format: (v: string | null, r: TournamentPartnershipTopEntry) =>
                  v ? (partnershipMatchLink(
                      r.match_id, v, r.batter1.person_id, r.batter2.person_id,
                    ) as unknown as string) : '-',
              },
            ]}
            data={top.partnerships}
            rowKey={(r) => `p-${r.partnership_id}`}
          />
        )}
      </div>
    </div>
  )
}

function MatchesTab({
  loading, error, matches, total, refetch, tournament, gender,
}: {
  loading: boolean; error: string | null
  matches: MatchListItem[]; total: number; refetch: () => void
  tournament: string | null
  gender: string | null | undefined
}) {
  if (loading) return <Spinner label="Loading matches…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!matches.length) {
    return <div className="wisden-empty">No matches in this filter scope.</div>
  }
  const scope = { tournament, gender }
  return (
    <div className="mt-4">
      <div className="wisden-tab-help">
        Showing {matches.length} of {total.toLocaleString()} matches in scope.
        Filters (gender, team type, seasons) respected.
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
              <>
                <Link to={teamLinkHref(r.team1, scope)} className="comp-link">{r.team1}</Link>
                {' v '}
                <Link to={teamLinkHref(r.team2, scope)} className="comp-link">{r.team2}</Link>
              </>
            ) as unknown as string,
          },
          {
            key: 'winner', label: 'Winner',
            format: (v: string | null, r) => v
              ? (<Link to={teamLinkHref(v, scope)} className="comp-link">{v}</Link>) as unknown as string
              : (r.result_text || '—'),
          },
          {
            key: 'team1_score', label: 'Score',
            format: (_v, r) => {
              const s1 = r.team1_score ?? '-'
              const s2 = r.team2_score ?? '-'
              return `${s1} / ${s2}`
            },
          },
          { key: 'venue', label: 'Venue' },
        ]}
        data={matches}
        rowKey={(r) => `m-${r.match_id}`}
      />
    </div>
  )
}

function EditionsTab({
  loading, error, seasons, onPickSeason, refetch,
}: {
  loading: boolean; error: string | null; seasons: TournamentSeason[]
  onPickSeason: (s: string) => void; refetch: () => void
}) {
  if (loading) return <Spinner label="Loading editions…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!seasons.length) return <div className="wisden-empty">No editions in scope.</div>

  const columns: Column<TournamentSeason>[] = [
    {
      key: 'season', label: 'Season', sortable: true,
      format: (v: string) => (
        <button
          type="button"
          className="comp-link"
          onClick={() => onPickSeason(v)}
        >{v}</button>
      ) as unknown as string,
    },
    { key: 'matches', label: 'Matches', sortable: true },
    { key: 'champion', label: 'Champion', sortable: true },
    { key: 'runner_up', label: 'Runner-up' },
    {
      key: 'top_scorer', label: 'Top scorer',
      format: (_v, r) => r.top_scorer
        ? (`${r.top_scorer.name} (${r.top_scorer.runs})`) : '-',
    },
    {
      key: 'top_wicket_taker', label: 'Top wicket-taker',
      format: (_v, r) => r.top_wicket_taker
        ? (`${r.top_wicket_taker.name} (${r.top_wicket_taker.wickets})`) : '-',
    },
    {
      key: 'run_rate', label: 'Run rate', sortable: true,
      format: (v: number | null) => fmt(v, 2),
    },
    {
      key: 'final_match_id', label: 'Final',
      format: (v: number | null) => v ? (matchLink(v, 'scorecard →') as unknown as string) : '-',
    },
  ]

  return (
    <div className="mt-4">
      <div className="wisden-tab-help">
        Click a season to narrow the whole page to that edition.
      </div>
      <DataTable columns={columns} data={seasons} />
    </div>
  )
}

function PointsTab({
  loading, error, data, refetch,
}: {
  loading: boolean; error: string | null
  data: TournamentPointsTableResponse | null; refetch: () => void
}) {
  if (loading) return <Spinner label="Loading points table…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null
  if (data.reason === 'multi_season') {
    return (
      <div className="wisden-empty">
        Points tables are per-edition. Set a single-season range to view.
      </div>
    )
  }
  if (!data.tables.length) {
    return <div className="wisden-empty">No league-stage matches in this edition.</div>
  }

  const columns: Column<PointsTableRow>[] = [
    { key: 'team', label: 'Team' },
    { key: 'played', label: 'P', sortable: true },
    { key: 'wins', label: 'W', sortable: true },
    { key: 'losses', label: 'L', sortable: true },
    { key: 'ties', label: 'T' },
    { key: 'nr', label: 'NR' },
    { key: 'points', label: 'Pts', sortable: true },
    {
      key: 'nrr', label: 'NRR', sortable: true,
      format: (v: number | null) => v == null ? '-' : (v >= 0 ? `+${v.toFixed(3)}` : v.toFixed(3)),
    },
  ]

  return (
    <div className="mt-4">
      {data.tables.map((t, i) => (
        <div key={i} className="mb-8">
          {t.group !== null && (
            <h3 className="wisden-section-title">Group {t.group}</h3>
          )}
          <DataTable columns={columns} data={t.rows} rowKey={(r) => r.team} />
        </div>
      ))}
    </div>
  )
}

/** Build the (label, params) pair for the contextual link shown after
 *  a player name. Tournament context wins over team-pair for compactness
 *  when both are set; user can still drill further via the player page. */
function playerContext(opts: {
  tournament: string | null
  filterTeam: string | null | undefined
  filterOpponent: string | null | undefined
}): { label: string; params: Record<string, string> } | undefined {
  const { tournament, filterTeam, filterOpponent } = opts
  if (tournament) {
    return { label: `in ${tournament}`, params: { tournament } }
  }
  if (filterTeam && filterOpponent) {
    return {
      label: `vs ${filterOpponent}`,
      params: { filter_team: filterTeam, filter_opponent: filterOpponent },
    }
  }
  if (filterTeam) {
    return { label: `at ${filterTeam}`, params: { filter_team: filterTeam } }
  }
  return undefined
}

function BattersTab({
  loading, error, data, refetch, tournament, filterTeam, filterOpponent, gender,
}: {
  loading: boolean; error: string | null
  data: BattingLeaders | null; refetch: () => void
  tournament: string | null
  filterTeam: string | null | undefined
  filterOpponent: string | null | undefined
  gender: string | null | undefined
}) {
  if (loading) return <Spinner label="Loading batters…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null

  const ctx = playerContext({ tournament, filterTeam, filterOpponent })

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By average (runs / dismissals)</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Batter',
              format: (_v, r) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="batter" gender={gender}
                  contextLabel={ctx?.label} contextParams={ctx?.params}
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
              format: (_v, r) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="batter" gender={gender}
                  contextLabel={ctx?.label} contextParams={ctx?.params}
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
  loading, error, data, refetch, tournament, filterTeam, filterOpponent, gender,
}: {
  loading: boolean; error: string | null
  data: BowlingLeaders | null; refetch: () => void
  tournament: string | null
  filterTeam: string | null | undefined
  filterOpponent: string | null | undefined
  gender: string | null | undefined
}) {
  if (loading) return <Spinner label="Loading bowlers…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null

  const ctx = playerContext({ tournament, filterTeam, filterOpponent })

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By strike rate</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Bowler',
              format: (_v, r) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="bowler" gender={gender}
                  contextLabel={ctx?.label} contextParams={ctx?.params}
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
              format: (_v, r) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="bowler" gender={gender}
                  contextLabel={ctx?.label} contextParams={ctx?.params}
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
  loading, error, data, refetch, tournament, filterTeam, filterOpponent, gender,
}: {
  loading: boolean; error: string | null
  data: FieldingLeaders | null; refetch: () => void
  tournament: string | null
  filterTeam: string | null | undefined
  filterOpponent: string | null | undefined
  gender: string | null | undefined
}) {
  if (loading) return <Spinner label="Loading fielders…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null

  const ctx = playerContext({ tournament, filterTeam, filterOpponent })

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By dismissals (all)</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Fielder',
              format: (_v, r) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="fielder" gender={gender}
                  contextLabel={ctx?.label} contextParams={ctx?.params}
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
              format: (_v, r) => (
                <PlayerLink
                  personId={r.person_id} name={r.name} role="fielder" gender={gender}
                  contextLabel={ctx?.label} contextParams={ctx?.params}
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

function RecordsTab({
  loading, error, data, refetch, tournament, gender,
}: {
  loading: boolean; error: string | null
  data: TournamentRecords | null; refetch: () => void
  tournament: string | null
  gender: string | null | undefined
}) {
  if (loading) return <Spinner label="Loading records…" />
  if (error) return <ErrorBanner message={error} onRetry={refetch} />
  if (!data) return null

  const scope = { tournament, gender }
  const teamCell = (v: string) => (
    <Link to={teamLinkHref(v, scope)} className="comp-link">{v}</Link>
  ) as unknown as string

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">Highest team totals</h3>
        <DataTable
          columns={[
            { key: 'runs', label: 'Runs', sortable: true },
            { key: 'team', label: 'Team', format: (v: string) => teamCell(v) },
            { key: 'opponent', label: 'vs', format: (v: string) => teamCell(v) },
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
            { key: 'team', label: 'Team', format: (v: string) => teamCell(v) },
            { key: 'opponent', label: 'vs', format: (v: string) => teamCell(v) },
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
            { key: 'winner', label: 'Winner', format: (v: string) => teamCell(v) },
            { key: 'loser', label: 'Loser', format: (v: string) => teamCell(v) },
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
            { key: 'winner', label: 'Winner', format: (v: string) => teamCell(v) },
            { key: 'loser', label: 'Loser', format: (v: string) => teamCell(v) },
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
              format: (_v, r: TournamentRecordPartnership) =>
                `${r.batter1?.name ?? '?'} & ${r.batter2?.name ?? '?'}`,
            },
            { key: 'teams', label: 'Match' },
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
            { key: 'name', label: 'Bowler' },
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
