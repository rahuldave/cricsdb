/**
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

interface SeriesLinkProps {
  tournament?: string | null
  season?: string | null
  season_from?: string | null
  season_to?: string | null
  seriesType?: string | null
  team1?: string | null
  team2?: string | null
  gender?: string | null
  team_type?: string | null
  filter_venue?: string | null
  className?: string
  title?: string
  onClick?: React.MouseEventHandler<HTMLAnchorElement>
  children: React.ReactNode
}

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
