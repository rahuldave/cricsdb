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
  /** Cap the number of scope-phrase subscripts rendered (narrowest
   *  first). Default: unlimited. Dense cells pass 1 for a single
   *  narrow tier. */
  maxTiers?: number
  /** Override the rendered phrase text while keeping the computed URL.
   *  String replaces every phrase; function gets (tier, index) and
   *  returns per-tier text. The computed tier's `label` is preserved in
   *  the tooltip so the full scope stays discoverable on hover. Intended
   *  for compact-token variants like "ed" in dense tables. Mirrors
   *  TeamLink.phraseLabel. */
  phraseLabel?: string | ((tier: { label: string }, index: number) => string)
  /** Extra class appended to `comp-link scope-phrase` for rendering
   *  variants. `scope-phrase-ed` gives the small-caps compact marker
   *  style used on Matches / Records tabs. Mirrors
   *  TeamLink.phraseClassName. */
  phraseClassName?: string
  /** Override series_type for container resolution. Defaults to reading
   *  `series_type` from the URL. Pass explicitly on curated surfaces
   *  that know their own scope. Mirrors TeamLink.seriesType. */
  seriesType?: string | null
  /** Whether the rivalry pair (filter_team / filter_opponent) rides
   *  through into the phrase URL + is emitted as "vs <Opp>".
   *  PlayerLink's default is true — a player's "vs Opp" axis IS
   *  meaningful (Kohli at IPL vs CSK). Override to false on surfaces
   *  where the single-player destination should ignore rivalry context. */
  keepRivalry?: boolean
}

export default function PlayerLink({
  personId, name, role, subscriptSource, gender, compact, trailingContent,
  maxTiers, phraseLabel, phraseClassName,
  seriesType: seriesTypeProp, keepRivalry = true,
}: PlayerLinkProps) {
  const filters = useScopeFilters()
  const [searchParams] = useSearchParams()
  // Prop override wins so curated surfaces (tiles with their own scope)
  // don't depend on the caller page's URL carrying series_type.
  const seriesType = seriesTypeProp !== undefined
    ? seriesTypeProp
    : searchParams.get('series_type')
  const effectiveFilters = gender !== undefined
    ? { ...filters, gender: gender ?? undefined }
    : filters
  const phraseCls = `comp-link scope-phrase${phraseClassName ? ' ' + phraseClassName : ''}`
  const renderPhraseLabel = (origLabel: string, index: number): string => {
    if (phraseLabel === undefined) return origLabel
    if (typeof phraseLabel === 'string') return phraseLabel
    return phraseLabel({ label: origLabel }, index)
  }

  if (!personId) return <>{name}{trailingContent}</>
  const path = ROLE_PATH[role]

  const nameQs = new URLSearchParams({ player: personId, ...nameParams(effectiveFilters) })
  const nameHref = `${path}?${nameQs.toString()}`

  if (compact) {
    return <><Link to={nameHref} className="comp-link">{name}</Link>{trailingContent}</>
  }

  const bucket = resolveBucket(effectiveFilters, subscriptSource)
  const allPhrases = resolveScopePhrases(bucket, { keepRivalry, seriesType })
  const phrases = typeof maxTiers === 'number' ? allPhrases.slice(0, maxTiers) : allPhrases
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
            <Link to={s.href} className={phraseCls} title={s.tooltip}>
              {renderPhraseLabel(s.label, i)}
            </Link>
          </span>
        ))}
      </span>
    </>
  )
}
