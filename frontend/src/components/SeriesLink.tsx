/**
 * A link to the Series page with the scope given as props, not taken from the filter bar.
 *
 * SeriesLink — single link that navigates to `/series?...` with a fully
 * described scope.
 *
 * Mirror of TeamLink / PlayerLink, but pointing at a **series destination**
 * rather than an entity page. Used for tournament tiles, rivalry tiles,
 * innings-list tournament cells — anywhere the click target is "go to
 * this series view" rather than "go to this team/player".
 *
 * Props describe the scope directly (no useFilters / no SubscriptSource
 * resolution). Callers pass exactly what the URL should carry — this
 * keeps the component predictable on tile surfaces whose URL scope
 * doesn't match the ambient FilterBar (e.g. the landing tile carries
 * implicit gender/team_type from the row, not from the FilterBar).
 *
 * `season` collapses to season_from = season_to = season (single-edition
 * scope). For ranges, pass season_from + season_to explicitly.
 */
import type React from 'react'
import { Link } from 'react-router-dom'

/** Props of `SeriesLink`: the URL parameters to set; an empty one is left out. */
interface SeriesLinkProps {
  tournament?: string | null // the tournament name
  season?: string | null // one season; sets both `season_from` and `season_to`, and wins over them
  season_from?: string | null // the first season of a range
  season_to?: string | null // the last season of a range
  seriesType?: string | null // the `series_type` parameter; "all" is left out
  team1?: string | null // written as `filter_team`
  team2?: string | null // written as `filter_opponent`
  gender?: string | null // "male" or "female"
  team_type?: string | null // "international" or "club"
  filter_venue?: string | null // the venue name
  className?: string // the link's class; defaults to "comp-link"
  title?: string // the tooltip
  onClick?: React.MouseEventHandler<HTMLAnchorElement> // called on click, before navigation
  children: React.ReactNode // the link content
}

/** Show a link to `/series` with the given scope as URL parameters. */
export default function SeriesLink({
  tournament, season, season_from, season_to, seriesType,
  team1, team2, gender, team_type, filter_venue,
  className = 'comp-link', title, onClick, children,
}: SeriesLinkProps) {
  const p = new URLSearchParams()
  if (tournament) p.set('tournament', tournament)
  if (season) {
    p.set('season_from', season)
    p.set('season_to', season)
  } else {
    if (season_from) p.set('season_from', season_from)
    if (season_to) p.set('season_to', season_to)
  }
  if (seriesType && seriesType !== 'all') p.set('series_type', seriesType)
  if (team1) p.set('filter_team', team1)
  if (team2) p.set('filter_opponent', team2)
  if (gender) p.set('gender', gender)
  if (team_type) p.set('team_type', team_type)
  if (filter_venue) p.set('filter_venue', filter_venue)

  const qs = p.toString()
  const href = qs ? `/series?${qs}` : '/series'
  return (
    <Link to={href} className={className} title={title} onClick={onClick}>
      {children}
    </Link>
  )
}
