import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../../hooks/useFilters'
import { useFetch } from '../../hooks/useFetch'
import { getTournamentsLanding, getTournamentOtherRivalries } from '../../api'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import SeriesLink from '../SeriesLink'
import TeamLink from '../TeamLink'

/** Build a /teams?team=X URL with whatever scope params are non-empty.
 *  Used on tile lines where natural-language phrasing puts the scope on
 *  the team NAME (e.g. "Winner: India" reads as "India won this edition"
 *  — the India link should land on India-at-this-edition, not all-time).
 *  TeamLink's contract is the opposite (name = all-time); these inline
 *  usages are intentional exceptions. */
interface TeamScope {
  team: string
  gender?: string | null
  team_type?: string | null
  tournament?: string | null
  season_from?: string | null
  season_to?: string | null
  filter_team?: string | null
  filter_opponent?: string | null
  series_type?: string | null
}
function teamUrl(s: TeamScope): string {
  const qs = new URLSearchParams()
  qs.set('team', s.team)
  if (s.gender) qs.set('gender', s.gender)
  if (s.team_type) qs.set('team_type', s.team_type)
  if (s.tournament) qs.set('tournament', s.tournament)
  if (s.season_from) qs.set('season_from', s.season_from)
  if (s.season_to) qs.set('season_to', s.season_to)
  if (s.filter_team) qs.set('filter_team', s.filter_team)
  if (s.filter_opponent) qs.set('filter_opponent', s.filter_opponent)
  if (s.series_type && s.series_type !== 'all') qs.set('series_type', s.series_type)
  return `/teams?${qs.toString()}`
}
import type {
  TournamentsLanding as TLandingData,
  TournamentLandingEntry,
  RivalryEntry,
} from '../../types'

/** Pass-through scope fields common to every landing link. Used by the
 *  stretched primary link on each tile. */
interface AmbientScope {
  gender?: string
  team_type?: string
  season_from?: string
  season_to?: string
  filter_venue?: string
}

function ambientFromFilters(filters: ReturnType<typeof useFilters>): AmbientScope {
  return {
    gender: filters.gender || undefined,
    team_type: filters.team_type || undefined,
    season_from: filters.season_from || undefined,
    season_to: filters.season_to || undefined,
    filter_venue: filters.filter_venue || undefined,
  }
}

function TournamentTile({
  entry, ambient,
}: { entry: TournamentLandingEntry; ambient: AmbientScope }) {
  // Tile-implicit gender/team_type wins over ambient — "T20 World Cup
  // (Men)" never matches a cricsheet event_name for FilterBar
  // auto-narrow, so we pass them explicitly on every link URL.
  const rowGender = entry.gender || ambient.gender
  const rowTeamType = entry.team_type || ambient.team_type
  return (
    <div className="wisden-tile tile-wrapper">
      <SeriesLink
        tournament={entry.canonical}
        gender={rowGender}
        team_type={rowTeamType}
        season_from={ambient.season_from}
        season_to={ambient.season_to}
        filter_venue={ambient.filter_venue}
        className="tile-stretched"
        title={`All editions of ${entry.canonical}`}
      >
        {entry.canonical}
      </SeriesLink>
      <div className="wisden-tile-title">{entry.canonical}</div>
      <div className="wisden-tile-sub">
        {entry.editions} {entry.editions === 1 ? 'edition' : 'editions'}
        {' · '}
        {entry.matches.toLocaleString()} {entry.matches === 1 ? 'match' : 'matches'}
      </div>
      {entry.most_titles && (
        <div className="wisden-tile-line">
          Most titles:{' '}
          <TeamLink
            teamName={entry.most_titles.team}
            compact
            gender={rowGender ?? null}
            team_type={rowTeamType ?? null}
          />
          {entry.most_titles.titles > 1 && (
            <>
              {' ('}
              <Link
                to={teamUrl({
                  team: entry.most_titles.team,
                  gender: rowGender,
                  team_type: rowTeamType,
                  tournament: entry.canonical,
                })}
                className="comp-link"
                title={`${entry.most_titles.team} at ${entry.canonical}`}
              >
                {entry.most_titles.titles}
              </Link>
              {')'}
            </>
          )}
        </div>
      )}
      {entry.latest_edition && (
        <>
          <div className="wisden-tile-line">
            Latest:{' '}
            <SeriesLink
              tournament={entry.canonical}
              season={entry.latest_edition.season}
              gender={rowGender}
              team_type={rowTeamType}
              filter_venue={ambient.filter_venue}
              title={`${entry.canonical}, ${entry.latest_edition.season}`}
            >
              {entry.latest_edition.season}
            </SeriesLink>
          </div>
          {entry.latest_edition.champion && (
            <div className="wisden-tile-line">
              <Link
                to={teamUrl({
                  team: entry.latest_edition.champion,
                  gender: rowGender,
                  team_type: rowTeamType,
                  tournament: entry.canonical,
                  season_from: entry.latest_edition.season,
                  season_to: entry.latest_edition.season,
                })}
                className="comp-link"
                title={`${entry.latest_edition.champion} at ${entry.canonical}, ${entry.latest_edition.season}`}
              >
                Winner: {entry.latest_edition.champion}
              </Link>
              <span className="scope-phrases-inline">
                {' '}
                <Link
                  to={teamUrl({
                    team: entry.latest_edition.champion,
                    gender: rowGender,
                    team_type: rowTeamType,
                  })}
                  className="comp-link scope-phrase"
                  title={`${entry.latest_edition.champion}, all-time`}
                >
                  all-time
                </Link>
              </span>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function RivalryTile({
  entry, ambient, gender,
}: { entry: RivalryEntry; ambient: AmbientScope; gender: 'male' | 'female' }) {
  // Rivalry tiles show an all-time bilateral pair; tile click opens the
  // rivalry dossier on `all` (bilateral + ICC) so the user can see the
  // full picture and narrow via the series-type pill.
  const genderLabel = gender === 'female' ? "women's" : "men's"
  const latest = entry.latest_match
  // Bilateral when event_name was null on the server side.
  const latestIsBilateral = !!latest && latest.tournament == null
  return (
    <div className="wisden-tile tile-wrapper">
      <SeriesLink
        team1={entry.team1}
        team2={entry.team2}
        seriesType="all"
        gender={gender}
        team_type="international"
        season_from={ambient.season_from}
        season_to={ambient.season_to}
        filter_venue={ambient.filter_venue}
        className="tile-stretched"
        title={`${entry.team1} vs ${entry.team2} — all meetings`}
      >
        {`${entry.team1} v ${entry.team2}`}
      </SeriesLink>
      <div className="wisden-tile-title">
        {entry.team1} <span className="wisden-tile-vs">v</span> {entry.team2}
        <span className="wisden-tile-faint" style={{ fontSize: '0.78em' }}> {genderLabel}</span>
      </div>
      <div className="wisden-tile-sub">
        {entry.matches} {entry.matches === 1 ? 'match' : 'matches'}
      </div>
      <div className="wisden-tile-line">
        {entry.team1_wins}–{entry.team2_wins}
        {(entry.ties || entry.no_result) ? (
          <span className="wisden-tile-faint">
            {entry.ties ? ` · ${entry.ties} tie${entry.ties > 1 ? 's' : ''}` : ''}
            {entry.no_result ? ` · ${entry.no_result} NR` : ''}
          </span>
        ) : null}
      </div>
      {latest && (
        <>
          <div className="wisden-tile-line">
            Latest:{' '}
            <SeriesLink
              tournament={latestIsBilateral ? null : latest.tournament}
              season={latest.season}
              seriesType={latestIsBilateral ? 'bilateral' : 'all'}
              team1={entry.team1}
              team2={entry.team2}
              gender={gender}
              team_type="international"
            >
              {latestIsBilateral
                ? `${latest.season} bilateral`
                : `${latest.tournament} ${latest.season}`}
            </SeriesLink>
          </div>
          {latest.winner && (() => {
            const opp = latest.winner === entry.team1 ? entry.team2 : entry.team1
            const scopedHref = teamUrl({
              team: latest.winner,
              gender,
              team_type: 'international',
              tournament: latestIsBilateral ? null : latest.tournament,
              season_from: latest.season,
              season_to: latest.season,
              filter_opponent: opp,
              series_type: latestIsBilateral ? 'bilateral' : undefined,
            })
            const scopedDesc = latestIsBilateral
              ? `${latest.winner} vs ${opp}, ${latest.season} bilateral`
              : `${latest.winner} at ${latest.tournament}, ${latest.season} vs ${opp}`
            return (
              <div className="wisden-tile-line">
                <Link to={scopedHref} className="comp-link" title={scopedDesc}>
                  Winner: {latest.winner}
                </Link>
                <span className="scope-phrases-inline">
                  {' '}
                  <Link
                    to={teamUrl({
                      team: latest.winner,
                      gender,
                      team_type: 'international',
                    })}
                    className="comp-link scope-phrase"
                    title={`${latest.winner}, all-time`}
                  >
                    all-time
                  </Link>
                </span>
              </div>
            )
          })()}
        </>
      )}
    </div>
  )
}

function Section({
  title, tiles, emptyLabel, ambient,
}: {
  title: string
  tiles: TournamentLandingEntry[]
  emptyLabel?: string
  ambient: AmbientScope
}) {
  if (!tiles.length) {
    if (!emptyLabel) return null
    return (
      <div className="wisden-landing-section">
        <h3 className="wisden-section-title">{title}</h3>
        <div className="wisden-tab-help">{emptyLabel}</div>
      </div>
    )
  }
  return (
    <div className="wisden-landing-section">
      <h3 className="wisden-section-title">{title}</h3>
      <div className="wisden-tile-grid">
        {tiles.map(e => (
          <TournamentTile key={e.canonical} entry={e} ambient={ambient} />
        ))}
      </div>
    </div>
  )
}

function RivalryGrid({
  title, top, gender, ambient,
}: {
  title: string
  top: RivalryEntry[]
  gender: 'male' | 'female'
  ambient: AmbientScope
}) {
  if (!top.length) return null
  return (
    <div className="wisden-landing-section">
      <h3 className="wisden-section-title">{title}</h3>
      <div className="wisden-tile-grid">
        {top.map(e => (
          <RivalryTile
            key={`${gender}-${e.team1}|${e.team2}`}
            entry={e}
            ambient={ambient}
            gender={gender}
          />
        ))}
      </div>
    </div>
  )
}

export default function TournamentsLanding() {
  const filters = useFilters()
  const ambient = ambientFromFilters(filters)

  const { data, loading, error, refetch } = useFetch<TLandingData>(
    () => getTournamentsLanding(filters),
    [filters.gender, filters.team_type, filters.tournament,
     filters.season_from, filters.season_to, filters.filter_venue],
  )

  const [showOthersMen, setShowOthersMen] = useState(false)
  const [showOthersWomen, setShowOthersWomen] = useState(false)
  const [showOtherIntl, setShowOtherIntl] = useState(false)
  const othersMenFetch = useFetch<{ rivalries: RivalryEntry[]; threshold: number } | null>(
    () => showOthersMen
      ? getTournamentOtherRivalries({ ...filters, gender: 'male' })
      : Promise.resolve(null),
    [showOthersMen, filters.team_type, filters.tournament,
     filters.season_from, filters.season_to, filters.filter_venue],
  )
  const othersWomenFetch = useFetch<{ rivalries: RivalryEntry[]; threshold: number } | null>(
    () => showOthersWomen
      ? getTournamentOtherRivalries({ ...filters, gender: 'female' })
      : Promise.resolve(null),
    [showOthersWomen, filters.team_type, filters.tournament,
     filters.season_from, filters.season_to, filters.filter_venue],
  )

  if (loading) return <Spinner label="Loading tournaments…" size="lg" />
  if (error) return <ErrorBanner message={`Could not load tournaments: ${error}`} onRetry={refetch} />
  if (!data) return null

  const intlEvents = data.international.icc_events
  const otherIntl = data.international.other_international
  const rivalries = data.international.bilateral_rivalries
  const clubFranchise = data.club.franchise_leagues
  const clubDomestic = data.club.domestic_leagues
  const clubWomen = data.club.women_franchise
  const clubOther = data.club.other

  const showInternational = filters.team_type !== 'club'
  const showClub = filters.team_type !== 'international'

  return (
    <div>
      <h2 className="wisden-page-title">Series</h2>
      <div className="wisden-page-subtitle">
        Tournaments and bilateral rivalries — filter to narrow the scope.
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-6">
        {/* ── Left column — International ── */}
        {showInternational && (
          <div>
            <Section
              title="International events"
              tiles={intlEvents}
              ambient={ambient}
              emptyLabel="No international events in this filter scope."
            />

            {/* ── Men's bilateral rivalries ── */}
            {rivalries.men.top.length > 0 && (
              <RivalryGrid
                title={`Men's bilateral rivalries (${rivalries.men.top.length})`}
                top={rivalries.men.top}
                gender="male"
                ambient={ambient}
              />
            )}
            {rivalries.men.other_count > 0 && (
              <div className="mt-3 mb-4">
                {!showOthersMen ? (
                  <button
                    type="button"
                    className="wisden-clear"
                    onClick={() => setShowOthersMen(true)}
                  >
                    ▸ Show {rivalries.men.other_count} other men's rivalries
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      className="wisden-clear"
                      onClick={() => setShowOthersMen(false)}
                    >
                      ▾ Hide other men's rivalries
                    </button>
                    {othersMenFetch.loading && <Spinner label="Loading…" />}
                    {othersMenFetch.data?.rivalries?.length ? (
                      <div className="wisden-tile-grid mt-2">
                        {othersMenFetch.data.rivalries.map(e => (
                          <RivalryTile
                            key={`om-${e.team1}|${e.team2}`}
                            entry={e}
                            ambient={ambient}
                            gender="male"
                          />
                        ))}
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            )}

            {/* ── Women's bilateral rivalries ── */}
            {rivalries.women.top.length > 0 && (
              <RivalryGrid
                title={`Women's bilateral rivalries (${rivalries.women.top.length})`}
                top={rivalries.women.top}
                gender="female"
                ambient={ambient}
              />
            )}
            {rivalries.women.other_count > 0 && (
              <div className="mt-3 mb-4">
                {!showOthersWomen ? (
                  <button
                    type="button"
                    className="wisden-clear"
                    onClick={() => setShowOthersWomen(true)}
                  >
                    ▸ Show {rivalries.women.other_count} other women's rivalries
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      className="wisden-clear"
                      onClick={() => setShowOthersWomen(false)}
                    >
                      ▾ Hide other women's rivalries
                    </button>
                    {othersWomenFetch.loading && <Spinner label="Loading…" />}
                    {othersWomenFetch.data?.rivalries?.length ? (
                      <div className="wisden-tile-grid mt-2">
                        {othersWomenFetch.data.rivalries.map(e => (
                          <RivalryTile
                            key={`ow-${e.team1}|${e.team2}`}
                            entry={e}
                            ambient={ambient}
                            gender="female"
                          />
                        ))}
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            )}

            {otherIntl.length > 0 && (
              <div className="mt-5">
                {!showOtherIntl ? (
                  <button
                    type="button"
                    className="wisden-clear"
                    onClick={() => setShowOtherIntl(true)}
                  >
                    ▸ Other international tournaments ({otherIntl.length})
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      className="wisden-clear"
                      onClick={() => setShowOtherIntl(false)}
                    >
                      ▾ Hide other international tournaments
                    </button>
                    <div className="wisden-tile-help mt-1">
                      Qualifiers, regional events, minor series.
                    </div>
                    <div className="wisden-tile-grid mt-1">
                      {otherIntl.map(e => (
                        <TournamentTile key={e.canonical} entry={e} ambient={ambient} />
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Right column — Club ── */}
        {showClub && (
          <div>
            <Section
              title="Franchise leagues"
              tiles={clubFranchise}
              ambient={ambient}
              emptyLabel="No franchise leagues in this filter scope."
            />
            <Section
              title="Domestic leagues"
              tiles={clubDomestic}
              ambient={ambient}
            />
            <Section
              title="Women's franchise leagues"
              tiles={clubWomen}
              ambient={ambient}
            />
            <Section
              title="Other tournaments"
              tiles={clubOther}
              ambient={ambient}
            />
          </div>
        )}
      </div>
    </div>
  )
}
