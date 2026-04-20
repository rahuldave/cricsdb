/**
 * ScopeStatusStrip — one-line read-only summary of active filters.
 *
 * Deliberately duplicates the FilterBar chip state: FilterBar is edit
 * mode (dropdowns + controls), this strip is read mode (readable prose
 * + a copy-link button). The "(copy link)" button lifts the share
 * burden off the URL bar, which many users don't know how to manipulate.
 *
 * Hidden entirely when no filter is active — an empty strip would be
 * visual clutter on pages whose content is the whole app (the home page
 * or a scorecard where global filters don't apply).
 *
 * Reads:
 *   - FilterBar fields via `useFilters()` — gender, team_type, tournament,
 *     season_from/to, filter_team, filter_opponent, filter_venue.
 *   - `series_type` directly from URL (Series-tab local param, not in
 *     FilterParams).
 *   - Path identity params (`team`, `player`, `compare`, `venue`) so
 *     the strip reflects what the CURRENT PAGE is about, not just its
 *     FilterBar settings.
 */
import { useState } from 'react'
import { useSearchParams, useLocation } from 'react-router-dom'
import { useFilters } from '../hooks/useFilters'
import { seasonTag } from './scopeLinks'

type Segment = { label: string; value: string }

function buildSegments(
  filters: ReturnType<typeof useFilters>,
  seriesType: string | null,
  pathTeam: string | null,
  pathVenue: string | null,
  pathPlayer: string | null,
  pathCompare: string | null,
  tab: string | null,
  page: string | null,
): Segment[] {
  const segs: Segment[] = []

  // Page-identity segments go FIRST so the read "Team: Mumbai Indians · men's · IPL" starts with the subject.
  if (pathTeam) segs.push({ label: 'Team', value: pathTeam })
  if (pathVenue) segs.push({ label: 'Venue', value: pathVenue })
  if (pathPlayer) {
    // On compare URL, read as "A vs B" / "A vs B, C"
    if (pathCompare) {
      segs.push({ label: 'Compare', value: `${pathPlayer} vs ${pathCompare}` })
    } else {
      segs.push({ label: 'Player', value: pathPlayer })
    }
  }

  // Identity filters (gender, team_type) — short labels.
  if (filters.gender) segs.push({ label: 'Gender', value: filters.gender === 'male' ? "men's" : filters.gender === 'female' ? "women's" : filters.gender })
  if (filters.team_type) segs.push({ label: 'Type', value: filters.team_type })

  // Tournament container.
  if (filters.tournament) segs.push({ label: 'Tournament', value: filters.tournament })

  // Rivalry (when set via filter_team/opponent on a non-team-identity page).
  // On a team page (pathTeam set), filter_opponent narrows that team's
  // stats to matches vs the opponent.
  if (filters.filter_team && !pathTeam) {
    segs.push({ label: 'Team', value: filters.filter_team })
  }
  if (filters.filter_opponent) {
    segs.push({ label: 'vs Opponent', value: filters.filter_opponent })
  }

  // Season range.
  const season = seasonTag(filters.season_from, filters.season_to)
  if (season) segs.push({ label: 'Season', value: season })

  // Venue filter (filter_venue), distinct from path venue.
  if (filters.filter_venue && !pathVenue) {
    segs.push({ label: 'Venue', value: filters.filter_venue })
  }

  // Series-type aux filter — surfaced on every tab where it's set.
  // Initially a Series-tab-local pill, but the AuxParams refactor made
  // it propagate through useFilters and apply on every endpoint, so
  // showing it on /teams, /batting, /bowling, etc. is correct (and
  // necessary so the user understands why a count looks narrower than
  // expected on a deep-linked URL).
  if (seriesType && seriesType !== 'all') {
    const label = seriesType === 'bilateral' ? 'bilateral T20Is'
      : seriesType === 'icc' ? 'ICC events'
      : seriesType === 'club' ? 'club tournaments'
      : seriesType
    segs.push({ label: 'Show', value: label })
  }

  // Active tab + pagination — URL-driven, so both deep-link into the
  // strip. "Overview" is the default tab across every dossier; show
  // the segment only when it's something else. Page shown when > 1.
  if (tab && tab !== 'Overview') segs.push({ label: 'Tab', value: tab })
  const pageNum = page ? parseInt(page, 10) : 0
  if (pageNum > 1) segs.push({ label: 'Page', value: String(pageNum) })

  return segs
}

export default function ScopeStatusStrip() {
  const filters = useFilters()
  const [params] = useSearchParams()
  const { pathname } = useLocation()
  const [copied, setCopied] = useState(false)

  // Hidden on pages where global filters don't apply (home, scorecard, help).
  // Layout.tsx already hides FilterBar on those; mirror the same rule.
  if (pathname === '/' || /^\/matches\/[^/]+$/.test(pathname) || pathname.startsWith('/help')) {
    return null
  }

  const seriesType = params.get('series_type')
  const pathTeam = params.get('team')
  const pathVenue = params.get('venue')
  const pathPlayer = params.get('player')
  const pathCompare = params.get('compare')
  const tab = params.get('tab')
  const page = params.get('page')

  const segments = buildSegments(
    filters, seriesType, pathTeam, pathVenue, pathPlayer, pathCompare, tab, page,
  )

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      console.warn('Clipboard copy failed:', err)
    }
  }

  // Outer wrapper carries the tinted bg + bottom rule so the strip spans
  // the full viewport width. Inner element keeps the 80rem content
  // constraint aligned with the rest of the page. Always rendered when
  // FilterBar is visible — even on an unfiltered page, the copy-link
  // button stays accessible and the empty-state reads "Scope: all-time".
  return (
    <div className="wisden-scope-strip-wrap">
      <div className="wisden-scope-strip">
        <span className="wisden-scope-strip-label">Showing:</span>
        {segments.length === 0 ? (
          <span className="wisden-scope-strip-seg">
            <span className="wisden-scope-strip-segValue">all-time</span>
          </span>
        ) : segments.map((s, i) => (
          <span key={`${s.label}-${i}`} className="wisden-scope-strip-seg">
            {i > 0 && <span className="wisden-scope-strip-sep"> · </span>}
            <span className="wisden-scope-strip-segLabel">{s.label}:</span>
            {' '}
            <span className="wisden-scope-strip-segValue">{s.value}</span>
          </span>
        ))}
        <button
          type="button"
          className="wisden-scope-strip-copy"
          onClick={handleCopy}
          title="Copy shareable link to clipboard"
        >
          {copied ? 'copied ✓' : 'copy link'}
        </button>
      </div>
    </div>
  )
}
