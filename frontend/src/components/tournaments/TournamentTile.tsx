/**
 * The landing tile for one canonical tournament, linking to its all-editions page.
 *
 * TournamentTile — wisden-tile card for one canonical tournament.
 *
 * Renders the canonical name, edition + match counts, most-titles
 * team, and the most recent edition + its winner. The whole tile is
 * a stretched SeriesLink to the tournament's all-editions page.
 *
 * Originally a module-local component in `TournamentsLanding.tsx`;
 * extracted 2026-05-13 so the new `/league` page can reuse it as
 * its Overview "Tournaments in scope" tile grid. Single source of
 * truth — both consumers render identical tiles.
 *
 * Spec: docs/internal/spec-league-pages.md step 6.
 */
import type { useFilters } from '../../hooks/useFilters'
import SeriesLink from '../SeriesLink'
import TeamLink from '../TeamLink'
import type { TournamentLandingEntry } from '../../types'

/** Pass-through scope fields common to every landing link. Used by the
 *  stretched primary link on each tile. */
export interface TileAmbientScope {
  gender?: string // "male" or "female"; absent when not set
  team_type?: string // "international" or "club"; absent when not set
  season_from?: string // the first season of the range
  season_to?: string // the last season of the range
  filter_venue?: string // the venue filter
}

/** Pick the tile's pass-through scope out of the page filters, dropping empty values. */
export function tileAmbientFromFilters(
  filters: ReturnType<typeof useFilters>, // the page filters from `useFilters`
): TileAmbientScope { // gender, team_type, seasons and venue, each undefined when empty
  return {
    gender: filters.gender || undefined,
    team_type: filters.team_type || undefined,
    season_from: filters.season_from || undefined,
    season_to: filters.season_to || undefined,
    filter_venue: filters.filter_venue || undefined,
  }
}

/**
 * Show a tournament's name, edition and match counts, most-titles team, latest edition and its winner.
 * `entry` is the tournament's landing entry; `ambient` is the pass-through scope for the links.
 * The tile's own gender and team_type win over the ambient ones on every link.
 * @param props the props
 * @param props.entry the tournament's landing entry
 * @param props.ambient the pass-through scope for the links
 */
export default function TournamentTile({
  entry, ambient,
}: { entry: TournamentLandingEntry; ambient: TileAmbientScope }) {
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
          {entry.most_titles.titles > 1 ? (
            <TeamLink
              teamName={entry.most_titles.team}
              gender={rowGender ?? null}
              team_type={rowTeamType ?? null}
              subscriptSource={{ tournament: entry.canonical }}
              maxTiers={1}
              phraseLabel={`(${entry.most_titles.titles})`}
            />
          ) : (
            <TeamLink
              teamName={entry.most_titles.team}
              compact
              gender={rowGender ?? null}
              team_type={rowTeamType ?? null}
            />
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
              Winner:{' '}
              <TeamLink
                teamName={entry.latest_edition.champion}
                gender={rowGender ?? null}
                team_type={rowTeamType ?? null}
                subscriptSource={{
                  tournament: entry.canonical,
                  season: entry.latest_edition.season,
                }}
                maxTiers={1}
                phraseLabel="ed"
                phraseClassName="scope-phrase-ed"
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}
