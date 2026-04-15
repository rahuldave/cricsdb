import { Link } from 'react-router-dom'
import { useFilters } from '../components/FilterBar'
import { useUrlParam, useSetUrlParams } from '../hooks/useUrlState'
import { useFetch } from '../hooks/useFetch'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import PlayerSearch from '../components/PlayerSearch'
import TeamSearch from '../components/TeamSearch'
import StatCard from '../components/StatCard'
import DataTable, { type Column } from '../components/DataTable'
import BarChart from '../components/charts/BarChart'
import DonutChart from '../components/charts/DonutChart'
import { WISDEN_PHASES } from '../components/charts/palette'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import TournamentDossier from '../components/tournaments/TournamentDossier'
import { getHeadToHead, getTournamentsLanding } from '../api'
import type {
  PlayerSearchResult, HeadToHeadResponse, HeadToHeadMatch,
  TournamentsLanding, RivalryEntry,
} from '../types'

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
  const [batterId, setBatterId] = useUrlParam('batter')
  const [bowlerId, setBowlerId] = useUrlParam('bowler')

  const handleBatter = (p: PlayerSearchResult) => setBatterId(p.id)
  const handleBowler = (p: PlayerSearchResult) => setBowlerId(p.id)

  const enabled = !!(batterId && bowlerId)
  const { data, loading, error, refetch } = useFetch<HeadToHeadResponse | null>(
    () => enabled
      ? getHeadToHead(batterId, bowlerId, filters)
      : Promise.resolve(null),
    [batterId, bowlerId, filters.gender, filters.team_type, filters.tournament,
     filters.season_from, filters.season_to],
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
    { key: 'tournament', label: 'Tournament' },
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

      {!enabled && (
        <div className="wisden-empty">Select both a batter and bowler to view head-to-head stats</div>
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
            {' '}<span style={{ fontStyle: 'italic', color: 'var(--accent)', fontWeight: 400 }}>v</span>{' '}
            <Link to={`/bowling?player=${encodeURIComponent(bowlerId)}`} className="comp-link" style={{ fontSize: 'inherit', fontWeight: 'inherit' }}>
              {data.bowler.name}
            </Link>
          </h2>

          <div className="wisden-statrow cols-5">
            <StatCard label="Balls" value={data.summary.balls} />
            <StatCard label="Runs" value={data.summary.runs} />
            <StatCard label="Outs" value={data.summary.dismissals} />
            <StatCard label="Average" value={fmt(data.summary.average)} />
            <StatCard label="Strike Rate" value={fmt(data.summary.strike_rate)} />
          </div>
          <div className="wisden-statrow">
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

  const pickPair = (a: string, b: string, gender?: string) => {
    const updates: Record<string, string> = { team1: a, team2: b, mode: 'team' }
    if (gender) updates.gender = gender
    if (!updates.team_type) updates.team_type = 'international'
    setUrlParams(updates)
  }

  return (
    <>
      <div className="flex gap-6 items-start mb-8">
        <div className="flex-1">
          <label className="wisden-h2h-label">Team 1</label>
          <TeamSearch
            initialValue={team1}
            placeholder="Search team…"
            onSelect={onChangeTeam1}
          />
        </div>
        <span className="wisden-h2h-vs">v</span>
        <div className="flex-1">
          <label className="wisden-h2h-label">Team 2</label>
          <TeamSearch
            initialValue={team2}
            placeholder="Search team…"
            onSelect={onChangeTeam2}
          />
        </div>
      </div>

      {enabled ? (
        <TournamentDossier
          tournament={null}
          filterTeam={team1}
          filterOpponent={team2}
        />
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
                        </div>
                        <div className="wisden-tile-sub">
                          {r.matches} bilateral · {r.team1_wins}–{r.team2_wins}
                        </div>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}
    </>
  )
}
