import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useFilters } from '../../hooks/useFilters'
import { useFetch } from '../../hooks/useFetch'
import { getTournamentsLanding, getTournamentOtherRivalries } from '../../api'
import Spinner from '../Spinner'
import ErrorBanner from '../ErrorBanner'
import SeriesLink from '../SeriesLink'
import TeamLink from '../TeamLink'
import { SectionHeader } from '../ChartHeader'
import TournamentTile, {
  tileAmbientFromFilters as ambientFromFilters,
  type TileAmbientScope as AmbientScope,
} from './TournamentTile'
import type {
  TournamentsLanding as TLandingData,
  TournamentLandingEntry,
  RecentEditionEntry,
  RivalryEntry,
} from '../../types'

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
            return (
              <div className="wisden-tile-line">
                Winner:{' '}
                <TeamLink
                  teamName={latest.winner}
                  gender={gender}
                  team_type="international"
                  seriesType={latestIsBilateral ? 'bilateral' : null}
                  subscriptSource={{
                    tournament: latestIsBilateral ? null : latest.tournament,
                    season: latest.season,
                    team1: latest.winner,
                    team2: opp,
                  }}
                  keepRivalry
                  maxTiers={1}
                  phraseLabel="ed"
                  phraseClassName="scope-phrase-ed"
                />
              </div>
            )
          })()}
        </>
      )}
    </div>
  )
}

/** Top-of-landing strip — the 5 most recently played editions across
 *  every tournament, latest-first. Includes in-progress editions
 *  (champion is null until a Final is played). Vertical stack of
 *  links so the user can jump straight to the edition dossier.
 */
function RecentEditionsStrip({
  editions, ambient,
}: { editions: RecentEditionEntry[]; ambient: AmbientScope }) {
  if (!editions.length) return null
  return (
    <div className="wisden-landing-section mt-4">
      <SectionHeader title="Recently played editions" />
      <ul className="wisden-recent-editions">
        {editions.map(e => {
          const rowGender = e.gender || ambient.gender
          const rowTeamType = e.team_type || ambient.team_type
          return (
            <li key={`${e.tournament}|${e.season}`}>
              <SeriesLink
                tournament={e.tournament}
                season={e.season}
                gender={rowGender}
                team_type={rowTeamType}
                title={`${e.tournament}, ${e.season}`}
              >
                {e.tournament} {e.season}
              </SeriesLink>
              {e.champion && (
                <>
                  {' — winner '}
                  <TeamLink
                    teamName={e.champion}
                    compact
                    gender={rowGender ?? null}
                    team_type={rowTeamType ?? null}
                    subscriptSource={{
                      tournament: e.tournament,
                      season: e.season,
                    }}
                    maxTiers={1}
                    phraseLabel="ed"
                    phraseClassName="scope-phrase-ed"
                  />
                </>
              )}
            </li>
          )
        })}
      </ul>
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
        <SectionHeader title={title} />
        <div className="wisden-tab-help">{emptyLabel}</div>
      </div>
    )
  }
  return (
    <div className="wisden-landing-section">
      <SectionHeader title={title} />
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
      <SectionHeader title={title} />
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

      <RecentEditionsStrip editions={data.recent_editions} ambient={ambient} />

      <ByTierSection
        showInternational={showInternational}
        showClub={showClub}
      />

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


// ─── By-tier cards — entry points to the /league page ─────────────────
//
// 4-6 cards positioned above the per-tournament list. Each card → a
// /league URL with the matching FilterParams. Cards are filtered by
// the active FilterBar gender / team_type so users browsing women's
// only see women's tiers, etc. — same gating as showInternational /
// showClub on the per-tournament sections below.
//
// Spec: internal_docs/spec-league-pages.md §D5 step 10.

interface TierCardSpec {
  label: string
  sublabel: string
  gender: 'male' | 'female'
  team_type: 'club' | 'international'
  team_class?: 'primary_club' | 'secondary_club' | 'full_member'
}

const TIER_CARDS: TierCardSpec[] = [
  { label: "Men's club cricket", sublabel: 'All franchises and domestic leagues',
    gender: 'male', team_type: 'club' },
  { label: "Men's primary-tier clubs", sublabel: 'IPL · BBL · PSL · CPL · SA20 · ILT20 · LPL · MLC · The Hundred',
    gender: 'male', team_type: 'club', team_class: 'primary_club' },
  { label: "Men's secondary-tier clubs", sublabel: 'Other franchise + domestic competitions',
    gender: 'male', team_type: 'club', team_class: 'secondary_club' },
  { label: "Men's international cricket", sublabel: 'ICC events + bilaterals',
    gender: 'male', team_type: 'international' },
  { label: "Women's club cricket", sublabel: "WBBL · Women's Hundred · WPL and more",
    gender: 'female', team_type: 'club' },
  { label: "Women's international cricket", sublabel: 'ICC events + bilaterals',
    gender: 'female', team_type: 'international' },
]

function ByTierSection({
  showInternational, showClub,
}: { showInternational: boolean; showClub: boolean }) {
  // Mirror the per-section gating — when filters narrow to one
  // team_type, hide the other half's tier cards too.
  const visible = TIER_CARDS.filter(c =>
    (c.team_type === 'club' && showClub)
    || (c.team_type === 'international' && showInternational))

  if (visible.length === 0) return null

  return (
    <div className="wisden-landing-section mt-6">
      <SectionHeader title="By tier" />
      <div className="wisden-tile-help mt-1">
        Above-tournament dossiers — what does cricket look like at this scope?
      </div>
      <div className="wisden-tile-grid mt-2">
        {visible.map(c => {
          const params = new URLSearchParams({
            gender: c.gender,
            team_type: c.team_type,
          })
          if (c.team_class) params.set('team_class', c.team_class)
          return (
            <div key={c.label} className="wisden-tile tile-wrapper">
              <Link
                to={`/league?${params.toString()}`}
                className="tile-stretched"
                title={c.label}
              >
                {c.label}
              </Link>
              <div className="wisden-tile-title">{c.label}</div>
              <div className="wisden-tile-sub">{c.sublabel}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
