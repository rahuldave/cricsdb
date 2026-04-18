import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../FilterBar'
import { useFetch } from '../../hooks/useFetch'
import { getTournamentsLanding, getTournamentOtherRivalries } from '../../api'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import type {
  TournamentsLanding as TLandingData,
  TournamentLandingEntry,
  RivalryEntry,
} from '../../types'

/** Build a querystring that carries filters into dossier navigation. */
function buildFilterQs(filters: ReturnType<typeof useFilters>): string {
  const p = new URLSearchParams()
  if (filters.gender) p.set('gender', filters.gender)
  if (filters.team_type) p.set('team_type', filters.team_type)
  if (filters.season_from) p.set('season_from', filters.season_from)
  if (filters.season_to) p.set('season_to', filters.season_to)
  if (filters.filter_venue) p.set('filter_venue', filters.filter_venue)
  return p.toString()
}

function TournamentTile({
  entry, filterQs,
}: { entry: TournamentLandingEntry; filterQs: string }) {
  // Carry the tile's implicit gender/team_type into the URL so the
  // FilterBar doesn't have to auto-correct. For canonical names like
  // "T20 World Cup (Men)" those aren't auto-narrowable (no matching
  // cricsheet event_name); passing them explicitly keeps downstream
  // endpoints scoped correctly.
  const p = new URLSearchParams(filterQs)
  p.set('tournament', entry.canonical)
  if (entry.gender && !p.has('gender')) p.set('gender', entry.gender)
  if (entry.team_type && !p.has('team_type')) p.set('team_type', entry.team_type)
  const qs = `?${p.toString()}`
  return (
    <Link to={`/series${qs}`} className="wisden-tile">
      <div className="wisden-tile-title">{entry.canonical}</div>
      <div className="wisden-tile-sub">
        {entry.editions} {entry.editions === 1 ? 'edition' : 'editions'}
        {' · '}
        {entry.matches.toLocaleString()} {entry.matches === 1 ? 'match' : 'matches'}
      </div>
      {entry.most_titles && (
        <div className="wisden-tile-line">
          Most titles: <span className="wisden-tile-em">{entry.most_titles.team}</span>
          {entry.most_titles.titles > 1 && ` (${entry.most_titles.titles})`}
        </div>
      )}
      {entry.latest_edition && (
        <div className="wisden-tile-line">
          Latest: {entry.latest_edition.season}
          {entry.latest_edition.champion && (
            <> — <span className="wisden-tile-em">{entry.latest_edition.champion}</span></>
          )}
        </div>
      )}
    </Link>
  )
}

function RivalryTile({
  entry, filterQs, gender,
}: { entry: RivalryEntry; filterQs: string; gender: 'male' | 'female' }) {
  // Rivalry tiles are bilateral-only by design. Click → match-set
  // dossier scoped to the team pair, filtered to bilateral series.
  const p = new URLSearchParams(filterQs)
  p.set('filter_team', entry.team1)
  p.set('filter_opponent', entry.team2)
  // Tournaments-landing rivalry tiles are international bilateral pairs
  // by definition. Land on bilateral-T20Is scope (excludes ICC events
  // like World Cup meetings — those have their own discovery path).
  p.set('series_type', 'bilateral')
  if (!p.has('gender')) p.set('gender', gender)
  if (!p.has('team_type')) p.set('team_type', 'international')
  const qs = `?${p.toString()}`
  const genderLabel = gender === 'female' ? "women's" : "men's"
  return (
    <Link to={`/series${qs}`} className="wisden-tile">
      <div className="wisden-tile-title">
        {entry.team1} <span className="wisden-tile-vs">v</span> {entry.team2}
        <span className="wisden-tile-faint" style={{ fontSize: '0.78em' }}> {genderLabel}</span>
      </div>
      <div className="wisden-tile-sub">
        {entry.matches} {entry.matches === 1 ? 'match' : 'matches'}
        <span className="wisden-tile-faint"> · bilateral</span>
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
    </Link>
  )
}

function Section({
  title, tiles, emptyLabel, filterQs,
}: {
  title: string
  tiles: TournamentLandingEntry[]
  emptyLabel?: string
  filterQs: string
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
          <TournamentTile key={e.canonical} entry={e} filterQs={filterQs} />
        ))}
      </div>
    </div>
  )
}

function RivalryGrid({
  title, top, gender, filterQs,
}: {
  title: string
  top: RivalryEntry[]
  gender: 'male' | 'female'
  filterQs: string
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
            filterQs={filterQs}
            gender={gender}
          />
        ))}
      </div>
    </div>
  )
}

export default function TournamentsLanding() {
  const filters = useFilters()
  const filterQs = buildFilterQs(filters)

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
              filterQs={filterQs}
              emptyLabel="No international events in this filter scope."
            />

            {/* ── Men's bilateral rivalries ── */}
            {rivalries.men.top.length > 0 && (
              <RivalryGrid
                title={`Men's bilateral rivalries (${rivalries.men.top.length})`}
                top={rivalries.men.top}
                gender="male"
                filterQs={filterQs}
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
                            key={`m-${e.team1}|${e.team2}`}
                            entry={e}
                            filterQs={filterQs}
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
                filterQs={filterQs}
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
                            key={`w-${e.team1}|${e.team2}`}
                            entry={e}
                            filterQs={filterQs}
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
                        <TournamentTile key={e.canonical} entry={e} filterQs={filterQs} />
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
              filterQs={filterQs}
              emptyLabel="No franchise leagues in this filter scope."
            />
            <Section
              title="Domestic leagues"
              tiles={clubDomestic}
              filterQs={filterQs}
            />
            <Section
              title="Women's franchise leagues"
              tiles={clubWomen}
              filterQs={filterQs}
            />
            <Section
              title="Other tournaments"
              tiles={clubOther}
              filterQs={filterQs}
            />
          </div>
        )}
      </div>
    </div>
  )
}
