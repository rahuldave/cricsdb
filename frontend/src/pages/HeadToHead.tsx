import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import PlayerSearch from '../components/PlayerSearch'
import TeamSearch from '../components/TeamSearch'
import FlagBadge from '../components/FlagBadge'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import DonutChart from '../components/charts/DonutChart'
import { WISDEN_PHASES } from '../components/charts/palette'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import TournamentDossier from '../components/tournaments/TournamentDossier'
import { ScopeContext } from '../components/scopeLinks'
import { getHeadToHead, getTournamentsLanding } from '../api'
import type {
  PlayerSearchResult, HeadToHeadResponse, HeadToHeadMatch,
  TournamentsLanding, RivalryEntry, ClubRivalryEntry,
} from '../types'

// Curated player matchups for the Player-vs-Player canned suggestions.
// These are the ones we link from the Home page already, plus a few more.
// Hardcoded since "popular matchup" isn't a stat we compute.
// Curated list — bias toward cross-country matchups since those ARE
// the head-to-heads users usually come looking for (a domestic IPL
// pair is one click away via PlayerSearch). Mixed-country pairs first.
const POPULAR_MATCHUPS_MEN: { batter: string; bowler: string; batterName: string; bowlerName: string }[] = [
  { batter: 'c4487b84', bowler: '462411b3', batterName: 'AB de Villiers', bowlerName: 'JJ Bumrah' },     // SA v IND
  { batter: '8a75e999', bowler: '462411b3', batterName: 'Babar Azam',     bowlerName: 'JJ Bumrah' },     // PAK v IND
  { batter: '99b75528', bowler: '45a7e761', batterName: 'JC Buttler',     bowlerName: 'Shaheen Shah Afridi' }, // ENG v PAK
  { batter: '740742ef', bowler: 'a818c1be', batterName: 'RG Sharma',      bowlerName: 'TA Boult' },      // IND v NZ
  { batter: 'ba607b88', bowler: '462411b3', batterName: 'V Kohli',        bowlerName: 'JJ Bumrah' },     // IND (club-only meetings)
]
const POPULAR_MATCHUPS_WOMEN: { batter: string; bowler: string; batterName: string; bowlerName: string }[] = [
  { batter: 'd32cf49a', bowler: '63e3b6b3', batterName: 'HK Matthews', bowlerName: 'M Kapp' },
  { batter: '5d2eda89', bowler: 'be150fc8', batterName: 'S Mandhana',  bowlerName: 'EA Perry' },
  { batter: '52d1dbc8', bowler: 'be150fc8', batterName: 'BL Mooney',   bowlerName: 'EA Perry' },
]

const fmt = (v: number | null | undefined, d = 2) => v == null ? '-' : v.toFixed(d)

type Mode = 'player' | 'team'

export default function HeadToHead() {
  const [mode] = useUrlParam('mode', 'player') as [Mode, (v: Mode) => void]
  const setUrlParams = useSetUrlParams()
  // Default mode: if team1+team2 present without explicit mode, pick team
  const [team1Url] = useUrlParam('team1')
  const [team2Url] = useUrlParam('team2')
  const effectiveMode: Mode = (mode === 'team' || (team1Url && team2Url)) ? 'team' : 'player'

  return (
    <div className="max-w-6xl mx-auto">
      {/* Mode picker */}
      <div className="wisden-tabs mb-6">
        <button
          type="button"
          className={`wisden-tab${effectiveMode === 'player' ? ' is-active' : ''}`}
          onClick={() => setUrlParams({ mode: 'player', team1: '', team2: '' })}
        >Player vs Player</button>
        <button
          type="button"
          className={`wisden-tab${effectiveMode === 'team' ? ' is-active' : ''}`}
          onClick={() => setUrlParams({ mode: 'team', batter: '', bowler: '' })}
        >Team vs Team</button>
      </div>

      {effectiveMode === 'player' ? <PlayerVsPlayer /> : <TeamVsTeam />}
    </div>
  )
}

// ─── Player vs Player (existing flow) ────────────────────────────────

function PlayerVsPlayer() {
  const filters = useFilters()
  const setUrlParams = useSetUrlParams()
  const [batterId, setBatterId] = useUrlParam('batter')
  const [bowlerId, setBowlerId] = useUrlParam('bowler')
  const [seriesType, setSeriesType] = useUrlParam('series_type', 'all')

  const handleBatter = (p: PlayerSearchResult) => setBatterId(p.id)
  const handleBowler = (p: PlayerSearchResult) => setBowlerId(p.id)

  // If the active series_type becomes invalid after a FilterBar change
  // (e.g. pick Club → 'bilateral' is no longer offered), reset to 'all'
  // via replace — the stale state wasn't user-chosen, don't add history.
  useEffect(() => {
    if (!seriesType || seriesType === 'all') return
    const isClub = filters.team_type === 'club'
    const isIntl = filters.team_type === 'international'
    const valid =
      (seriesType === 'bilateral' && !isClub)
      || (seriesType === 'icc' && !isClub)
      || (seriesType === 'club' && !isIntl)
    if (!valid) setSeriesType('', { replace: true })
  }, [seriesType, filters.team_type])

  const enabled = !!(batterId && bowlerId)
  const { data, loading, error, refetch } = useFetch<HeadToHeadResponse | null>(
    () => enabled
      ? getHeadToHead(batterId, bowlerId, {
          ...filters,
          series_type: seriesType === 'all' ? undefined : seriesType,
        })
      : Promise.resolve(null),
    [batterId, bowlerId, seriesType, filters.gender, filters.team_type, filters.tournament,
     filters.season_from, filters.season_to, filters.filter_venue],
  )
  useDocumentTitle(
    data ? `${data.batter.name} v ${data.bowler.name}` : enabled ? null : 'Head to Head'
  )

  const matchColumns: Column<HeadToHeadMatch>[] = [
    { key: 'date', label: 'Date', sortable: true, format: (v: any, r: any) => (
      <Link
        to={`/matches/${r.match_id}?highlight_batter=${encodeURIComponent(batterId || '')}&highlight_bowler=${encodeURIComponent(bowlerId || '')}`}
        className="comp-link"
        onClick={e => e.stopPropagation()}>{v || '-'}</Link>
    ) as unknown as string },
    { key: 'tournament', label: 'Tournament', format: (v: any) => v ? (
      <Link to={`/series?tournament=${encodeURIComponent(v)}`}
        className="comp-link" onClick={e => e.stopPropagation()}>{v}</Link>
    ) as unknown as string : '-' },
    { key: 'venue', label: 'Venue' },
    { key: 'balls', label: 'Balls', sortable: true },
    { key: 'runs', label: 'Runs', sortable: true },
    { key: 'fours', label: '4s' },
    { key: 'sixes', label: '6s' },
    { key: 'how_out', label: 'Out?', format: (_: any, r: any) => r.dismissed ? (r.how_out || 'yes') : '-' },
  ]

  return (
    <>
      <div className="flex gap-6 items-start mb-8">
        <div className="flex-1">
          <label className="wisden-h2h-label">Batter</label>
          <PlayerSearch role="batter" onSelect={handleBatter} placeholder="Search batter…" />
        </div>
        <span className="wisden-h2h-vs">v</span>
        <div className="flex-1">
          <label className="wisden-h2h-label">Bowler</label>
          <PlayerSearch role="bowler" onSelect={handleBowler} placeholder="Search bowler…" />
        </div>
      </div>

      {/* Series-type pill — four mutually-exclusive categories. The pill
          only renders options that produce DIFFERENT results:
          - Type=Club: all four options return identical rows, so render
            a small "Showing: Club tournaments" caption instead.
          - Type=International: Club option hidden; "All meetings" label
            becomes "All international" since that's the truthful scope.
          - No Type filter: all four options shown.
          If the active option becomes invalid after a FilterBar change,
          auto-reset to 'all' so the user never sees a stale highlight. */}
      {enabled && (() => {
        const isClub = filters.team_type === 'club'
        const isIntl = filters.team_type === 'international'
        const opts = (['all', 'bilateral', 'icc', 'club'] as const).filter(s =>
          s === 'all'
            || (s === 'bilateral' && !isClub)
            || (s === 'icc' && !isClub)
            || (s === 'club' && !isIntl))
        // Invalid-series auto-reset moved to the useEffect below —
        // setting URL state during render pushed a history entry every
        // time it fired (after we flipped the hook default to push).
        if (isClub) {
          // Pill collapses to a read-only caption — every option would
          // narrow to the same rows the FilterBar is already showing.
          return (
            <div className="mb-4 wisden-tab-help">
              Showing: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Club tournaments</span>
            </div>
          )
        }
        const allLabel = isIntl ? 'All international' : 'All meetings'
        return (
          <div className="mb-4 flex items-center gap-2 wisden-tab-help flex-wrap">
            <span>Show:</span>
            {opts.map(s => (
              <button
                key={s}
                type="button"
                className="wisden-clear"
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

      {!enabled && (
        <>
          <div className="wisden-empty">Select both a batter and bowler — or pick a popular matchup below</div>
          <div className="mt-8">
            <h3 className="wisden-section-title">Popular matchups</h3>
            <div className="wisden-tab-help mb-2">Men's</div>
            <div className="wisden-tile-grid">
              {POPULAR_MATCHUPS_MEN.map(m => (
                <button
                  key={`m-${m.batter}-${m.bowler}`}
                  type="button"
                  className="wisden-tile"
                  onClick={() => setUrlParams({
                    batter: m.batter, bowler: m.bowler, mode: 'player', gender: 'male',
                  })}
                >
                  <div className="wisden-tile-title">
                    {m.batterName} <span className="wisden-tile-vs">v</span> {m.bowlerName}
                    <span className="wisden-tile-faint" style={{ fontSize: '0.78em' }}> men's</span>
                  </div>
                </button>
              ))}
            </div>
            <div className="wisden-tab-help mt-6 mb-2">Women's</div>
            <div className="wisden-tile-grid">
              {POPULAR_MATCHUPS_WOMEN.map(m => (
                <button
                  key={`w-${m.batter}-${m.bowler}`}
                  type="button"
                  className="wisden-tile"
                  onClick={() => setUrlParams({
                    batter: m.batter, bowler: m.bowler, mode: 'player', gender: 'female',
                  })}
                >
                  <div className="wisden-tile-title">
                    {m.batterName} <span className="wisden-tile-vs">v</span> {m.bowlerName}
                    <span className="wisden-tile-faint" style={{ fontSize: '0.78em' }}> women's</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      {enabled && loading && <Spinner label="Loading head-to-head…" size="lg" />}

      {enabled && error && (
        <ErrorBanner message={`Could not load head-to-head: ${error}`} onRetry={refetch} />
      )}

      {enabled && data && !loading && !error && (
        <>
          <h2 className="wisden-page-title">
            <Link to={`/batting?player=${encodeURIComponent(batterId)}`} className="comp-link" style={{ fontSize: 'inherit', fontWeight: 'inherit' }}>
              {data.batter.name}
            </Link>
            {data.batter.nationalities?.[0] && (
              <span style={{ marginLeft: '0.35rem' }}>
                <FlagBadge
                  team={data.batter.nationalities[0].team}
                  gender={data.batter.nationalities[0].gender}
                  size="sm"
                  linkTo
                />
              </span>
            )}
            {' '}<span style={{ fontStyle: 'italic', color: 'var(--accent)', fontWeight: 400 }}>v</span>{' '}
            <Link to={`/bowling?player=${encodeURIComponent(bowlerId)}`} className="comp-link" style={{ fontSize: 'inherit', fontWeight: 'inherit' }}>
              {data.bowler.name}
            </Link>
            {data.bowler.nationalities?.[0] && (
              <span style={{ marginLeft: '0.35rem' }}>
                <FlagBadge
                  team={data.bowler.nationalities[0].team}
                  gender={data.bowler.nationalities[0].gender}
                  size="sm"
                  linkTo
                />
              </span>
            )}
          </h2>

          <div className="wisden-statrow cols-5">
            <StatCard label="Matches" value={data.summary.matches} />
            <StatCard label="Balls" value={data.summary.balls} />
            <StatCard label="Runs" value={data.summary.runs} />
            <StatCard label="Outs" value={data.summary.dismissals} />
            <StatCard label="Average" value={fmt(data.summary.average)} />
          </div>
          <div className="wisden-statrow cols-5">
            <StatCard label="Strike Rate" value={fmt(data.summary.strike_rate)} />
            <StatCard label="Fours" value={data.summary.fours} />
            <StatCard label="Sixes" value={data.summary.sixes} />
            <StatCard label="Dots" value={data.summary.dots} />
            <StatCard label="Dot %" value={data.summary.dot_pct != null ? `${data.summary.dot_pct}%` : '-'} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {data.by_phase.length > 0 && (
              <BarChart
                data={data.by_phase}
                categoryAccessor="phase" valueAccessor={(d: Record<string, any>) => (d.strike_rate as number) ?? 0}
                title="Strike Rate by Phase" categoryLabel="Phase" valueLabel="SR"
                height={280} colorScheme={WISDEN_PHASES} />
            )}
            {Object.keys(data.dismissal_kinds).length > 0 && (
              <DonutChart
                data={Object.entries(data.dismissal_kinds).map(([label, value]) => ({ label, value }))}
                categoryAccessor="label" valueAccessor="value"
                title={`Dismissals (${data.summary.dismissals})`} width={300} height={280} />
            )}
          </div>

          {data.by_season.length > 0 && (
            <div className="mb-8">
              <BarChart
                data={data.by_season.filter(s => s.strike_rate != null)}
                categoryAccessor="season" valueAccessor={(d: Record<string, any>) => d.strike_rate ?? 0}
                title="Strike Rate by Season" categoryLabel="Season" valueLabel="SR"
                height={300} />
            </div>
          )}

          {data.by_over.length > 0 && (
            <div className="mb-8">
              <BarChart
                data={data.by_over.filter(o => o.balls > 0).map(o => ({ ...o, over: `${o.over_number}` }))}
                categoryAccessor="over"
                valueAccessor="runs"
                title="Runs by Over" categoryLabel="Over" valueLabel="Runs"
                height={300} />
            </div>
          )}

          <div>
            <div className="section-head"><span className="section-label">Match by Match</span></div>
            <div className="rule" />
            <DataTable columns={matchColumns} data={data.by_match} />
          </div>
        </>
      )}
    </>
  )
}

// ─── Team vs Team (new) ──────────────────────────────────────────────

function TeamVsTeam() {
  const [team1, setTeam1] = useUrlParam('team1')
  const [team2, setTeam2] = useUrlParam('team2')
  const enabled = !!(team1 && team2)

  return (
    <TeamVsTeamPicker
      team1={team1} team2={team2}
      onChangeTeam1={setTeam1}
      onChangeTeam2={setTeam2}
      showSuggestions={!enabled}
    />
  )
}

function TeamVsTeamPicker({
  team1, team2, onChangeTeam1, onChangeTeam2, showSuggestions,
}: {
  team1: string
  team2: string
  onChangeTeam1: (v: string) => void
  onChangeTeam2: (v: string) => void
  showSuggestions?: boolean
}) {
  const setUrlParams = useSetUrlParams()
  const enabled = !!(team1 && team2)

  // Common matchups grid — fetched only when picker is shown.
  const suggestionsFetch = useFetch<TournamentsLanding | null>(
    () => showSuggestions ? getTournamentsLanding({}) : Promise.resolve(null),
    [showSuggestions],
  )

  const pickPair = (
    a: string, b: string, gender?: string,
    teamType: 'international' | 'club' = 'international',
  ) => {
    const updates: Record<string, string> = {
      team1: a, team2: b, mode: 'team', team_type: teamType,
    }
    if (gender) updates.gender = gender
    setUrlParams(updates)
  }

  return (
    <>
      <div className="flex gap-6 items-start mb-8">
        <div className="flex-1">
          <label className="wisden-h2h-label">Team 1</label>
          <TeamSearch
            value={team1}
            placeholder="Search team…"
            onSelect={onChangeTeam1}
          />
        </div>
        <span className="wisden-h2h-vs">v</span>
        <div className="flex-1">
          <label className="wisden-h2h-label">Team 2</label>
          <TeamSearch
            value={team2}
            placeholder="Search team…"
            onSelect={onChangeTeam2}
          />
        </div>
      </div>

      {enabled ? (
        // Promote team1/team2 path params → filter_team/filter_opponent
        // pinning so PlayerLink/TeamLink inside the dossier carry the
        // rivalry through their (s)/(b) letter links. The dossier itself
        // reads the same pair via props; this is purely for link-building.
        <ScopeContext.Provider value={{ filter_team: team1, filter_opponent: team2 }}>
          <TournamentDossier
            tournament={null}
            filterTeam={team1}
            filterOpponent={team2}
          />
        </ScopeContext.Provider>
      ) : (
        <>
          <div className="wisden-empty">
            Select two teams to see all their meetings — bilateral series and tournament matches combined.
          </div>

          {showSuggestions && (
            <div className="mt-8">
              <h3 className="wisden-section-title">Or browse a common matchup</h3>
              {suggestionsFetch.loading && <Spinner label="Loading suggestions…" />}
              {suggestionsFetch.data && (
                <>
                  <div className="wisden-tab-help mb-2">Men's</div>
                  <div className="wisden-tile-grid">
                    {suggestionsFetch.data.international.bilateral_rivalries.men.top.slice(0, 12).map((r: RivalryEntry) => (
                      <button
                        key={`m-${r.team1}|${r.team2}`}
                        type="button"
                        className="wisden-tile"
                        onClick={() => pickPair(r.team1, r.team2, 'male')}
                      >
                        <div className="wisden-tile-title">
                          {r.team1} <span className="wisden-tile-vs">v</span> {r.team2}
                          <span className="wisden-tile-faint" style={{ fontSize: '0.78em' }}> men's</span>
                        </div>
                        <div className="wisden-tile-sub">
                          {r.matches} bilateral · {r.team1_wins}–{r.team2_wins}
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className="wisden-tab-help mt-6 mb-2">Women's</div>
                  <div className="wisden-tile-grid">
                    {suggestionsFetch.data.international.bilateral_rivalries.women.top.slice(0, 12).map((r: RivalryEntry) => (
                      <button
                        key={`w-${r.team1}|${r.team2}`}
                        type="button"
                        className="wisden-tile"
                        onClick={() => pickPair(r.team1, r.team2, 'female')}
                      >
                        <div className="wisden-tile-title">
                          {r.team1} <span className="wisden-tile-vs">v</span> {r.team2}
                          <span className="wisden-tile-faint" style={{ fontSize: '0.78em' }}> women's</span>
                        </div>
                        <div className="wisden-tile-sub">
                          {r.matches} bilateral · {r.team1_wins}–{r.team2_wins}
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* ── Club rivalries (e.g. CSK v MI in IPL) ── */}
                  {suggestionsFetch.data.club.rivalries.men.length > 0 && (
                    <>
                      <div className="wisden-tab-help mt-6 mb-2">Club — Men's</div>
                      <div className="wisden-tile-grid">
                        {suggestionsFetch.data.club.rivalries.men.map((r: ClubRivalryEntry) => (
                          <button
                            key={`cm-${r.team1}|${r.team2}`}
                            type="button"
                            className="wisden-tile"
                            onClick={() => pickPair(r.team1, r.team2, 'male', 'club')}
                          >
                            <div className="wisden-tile-title">
                              {r.team1} <span className="wisden-tile-vs">v</span> {r.team2}
                            </div>
                            <div className="wisden-tile-sub">
                              {r.matches} matches · {r.team1_wins}–{r.team2_wins}
                              <span className="wisden-tile-faint"> · {r.tournament}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                  {suggestionsFetch.data.club.rivalries.women.length > 0 && (
                    <>
                      <div className="wisden-tab-help mt-6 mb-2">Club — Women's</div>
                      <div className="wisden-tile-grid">
                        {suggestionsFetch.data.club.rivalries.women.map((r: ClubRivalryEntry) => (
                          <button
                            key={`cw-${r.team1}|${r.team2}`}
                            type="button"
                            className="wisden-tile"
                            onClick={() => pickPair(r.team1, r.team2, 'female', 'club')}
                          >
                            <div className="wisden-tile-title">
                              {r.team1} <span className="wisden-tile-vs">v</span> {r.team2}
                            </div>
                            <div className="wisden-tile-sub">
                              {r.matches} matches · {r.team1_wins}–{r.team2_wins}
                              <span className="wisden-tile-faint"> · {r.tournament}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}
    </>
  )
}
