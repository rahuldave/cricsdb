import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useFilters } from '../../hooks/useFilters'
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
import TeamLink from '../TeamLink'
import SeriesLink from '../SeriesLink'
import {
  resolveBucket, resolveScopePhrases, seasonTag,
  type PhraseTier, type SubscriptSource,
} from '../scopeLinks'
import DataTable, { type Column } from '../DataTable'
import LineChart from '../charts/LineChart'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import type {
  TournamentSummary, TournamentSeason, TournamentPointsTableResponse,
  PointsTableRow, TournamentRecords,
  TournamentRecordTeamTotal, TournamentRecordWin,
  TournamentRecordPartnership, TournamentRecordBowling, TournamentRecordMatchSixes,
  BattingLeaders, BattingLeaderEntry,
  BowlingLeaders, BowlingLeaderEntry,
  FieldingLeaders, FieldingLeaderEntry,
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

type BatterLike = { person_id: string | null; name: string }
const renderBatter = (b: BatterLike) => b.person_id
  ? <Link to={`/batting?player=${encodeURIComponent(b.person_id)}`} className="comp-link">{b.name}</Link>
  : <>{b.name}</>
const renderBatterPair = (b1: BatterLike, b2: BatterLike) => (
  <>{renderBatter(b1)}{' & '}{renderBatter(b2)}</>
)

const renderVsTeams = (team1: string, team2: string, sep = ' v ') => (
  <>
    <Link to={`/teams?team=${encodeURIComponent(team1)}`} className="comp-link">{team1}</Link>
    {sep}
    <Link to={`/teams?team=${encodeURIComponent(team2)}`} className="comp-link">{team2}</Link>
  </>
)

const renderVsTeamsFromString = (s: string) => {
  const parts = s.split(/ vs | v /)
  if (parts.length !== 2) return s
  return renderVsTeams(parts[0].trim(), parts[1].trim())
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

  // Auto-reset series_type when a FilterBar change (team_type=club)
  // makes the current choice invalid. Replace — the reset is
  // auto-correcting, not a user pick.
  useEffect(() => {
    if (!isRivalryMode || isSingleTournament) return
    if (!seriesType || seriesType === 'all') return
    const isClub = filters.team_type === 'club'
    const isIntl = filters.team_type === 'international'
    const valid =
      (seriesType === 'bilateral' && !isClub)
      || (seriesType === 'icc' && !isClub)
      || (seriesType === 'club' && !isIntl)
    if (!valid) setSeriesType('', { replace: true })
  }, [isRivalryMode, isSingleTournament, seriesType, filters.team_type])

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
    filters.filter_venue,
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
          {/* H2 team links use block-layout subscripts. When tournament
              or season filter is set, each team's name gets small-caps
              phrase subscripts below it (tournament-level and/or
              edition-level). Rivalry is page identity (shown in the H2
              text) so it never produces a subscript — see resolveScopePhrases. */}
          <TeamLink teamName={filterTeam!} layout="block" />
          {' '}<span className="wisden-h2h-vs">v</span>{' '}
          <TeamLink teamName={filterOpponent!} layout="block" />
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
        // Invalid-series auto-reset handled in the useEffect below so
        // the setter doesn't fire during render (pushing history).
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
                onClick={() => {
                  // Clear tournament too. The series-type change
                  // usually invalidates the current tournament choice
                  // (e.g. "bilateral" + tournament=T20 WC is empty).
                  // If the new scope unambiguously implies one
                  // tournament, FilterBar's auto-narrow re-pins it via
                  // replace. Clearing here also ensures the push URL
                  // doesn't carry a stale tournament through the back
                  // button.
                  setUrlParams({
                    series_type: s === 'all' ? '' : s,
                    tournament: '',
                  })
                }}
                style={{
                  color: seriesType === s ? 'var(--accent)' : 'var(--ink-faint)',
                  fontWeight: seriesType === s ? 600 : 400,
                }}
              >
                {s === 'all' ? allLabel
                  : s === 'bilateral' ? 'only bilaterals'
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
          teamType={filters.team_type}
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
  summary, seasons, tournament, gender, teamType,
}: {
  summary: TournamentSummary
  seasons: TournamentSeason[]
  tournament: string | null
  gender: string | null | undefined
  teamType: string | null | undefined
}) {
  // Seasons come newest-first from backend — flip for chart reading left-to-right.
  const trend = [...seasons].reverse()
    .filter(s => s.run_rate != null)
    .map(s => ({ ...s, _x: seasonNum(s.season) }))
  const isRivalry = !!summary.by_team
  const teamNames = isRivalry && summary.by_team ? Object.keys(summary.by_team) : []

  const h2h = summary.head_to_head

  // Scope-phrase tiers for the top-of-Overview StatCards. Subtitle
  // renders tiers inline narrow→broad ("759 runs · at IPL, 2024, at IPL"),
  // giving readers every meaningful destination the card's scope implies.
  //
  // On rivalry scope, the phrase orientation must reflect the player's
  // own team. A batter playing for India against Australia should read
  // "vs Australia" (not "vs India"). `orientedSource` flips the rivalry
  // pair per-card based on the payload's `team` field; same pattern the
  // leaderboard tables use via `rowSubscriptSource`.
  const filters = useFilters()
  const [phraseSearchParams] = useSearchParams()
  const seriesType = phraseSearchParams.get('series_type')
  const filterTeam = filters.filter_team
  const filterOpponent = filters.filter_opponent

  const orientedSource = (rowTeam: string | null | undefined): SubscriptSource | undefined => {
    if (!filterTeam || !filterOpponent || !rowTeam) return undefined
    return rowTeam === filterOpponent
      ? { team1: filterOpponent, team2: filterTeam }
      : { team1: filterTeam, team2: filterOpponent }
  }

  /** Compute phrase tiers for one card, correctly oriented per its `rowTeam`. */
  const cardPhrases = (keepRivalry: boolean, rowTeam?: string | null): PhraseTier[] => {
    const source = keepRivalry ? orientedSource(rowTeam) : undefined
    const bucket = resolveBucket(filters, source)
    return resolveScopePhrases(bucket, { keepRivalry, seriesType })
  }

  /** Render the full tier chain inline, comma-separated. Matches PlayerLink
   *  / TeamLink inline format. Returns null when there are no phrases. */
  const phraseLinks = (
    phrases: PhraseTier[],
    baseHref: string,
    baseParams: Record<string, string>,
  ) => {
    if (phrases.length === 0) return null
    return (
      <>
        {phrases.map((ph, i) => {
          const qs = new URLSearchParams({ ...baseParams, ...ph.params })
          return (
            <span key={`${i}-${ph.label}`}>
              {i > 0 && <span className="scope-phrases-sep">, </span>}
              <Link
                to={`${baseHref}?${qs.toString()}`}
                className="comp-link scope-phrase"
                title={ph.tooltip}
              >
                {ph.label}
              </Link>
            </span>
          )
        })}
      </>
    )
  }

  // Per-card phrase tiers. Non-player-axis cards (Most titles, Highest
  // total) use keepRivalry=false so orientation is irrelevant — rivalry
  // drops from the URL, destination is the single-team/edition page.
  const teamCardPhrases = cardPhrases(false, null)
  const topScorerPhrases = summary.top_scorer_alltime
    ? cardPhrases(true, summary.top_scorer_alltime.team)
    : []
  const topWicketPhrases = summary.top_wicket_taker_alltime
    ? cardPhrases(true, summary.top_wicket_taker_alltime.team)
    : []
  // Largest partnership is attributed to the batting team (both batters
  // belong to it), so orient to the partnership's team. The other best-
  // moments lines use PlayerLink's native phrase rendering (name → stat
  // → phrase tiers via trailingContent), which orients via the
  // subscriptSource we pass directly.
  const lpPhrases = summary.largest_partnership
    ? cardPhrases(true, summary.largest_partnership.team)
    : []
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

      <div className={`wisden-statrow ${h2h ? 'cols-5' : 'cols-6'} mt-4`}>
        {!h2h && <StatCard label="Matches" value={summary.matches.toLocaleString()} />}
        <StatCard label="Run rate" value={fmt(summary.run_rate, 2)} subtitle="per over" />
        <StatCard label="Boundary %" value={fmt(summary.boundary_pct, 1)} />
        <StatCard label="Dot %" value={fmt(summary.dot_pct, 1)} />
        <StatCard label="Fours" value={summary.total_fours.toLocaleString()} />
        <StatCard label="Sixes" value={summary.total_sixes.toLocaleString()} />
      </div>

      {/* Leaders row — aggregate titles + top-of-leaderboard. */}
      <div className="wisden-statrow cols-3 mt-2">
        {summary.most_titles && (
          <StatCard
            label="Most titles"
            value={<TeamLink compact teamName={summary.most_titles.team} gender={gender} />}
            subtitle={
              <>
                {summary.most_titles.titles}{' '}
                {summary.most_titles.titles === 1 ? 'title' : 'titles'}
                {teamCardPhrases.length > 0 && (
                  <>
                    {' · '}
                    {phraseLinks(teamCardPhrases, '/teams', { team: summary.most_titles.team })}
                  </>
                )}
              </>
            }
          />
        )}
        {summary.top_scorer_alltime && (
          <StatCard
            label="Top scorer"
            value={
              <PlayerLink
                compact
                personId={summary.top_scorer_alltime.person_id}
                name={summary.top_scorer_alltime.name}
                role="batter"
                gender={gender}
                subscriptSource={orientedSource(summary.top_scorer_alltime.team)}
              />
            }
            subtitle={
              <>
                {summary.top_scorer_alltime.runs.toLocaleString()} runs
                {topScorerPhrases.length > 0 && summary.top_scorer_alltime.person_id && (
                  <>
                    {' · '}
                    {phraseLinks(topScorerPhrases, '/batting', {
                      player: summary.top_scorer_alltime.person_id,
                    })}
                  </>
                )}
              </>
            }
          />
        )}
        {summary.top_wicket_taker_alltime && (
          <StatCard
            label="Top wicket-taker"
            value={
              <PlayerLink
                compact
                personId={summary.top_wicket_taker_alltime.person_id}
                name={summary.top_wicket_taker_alltime.name}
                role="bowler"
                gender={gender}
                subscriptSource={orientedSource(summary.top_wicket_taker_alltime.team)}
              />
            }
            subtitle={
              <>
                {summary.top_wicket_taker_alltime.wickets} wickets
                {topWicketPhrases.length > 0 && summary.top_wicket_taker_alltime.person_id && (
                  <>
                    {' · '}
                    {phraseLinks(topWicketPhrases, '/bowling', {
                      player: summary.top_wicket_taker_alltime.person_id,
                    })}
                  </>
                )}
              </>
            }
          />
        )}
      </div>

      {/* Best moments — single-match highlights across the scope.
          Prose lines rather than tiles: too many big cards made the
          Overview read as a wall. Same markup as the rivalry by-team
          tile body. PlayerLink's `trailingContent` holds the stat; the
          scope-phrase tiers flow after it via the component's native
          phrase rendering. */}
      {(summary.highest_individual || summary.best_bowling
        || summary.largest_partnership || summary.best_fielding
        || summary.highest_team_total) && (
        <div className="mt-8">
          <h3 className="wisden-section-title">Best moments</h3>
          <div className="wisden-tile-line mt-2">
            {summary.highest_individual && (
              <div>
                <span className="wisden-tile-faint">Best batting: </span>
                <PlayerLink
                  personId={summary.highest_individual.person_id}
                  name={summary.highest_individual.name}
                  role="batter"
                  gender={gender}
                  subscriptSource={orientedSource(summary.highest_individual.team)}
                  trailingContent={
                    <span className="wisden-tile-faint">
                      {' · '}{summary.highest_individual.runs}
                      {summary.highest_individual.date && (
                        <> · {matchLink(summary.highest_individual.match_id, summary.highest_individual.date)}</>
                      )}
                    </span>
                  }
                />
              </div>
            )}
            {summary.best_bowling && (
              <div>
                <span className="wisden-tile-faint">Best bowling: </span>
                <PlayerLink
                  personId={summary.best_bowling.person_id}
                  name={summary.best_bowling.name}
                  role="bowler"
                  gender={gender}
                  subscriptSource={orientedSource(summary.best_bowling.team)}
                  trailingContent={
                    <span className="wisden-tile-faint">
                      {' · '}{summary.best_bowling.figures}
                      {summary.best_bowling.date && (
                        <> · {matchLink(summary.best_bowling.match_id, summary.best_bowling.date)}</>
                      )}
                    </span>
                  }
                />
              </div>
            )}
            {summary.largest_partnership && (
              <div>
                <span className="wisden-tile-faint">Highest partnership: </span>
                <span className="wisden-tile-em">{summary.largest_partnership.runs}</span>
                <span className="wisden-tile-faint">
                  {' ('}
                  <PlayerLink
                    compact
                    personId={summary.largest_partnership.batter1.person_id}
                    name={summary.largest_partnership.batter1.name}
                    role="batter"
                    gender={gender}
                  />
                  {' & '}
                  <PlayerLink
                    compact
                    personId={summary.largest_partnership.batter2.person_id}
                    name={summary.largest_partnership.batter2.name}
                    role="batter"
                    gender={gender}
                  />
                  {')'}
                  {summary.largest_partnership.date && (
                    <> · {matchLink(summary.largest_partnership.match_id, summary.largest_partnership.date)}</>
                  )}
                  {lpPhrases.length > 0 && summary.largest_partnership.team && (
                    <>
                      {' '}
                      {phraseLinks(lpPhrases, '/teams', { team: summary.largest_partnership.team })}
                    </>
                  )}
                </span>
              </div>
            )}
            {summary.best_fielding && (
              <div>
                <span className="wisden-tile-faint">Best fielding: </span>
                <PlayerLink
                  personId={summary.best_fielding.person_id}
                  name={summary.best_fielding.name}
                  role="fielder"
                  gender={gender}
                  subscriptSource={orientedSource(summary.best_fielding.team)}
                  trailingContent={
                    <span className="wisden-tile-faint">
                      {' · '}{summary.best_fielding.total} dismissal{summary.best_fielding.total === 1 ? '' : 's'}
                      {summary.best_fielding.date && (
                        <> · {matchLink(summary.best_fielding.match_id, summary.best_fielding.date)}</>
                      )}
                    </span>
                  }
                />
              </div>
            )}
            {summary.highest_team_total && (
              <div>
                <span className="wisden-tile-faint">Highest total: </span>
                <span className="wisden-tile-em">{summary.highest_team_total.total}</span>
                <span className="wisden-tile-faint">
                  {' ('}
                  <TeamLink compact teamName={summary.highest_team_total.team} gender={gender} />
                  {' v '}
                  <TeamLink compact teamName={summary.highest_team_total.opponent} gender={gender} />
                  {')'}
                  {summary.highest_team_total.date && (
                    <> · {matchLink(summary.highest_team_total.match_id, summary.highest_team_total.date)}</>
                  )}
                  {teamCardPhrases.length > 0 && (
                    <>
                      {' '}
                      {phraseLinks(teamCardPhrases, '/series', {})}
                    </>
                  )}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

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
              // Per-team tile in a rivalry dossier: the player link's
              // (s, b) tier should orient toward this tile's team.
              const otherTeam = teamNames.find(n => n !== team) ?? null
              const rivalrySrc = { team1: team, team2: otherTeam }
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
                          subscriptSource={rivalrySrc}
                          trailingContent={
                            <span className="wisden-tile-faint"> · {t.top_scorer.runs} runs</span>
                          }
                        />
                      </div>
                    )}
                    {t.top_wicket_taker && (
                      <div>
                        <span className="wisden-tile-faint">Top wicket-taker: </span>
                        <PlayerLink
                          personId={t.top_wicket_taker.person_id} name={t.top_wicket_taker.name}
                          role="bowler" gender={gender}
                          subscriptSource={rivalrySrc}
                          trailingContent={
                            <span className="wisden-tile-faint"> · {t.top_wicket_taker.wickets} wkts</span>
                          }
                        />
                      </div>
                    )}
                    {t.highest_individual && (
                      <div>
                        <span className="wisden-tile-faint">Highest individual: </span>
                        <PlayerLink
                          personId={t.highest_individual.person_id} name={t.highest_individual.name}
                          role="batter" gender={gender}
                          subscriptSource={rivalrySrc}
                          trailingContent={
                            <span className="wisden-tile-faint"> · {t.highest_individual.runs}</span>
                          }
                        />
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
              {
                // Edition column. Single-tournament dossier: just the
                // season (plain text, tournament implied by page scope).
                // Multi-tournament scope (rivalry, ICC Trophies, etc.):
                // "<Tournament> <Season>" as a link to that edition's
                // dossier, since the season alone is ambiguous.
                key: 'season',
                label: tournament ? 'Season' : 'Edition',
                format: (v: string, r) => {
                  if (tournament || !r.tournament) return v
                  return (
                    <SeriesLink
                      tournament={r.tournament}
                      season={r.season}
                      gender={gender}
                      team_type={teamType}
                    >
                      {r.tournament} {r.season}
                    </SeriesLink>
                  ) as unknown as string
                },
              },
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

      {/* ── Participating teams (only meaningful for tournaments) ──
          The section title embeds the tournament + season scope once, so
          per-chip text can stay tight. Each chip splits into two links:
          the country NAME is a TeamLink (all-time — preserves the "team-
          name-as-link always means all-time" convention), and the match
          COUNT links to the scoped view (team at this tournament +
          season window). */}
      {tournament && summary.teams.length > 0 && (() => {
        const season = seasonTag(filters.season_from, filters.season_to)
        const scopeLabel = season
          ? `at ${tournament}, ${season}`
          : `at ${tournament}`
        return (
          <div className="mt-8">
            <h3 className="wisden-section-title">
              Teams {scopeLabel} ({summary.teams.length})
            </h3>
            <div className="flex flex-wrap gap-2">
              {summary.teams.map(t => {
                const scopedQs = new URLSearchParams({ team: t.name })
                scopedQs.set('tournament', tournament)
                if (gender) scopedQs.set('gender', gender)
                if (teamType) scopedQs.set('team_type', teamType)
                if (filters.season_from) scopedQs.set('season_from', filters.season_from)
                if (filters.season_to) scopedQs.set('season_to', filters.season_to)
                return (
                  <span key={t.name} className="wisden-chip">
                    <TeamLink
                      teamName={t.name}
                      compact
                      gender={gender}
                      team_type={teamType}
                    />
                    <span className="wisden-tile-faint"> · </span>
                    <Link
                      to={`/teams?${scopedQs.toString()}`}
                      className="comp-link"
                      title={`${t.name} ${scopeLabel} — ${t.matches} matches`}
                    >
                      {t.matches}
                    </Link>
                  </span>
                )
              })}
            </div>
          </div>
        )
      })()}

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
                  ? (renderBatterPair(r.best_partnership.batter1, r.best_partnership.batter2) as unknown as string)
                  : '-',
              },
              {
                key: 'best_partnership', label: 'Match',
                format: (_v, r) => r.best_partnership
                  ? (renderVsTeams(r.best_partnership.batting_team, r.best_partnership.opponent) as unknown as string)
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
                  renderBatterPair(r.batter1, r.batter2) as unknown as string,
              },
              {
                key: 'batting_team', label: 'Match',
                format: (_v, r: TournamentPartnershipTopEntry) =>
                  renderVsTeams(r.batting_team, r.opponent) as unknown as string,
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
    {
      key: 'champion', label: 'Champion', sortable: true,
      format: (v: string | null) => v ? (
        <Link to={`/teams?team=${encodeURIComponent(v)}`} className="comp-link">{v}</Link>
      ) as unknown as string : '-',
    },
    {
      key: 'runner_up', label: 'Runner-up',
      format: (v: string | null) => v ? (
        <Link to={`/teams?team=${encodeURIComponent(v)}`} className="comp-link">{v}</Link>
      ) as unknown as string : '-',
    },
    {
      key: 'top_scorer', label: 'Top scorer',
      format: (_v, r) => r.top_scorer ? (
        <>
          <Link to={`/batting?player=${encodeURIComponent(r.top_scorer.person_id)}`}
            className="comp-link">{r.top_scorer.name}</Link>
          {` (${r.top_scorer.runs})`}
        </>
      ) as unknown as string : '-',
    },
    {
      key: 'top_wicket_taker', label: 'Top wicket-taker',
      format: (_v, r) => r.top_wicket_taker ? (
        <>
          <Link to={`/bowling?player=${encodeURIComponent(r.top_wicket_taker.person_id)}`}
            className="comp-link">{r.top_wicket_taker.name}</Link>
          {` (${r.top_wicket_taker.wickets})`}
        </>
      ) as unknown as string : '-',
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

/** Per-row subscript source for a leaderboard entry in rivalry mode —
 *  orient (s, b) to the row's own team so a Kohli row in an India-vs-Aus
 *  dossier shows "India vs Australia" and a Smith row shows "Australia vs
 *  India". Outside rivalry mode returns undefined (component falls back
 *  to useFilters, which already has the tournament + season for (e, t)). */
function rowSubscriptSource(opts: {
  filterTeam: string | null | undefined
  filterOpponent: string | null | undefined
  rowTeam?: string | null
}): { team1: string; team2: string } | undefined {
  const { filterTeam, filterOpponent, rowTeam } = opts
  if (!filterTeam || !filterOpponent) return undefined
  if (rowTeam && rowTeam === filterOpponent) {
    return { team1: filterOpponent, team2: filterTeam }
  }
  return { team1: filterTeam, team2: filterOpponent }
}

function BattersTab({
  loading, error, data, refetch, filterTeam, filterOpponent, gender,
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

  const rowSrc = (r: BattingLeaderEntry) =>
    rowSubscriptSource({ filterTeam, filterOpponent, rowTeam: r.team })

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By average (runs / dismissals)</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Batter',
              format: (_v, r) => {
                const src = rowSrc(r)
                return (
                  <PlayerLink
                    personId={r.person_id} name={r.name} role="batter" gender={gender}
                    subscriptSource={src}
                  />
                ) as unknown as string
              },
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
              format: (_v, r) => {
                const src = rowSrc(r)
                return (
                  <PlayerLink
                    personId={r.person_id} name={r.name} role="batter" gender={gender}
                    subscriptSource={src}
                  />
                ) as unknown as string
              },
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
  loading, error, data, refetch, filterTeam, filterOpponent, gender,
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

  const rowSrc = (r: BowlingLeaderEntry) =>
    rowSubscriptSource({ filterTeam, filterOpponent, rowTeam: r.team })

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By strike rate</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Bowler',
              format: (_v, r) => {
                const src = rowSrc(r)
                return (
                  <PlayerLink
                    personId={r.person_id} name={r.name} role="bowler" gender={gender}
                    subscriptSource={src}
                  />
                ) as unknown as string
              },
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
              format: (_v, r) => {
                const src = rowSrc(r)
                return (
                  <PlayerLink
                    personId={r.person_id} name={r.name} role="bowler" gender={gender}
                    subscriptSource={src}
                  />
                ) as unknown as string
              },
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
  loading, error, data, refetch, filterTeam, filterOpponent, gender,
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

  const rowSrc = (r: FieldingLeaderEntry) =>
    rowSubscriptSource({ filterTeam, filterOpponent, rowTeam: r.team })

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
      <div>
        <h3 className="wisden-section-title">By dismissals (all)</h3>
        <DataTable
          columns={[
            {
              key: 'name', label: 'Fielder',
              format: (_v, r) => {
                const src = rowSrc(r)
                return (
                  <PlayerLink
                    personId={r.person_id} name={r.name} role="fielder" gender={gender}
                    subscriptSource={src}
                  />
                ) as unknown as string
              },
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
              format: (_v, r) => {
                const src = rowSrc(r)
                return (
                  <PlayerLink
                    personId={r.person_id} name={r.name} role="fielder" gender={gender}
                    subscriptSource={src}
                  />
                ) as unknown as string
              },
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
                (r.batter1 && r.batter2
                  ? renderBatterPair(r.batter1, r.batter2)
                  : '-') as unknown as string,
            },
            {
              key: 'teams', label: 'Match',
              format: (v: string) => v
                ? (renderVsTeamsFromString(v) as unknown as string)
                : '-',
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
                <Link to={`/bowling?player=${encodeURIComponent(r.person_id)}`}
                  className="comp-link">{r.name}</Link>
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
            {
              key: 'teams', label: 'Teams',
              format: (v: string) => v
                ? (renderVsTeamsFromString(v) as unknown as string)
                : '-',
            },
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
