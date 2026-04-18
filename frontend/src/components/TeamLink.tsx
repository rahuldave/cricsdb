/**
 * TeamLink — name link + contextual letter links for a team.
 *
 *   Name link  → /teams?team=X
 *                All-time, gender only. Same model as PlayerLink.
 *
 *   Letter links (e, t, s, b) → scoped variants. Carry the full
 *                FilterBar state except the axis each letter represents;
 *                see `scopeLinks.ts`. In rivalry mode, if the linked
 *                team is the secondary (filter_opponent), the component
 *                auto-swaps so filter_team = the linked team.
 *
 * Per-row surfaces pass `subscriptSource` to draw the bucket from the
 * row's match rather than page filters. Dense surfaces pass `compact`
 * to render only the name link.
 */
import { Link } from 'react-router-dom'
import {
  resolveBucket, nameParams, tierParams, activeTiers, tierTooltip, sameParams,
  useScopeFilters,
  type SubscriptSource,
} from './scopeLinks'

interface TeamLinkProps {
  /** Canonical team name — used as both label and URL value. */
  teamName: string
  subscriptSource?: SubscriptSource
  gender?: string | null
  compact?: boolean
}

export default function TeamLink({
  teamName, subscriptSource, gender, compact,
}: TeamLinkProps) {
  const filters = useScopeFilters()
  const effectiveFilters = gender !== undefined
    ? { ...filters, gender: gender ?? undefined }
    : filters

  const nameQs = new URLSearchParams({ team: teamName, ...nameParams(effectiveFilters) })
  const nameHref = `/teams?${nameQs.toString()}`

  if (compact) {
    return <Link to={nameHref} className="comp-link">{teamName}</Link>
  }

  const bucket = resolveBucket(effectiveFilters, subscriptSource)
  const tiers = activeTiers(bucket, subscriptSource)
  if (tiers.length === 0) {
    return <Link to={nameHref} className="comp-link">{teamName}</Link>
  }

  const subs = tiers.map(tier => {
    const p = tierParams(bucket, tier, teamName)
    // On rivalry subscripts, if the linked team IS in the pair, the `team=`
    // path param should match filter_team (post-swap). Otherwise leave
    // team=teamName and let the rivalry pair narrow the view.
    const qs = new URLSearchParams({ team: teamName, ...p })
    return {
      tier,
      href: `/teams?${qs.toString()}`,
      tooltip: tierTooltip(bucket, tier, teamName),
      params: p,
    }
  })
  const visible = subs.filter((s, i) => {
    if (s.tier === 'e' || s.tier === 's') {
      const sibling = subs[i + 1]
      return !sibling || !sameParams(s.params, sibling.params)
    }
    return true
  })

  return (
    <>
      <Link to={nameHref} className="comp-link">{teamName}</Link>
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
