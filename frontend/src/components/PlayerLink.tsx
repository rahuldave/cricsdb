/**
 * PlayerLink — name link + contextual scope-phrase subscripts for a player.
 *
 *   Name link    → /batting|/bowling|/fielding|/players?player=X
 *                  All-time, gender only. "Go to this player"; no scope.
 *
 *   Phrase subscripts (0–3), small-caps:
 *     - "vs <Opp>"                — rivalry alone (all-time vs opponent)
 *     - "at <Tournament> vs <Opp>" — rivalry + tournament
 *     - "at <Tournament>, <Season> vs <Opp>" — rivalry + tournament + season
 *     - "at <Tournament>"          — tournament alone (no rivalry)
 *     - "at <Tournament>, <Season>" — tournament alone narrowed by season
 *     - "in <Season>"              — season alone
 *
 *   See `scopeLinks.ts::resolveScopePhrases` (called with keepRivalry: true)
 *   for tier resolution.
 *
 * Per-row surfaces (innings lists, leaderboard rows) pass `subscriptSource`
 * to draw the phrase bucket from the row's match, not page filters. For
 * rivalry-mode rows, `rowSubscriptSource` (in TournamentDossier) pre-orients
 * the source so the rivalry phrase faces the row's own team.
 *
 * Dense surfaces (scorecard rows, matchup grids) pass `compact` to
 * render only the name link.
 */
import type React from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  resolveBucket, nameParams, resolveScopePhrases,
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
  /** Hide the phrase subscripts. For dense surfaces (scorecard rows). */
  compact?: boolean
  /** Content rendered between the name link and the phrase subscripts.
   *  Use when a stat is intrinsic to the scope (e.g. "· 794 runs" against
   *  a rivalry opponent reads more natural with the "vs Australia" phrase
   *  AFTER the stat: `V Kohli · 794 runs vs Australia`). */
  trailingContent?: React.ReactNode
}

export default function PlayerLink({
  personId, name, role, subscriptSource, gender, compact, trailingContent,
}: PlayerLinkProps) {
  const filters = useScopeFilters()
  const [searchParams] = useSearchParams()
  const seriesType = searchParams.get('series_type')
  const effectiveFilters = gender !== undefined
    ? { ...filters, gender: gender ?? undefined }
    : filters

  if (!personId) return <>{name}{trailingContent}</>
  const path = ROLE_PATH[role]

  const nameQs = new URLSearchParams({ player: personId, ...nameParams(effectiveFilters) })
  const nameHref = `${path}?${nameQs.toString()}`

  if (compact) {
    return <><Link to={nameHref} className="comp-link">{name}</Link>{trailingContent}</>
  }

  const bucket = resolveBucket(effectiveFilters, subscriptSource)
  const phrases = resolveScopePhrases(bucket, { keepRivalry: true, seriesType })
  if (phrases.length === 0) {
    return <><Link to={nameHref} className="comp-link">{name}</Link>{trailingContent}</>
  }

  const subs = phrases.map((ph, i) => {
    const qs = new URLSearchParams({ player: personId, ...ph.params })
    return { key: `${i}-${ph.label}`, href: `${path}?${qs.toString()}`, ...ph }
  })

  return (
    <>
      <Link to={nameHref} className="comp-link">{name}</Link>
      {trailingContent}
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
