/**
 * PlayerLink — name link + contextual letter links for a player.
 *
 *   Name link    → /batting|/bowling|/fielding|/players?player=X
 *                  All-time, gender only. "Go to this player"; no scope.
 *
 *   Letter links (e, t, s, b) → scoped variants. Each carries the
 *                  entire FilterBar state EXCEPT the axis it represents.
 *                  See `scopeLinks.ts` for the full table-driven model.
 *                    (e) = this tournament, current season range
 *                    (t) = this tournament, all editions
 *                    (s) = this rivalry, current series
 *                    (b) = this rivalry, all-time
 *                  Tooltip spells out the full scope in words.
 *
 * Per-row surfaces (innings lists, match rows) pass `subscriptSource` to
 * draw the letter-link bucket from the row's match, not page filters.
 *
 * Dense surfaces (scorecard rows, matchup grids) pass `compact` to
 * render only the name link.
 */
import { Link } from 'react-router-dom'
import {
  resolveBucket, nameParams, tierParams, activeTiers, tierTooltip, sameParams,
  useScopeFilters,
  type SubscriptSource,
} from './scopeLinks'

type PlayerRole = 'home' | 'batter' | 'bowler' | 'fielder'

const ROLE_PATH: Record<PlayerRole, string> = {
  home: '/players',
  batter: '/batting',
  bowler: '/bowling',
  fielder: '/fielding',
}

interface PlayerLinkProps {
  personId: string | null | undefined
  name: string
  role: PlayerRole
  subscriptSource?: SubscriptSource
  /** Override gender on the name link. Defaults to FilterBar's gender.
   *  Use on curated/filter-less surfaces (Home's featured players) where
   *  gender is known per-link but no FilterBar is present. */
  gender?: string | null
  /** Hide the letter-link cluster. For dense surfaces (scorecard rows). */
  compact?: boolean
}

export default function PlayerLink({
  personId, name, role, subscriptSource, gender, compact,
}: PlayerLinkProps) {
  const filters = useScopeFilters()
  const effectiveFilters = gender !== undefined
    ? { ...filters, gender: gender ?? undefined }
    : filters

  if (!personId) return <>{name}</>
  const path = ROLE_PATH[role]

  const nameQs = new URLSearchParams({ player: personId, ...nameParams(effectiveFilters) })
  const nameHref = `${path}?${nameQs.toString()}`

  if (compact) {
    return <Link to={nameHref} className="comp-link">{name}</Link>
  }

  const bucket = resolveBucket(effectiveFilters, subscriptSource)
  const tiers = activeTiers(bucket, subscriptSource)
  if (tiers.length === 0) {
    return <Link to={nameHref} className="comp-link">{name}</Link>
  }

  // Build subscript links + collapse duplicates.
  const subs = tiers.map(tier => {
    const p = tierParams(bucket, tier)
    const qs = new URLSearchParams({ player: personId, ...p })
    return {
      tier,
      href: `${path}?${qs.toString()}`,
      tooltip: tierTooltip(bucket, tier),
      params: p,
    }
  })
  // Hide (e) if its URL == (t)'s; hide (s) if == (b)'s.
  const visible = subs.filter((s, i) => {
    if (s.tier === 'e' || s.tier === 's') {
      const sibling = subs[i + 1]  // t or b
      return !sibling || !sameParams(s.params, sibling.params)
    }
    return true
  })

  return (
    <>
      <Link to={nameHref} className="comp-link">{name}</Link>
      {' '}
      <span className="scope-subs">
        (
        {visible.map((s, i) => (
          <span key={s.tier}>
            {i > 0 && <span className="scope-subs-sep">, </span>}
            <Link to={s.href} className="comp-link scope-sub" title={s.tooltip}>{s.tier}</Link>
          </span>
        ))}
        )
      </span>
    </>
  )
}
