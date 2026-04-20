/**
 * TeamLink — name link + contextual scope-phrase subscripts for a team.
 *
 *   Name link  → /teams?team=X — identity only (gender + team_type).
 *                Same destination on every tab: "go to this team's
 *                overall page". Subscripts below or beside the name
 *                carry scope.
 *
 *   Phrase subscripts (0, 1, or 2):
 *     - "at <Tournament>" — broad, all editions at this tournament
 *     - "at <Tournament>, <Season>" — narrow, this edition
 *     - "vs <Opponent>" / "vs <Opponent>, <Season>" — when rivalry is
 *       the active axis (no tournament set)
 *   Off-axis filters are dropped from the subscript URL (e.g. rivalry
 *   pair drops when tournament wins). Venue + series_type ride through
 *   silently — their detail appears in the tooltip.
 *
 *   See `scopeLinks.ts::resolveScopePhrases` for the axis resolution.
 *
 * Layout prop:
 *   - 'inline' (default) → "Australia at T20 WC 2024, at T20 WC"
 *   - 'block'            → small-caps phrases stacked below the name
 *                          (used in H2 page titles)
 *
 * Dense surfaces pass `compact` to render only the name link.
 */
import { Link, useSearchParams } from 'react-router-dom'
import {
  resolveBucket, nameParams, resolveScopePhrases,
  useScopeFilters,
  type SubscriptSource,
} from './scopeLinks'

interface TeamLinkProps {
  /** Canonical team name — used as both label and URL value. */
  teamName: string
  subscriptSource?: SubscriptSource
  /** Override gender on the name link. */
  gender?: string | null
  /** Override team_type on the name link. Useful on curated surfaces
   *  (landing tiles) where team_type is known per-row but no FilterBar
   *  context is available. */
  team_type?: string | null
  /** Render only the name link. */
  compact?: boolean
  /** 'inline' after the name (tables) or 'block' below it (H2). */
  layout?: 'inline' | 'block'
  /** Preserve rivalry pair in URL + emit "vs <Opp>" phrase. Default false
   *  — TeamLink's single-team page destination normally drops the pair.
   *  Callers that sit on a rivalry surface (e.g. rivalry-tile Winner
   *  line) pass true so the scope phrase reads "at T20 WC, 2024 vs
   *  Australia". */
  keepRivalry?: boolean
  /** Override series_type for container resolution. Defaults to reading
   *  `series_type` from the URL. Pass explicitly on surfaces whose own
   *  URL doesn't carry the aux filter (e.g. home-tab rivalry tiles
   *  linking the Winner into a bilateral-scoped URL). */
  seriesType?: string | null
  /** Cap the number of scope-phrase subscripts rendered (narrowest
   *  first). Default: unlimited — all tiers that apply to the active
   *  axes are shown (see `resolveScopePhrases`). Dense surfaces (landing
   *  tiles) pass 1 to show only the narrowest phrase; the broader-scope
   *  tiers are redundant there because the team name link itself is the
   *  all-time view. */
  maxTiers?: number
}

export default function TeamLink({
  teamName, subscriptSource, gender, team_type, compact, layout = 'inline',
  keepRivalry = false, seriesType: seriesTypeProp, maxTiers,
}: TeamLinkProps) {
  const filters = useScopeFilters()
  const [searchParams] = useSearchParams()
  // series_type is a Series-tab-local URL param (mirrors the backend's
  // AuxParams split). Not in FILTER_KEYS, so useFilters() doesn't pick
  // it up — read directly. Drives the team-level container resolution
  // (bilateral → drop tournament from URL; icc/club → keep it).
  // Prop override wins when set: curated surfaces (rivalry tiles) know
  // their scope without relying on the caller page's URL.
  const seriesType = seriesTypeProp !== undefined ? seriesTypeProp : searchParams.get('series_type')
  const effectiveFilters = (gender !== undefined || team_type !== undefined)
    ? {
        ...filters,
        ...(gender !== undefined ? { gender: gender ?? undefined } : {}),
        ...(team_type !== undefined ? { team_type: team_type ?? undefined } : {}),
      }
    : filters

  const nameQs = new URLSearchParams({
    team: teamName,
    ...nameParams(effectiveFilters, ['gender', 'team_type']),
  })
  const nameHref = `/teams?${nameQs.toString()}`

  if (compact) {
    return <Link to={nameHref} className="comp-link">{teamName}</Link>
  }

  const bucket = resolveBucket(effectiveFilters, subscriptSource)
  const allPhrases = resolveScopePhrases(bucket, { swapForTeam: teamName, seriesType, keepRivalry })
  const phrases = typeof maxTiers === 'number' ? allPhrases.slice(0, maxTiers) : allPhrases
  if (phrases.length === 0) {
    return <Link to={nameHref} className="comp-link">{teamName}</Link>
  }

  const subs = phrases.map((ph, i) => {
    const qs = new URLSearchParams({ team: teamName, ...ph.params })
    return { key: `${i}-${ph.label}`, href: `/teams?${qs.toString()}`, ...ph }
  })

  if (layout === 'block') {
    // Wrap the name+subscripts in an inline-block container so that the
    // H2 flow ("Australia v India") stays on one line while the
    // subscripts stack vertically UNDER each team name. Without this,
    // `display: block` on the subscript span pushes the " v India"
    // onto a new line.
    return (
      <span className="team-link-block">
        <Link to={nameHref} className="comp-link">{teamName}</Link>
        <span className="scope-phrases-block">
          {subs.map(s => (
            <Link key={s.key} to={s.href} className="comp-link scope-phrase" title={s.tooltip}>
              {s.label}
            </Link>
          ))}
        </span>
      </span>
    )
  }

  return (
    <>
      <Link to={nameHref} className="comp-link">{teamName}</Link>
      <span className="scope-phrases-inline">
        {subs.map((s, i) => (
          <span key={s.key}>
            {i === 0 ? ' ' : <span className="scope-phrases-sep">, </span>}
            <Link to={s.href} className="comp-link scope-phrase" title={s.tooltip}>
              {s.label}
            </Link>
          </span>
        ))}
      </span>
    </>
  )
}
