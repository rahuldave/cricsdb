/**
 * Shared scope-link helpers used by PlayerLink and TeamLink.
 *
 * Model
 * -----
 * - **Name link**: all-time + gender only. See `nameParams`.
 * - **Letter links** (e, t, s, b): carry the *entire* FilterBar state
 *   through, dropping only the axis the letter represents. Everything
 *   else rides through unchanged.
 *
 * Extensibility
 * -------------
 * Adding a new filter to the FilterBar (e.g. a future `filter_result`)
 * is ONE edit here: append it to `FILTER_KEYS`. It will auto-ride through
 * every letter link. Only touch `TIER_SPECS.drops` if the new filter has
 * an axis that a tier must clear; only touch `SOURCE_MAP` if it needs a
 * per-row override path (row data differing from page state).
 *
 * This guarantees that no tab falls out of sync when a filter is added —
 * the "explicit, per-page, easy to under-wire" landmine documented in
 * internal_docs/design-decisions.md doesn't reappear on link URLs.
 */
import { createContext, useContext } from 'react'
import type { FilterParams } from '../types'
import { useFilters } from './FilterBar'

// ─── Filter registry ───────────────────────────────────────────────────
//
// Single source of truth for which FilterBar fields appear in letter
// link URLs. Every one rides through every letter by default; see
// `TIER_SPECS` below for the per-letter exceptions.
export const FILTER_KEYS = [
  'gender',
  'team_type',
  'tournament',
  'season_from',
  'season_to',
  'filter_team',
  'filter_opponent',
  'filter_venue',
] as const
export type FilterKey = typeof FILTER_KEYS[number]

// ─── Subscript source (per-row override) ───────────────────────────────
//
// When a row's scope differs from the page's FilterBar (e.g. an innings-
// list row has its own tournament + season + teams), callers pass a
// `SubscriptSource` whose fields map onto `FILTER_KEYS` via SOURCE_MAP.
// This decouples the ergonomic per-row shape from the filter registry so
// new filter keys don't force per-row API churn.

export interface SubscriptSource {
  tournament?: string | null
  /** Single season — expands to season_from = season_to = season. */
  season?: string | null
  /** Rivalry pair. TeamLink auto-swaps so filter_team = the linked team. */
  team1?: string | null
  team2?: string | null
}

/** How SubscriptSource's friendly keys map onto FILTER_KEYS. `season`
 *  fans out to both season_from and season_to; the others are 1:1. */
const SOURCE_MAP: Record<keyof SubscriptSource, FilterKey[]> = {
  tournament: ['tournament'],
  season: ['season_from', 'season_to'],
  team1: ['filter_team'],
  team2: ['filter_opponent'],
}

// ─── Tier specs ────────────────────────────────────────────────────────
//
// Each letter link is one tier along the scope axis. Only two things are
// tier-specific: which filter keys the tier "pins" from source (making
// it meaningful to render even when FilterBar has none), and which keys
// it drops from the carried state (the axis being broadened).

export type SubscriptTier = 'e' | 't' | 's' | 'b'

interface TierSpec {
  /** SubscriptSource keys that define this tier — if any are present in
   *  the source, the tier applies. Used by `activeTiers`. */
  needsFromSource: (keyof SubscriptSource)[]
  /** FILTER_KEYS that this tier clears (drops from the URL). Everything
   *  NOT listed here rides through from the resolved bucket. */
  drops: FilterKey[]
}

const TIER_SPECS: Record<SubscriptTier, TierSpec> = {
  // Edition: this tournament's current season range. No drops — pins
  // tournament + season from source; everything else (gender, team_type,
  // filter_venue, plus rivalry if set) rides through.
  e: { needsFromSource: ['tournament'], drops: [] },
  // Tournament (all editions): clear the season range, keep tournament.
  t: { needsFromSource: ['tournament'], drops: ['season_from', 'season_to'] },
  // Series: rivalry pair + tournament + season. No drops — the pair is
  // pinned from source, the rest rides through.
  s: { needsFromSource: ['team1', 'team2'], drops: [] },
  // Bilateral rivalry (all-time): clear tournament + season, keep pair.
  b: { needsFromSource: ['team1', 'team2'], drops: ['tournament', 'season_from', 'season_to'] },
}

// ─── Page scope context ────────────────────────────────────────────────
//
// Some pages use path-like URL params as their primary identity — e.g.
// /teams?team=X, /venues?venue=X, /head-to-head?mode=team&team1=A&team2=B.
// These are NOT in the FilterBar (useFilters doesn't pick them up), but
// they narrow everything inside the page just like FilterBar filters do.
//
// `ScopeContext` lets a page promote path identity into the filter view
// used by link builders. Three layers compose, in override order:
//
//     FilterBar state     (useFilters, from URL search params)
//         ▼
//     Page scope          (ScopeContext — path-identity pinning)
//         ▼
//     Per-row override    (SubscriptSource — innings rows, matchup cells)
//
// New filter types (e.g. a future `filter_result`, or a new search input
// that surfaces a filter) plug into whichever layer they belong to
// without forcing every link call site to know about them.

export const ScopeContext = createContext<Partial<FilterParams>>({})

/** FilterBar state merged with the current page scope. Use this (not
 *  useFilters) in link-building components so path-identity narrowings
 *  flow through without per-call-site prop-drilling. */
export function useScopeFilters(): FilterParams {
  const base = useFilters()
  const extra = useContext(ScopeContext)
  return { ...base, ...extra }
}

// ─── Bucket resolution ─────────────────────────────────────────────────

/** Resolved scope: every FilterBar field, with SubscriptSource overrides
 *  merged on top. A letter link's URL is just this bucket minus the
 *  tier's drops. */
export type SubscriptBucket = { [K in FilterKey]: string | null | undefined }

export function resolveBucket(
  filters: FilterParams,
  source: SubscriptSource | undefined,
): SubscriptBucket {
  const bucket: Partial<SubscriptBucket> = {}
  for (const k of FILTER_KEYS) bucket[k] = filters[k]
  if (source) {
    for (const srcKey of Object.keys(SOURCE_MAP) as (keyof SubscriptSource)[]) {
      const v = source[srcKey]
      if (v === undefined) continue
      for (const filterKey of SOURCE_MAP[srcKey]) {
        bucket[filterKey] = v
      }
    }
  }
  return bucket as SubscriptBucket
}

// ─── Tier activation ───────────────────────────────────────────────────

/** Which tiers apply for the given bucket + source. Rivalry-axis letters
 *  (s, b) win over tournament-axis letters (e, t) when both apply — the
 *  rivalry × tournament overlap case is deferred; see design-decisions.md. */
export function activeTiers(
  bucket: SubscriptBucket,
  source: SubscriptSource | undefined,
): SubscriptTier[] {
  const has = (srcKey: keyof SubscriptSource) => {
    const val = source?.[srcKey]
    if (val !== undefined && val !== null && val !== '') return true
    // If source didn't set it, fall back to the bucket (which has the
    // merged FilterBar value in the SOURCE_MAP-mapped filter key).
    for (const fk of SOURCE_MAP[srcKey]) {
      if (bucket[fk]) return true
    }
    return false
  }
  // Rivalry-axis takes precedence: both team1 AND team2 must be present.
  if (has('team1') && has('team2')) return ['s', 'b']
  if (has('tournament')) return ['e', 't']
  return []
}

// ─── URL param builders ────────────────────────────────────────────────

/** Name link params — intentionally minimal. All-time view; narrowing
 *  is the job of the letter links. Only gender carries because it's an
 *  invariant of the entity (player/team). */
export function nameParams(filters: FilterParams): Record<string, string> {
  const p: Record<string, string> = {}
  if (filters.gender) p.gender = filters.gender
  return p
}

/** Letter-link params. Carries every field in `FILTER_KEYS` from the
 *  resolved bucket EXCEPT those in the tier's drop list. No hand-listed
 *  per-field logic here — the tier's axis is fully declared in TIER_SPECS,
 *  so any new filter added to FILTER_KEYS rides through automatically.
 *
 *  `swapForTeam`: TeamLink passes the linked team's name. When the linked
 *  team IS the rivalry's `filter_opponent`, we swap so the URL's
 *  `filter_team` matches the linked team (e.g. clicking "Australia" in
 *  an India-vs-Australia rivalry gives you filter_team=Australia). */
export function tierParams(
  bucket: SubscriptBucket,
  tier: SubscriptTier,
  swapForTeam?: string,
): Record<string, string> {
  const { drops } = TIER_SPECS[tier]
  const dropSet = new Set<FilterKey>(drops)
  const shouldSwap = !!(
    swapForTeam
    && bucket.filter_team
    && bucket.filter_opponent
    && swapForTeam === bucket.filter_opponent
  )

  const p: Record<string, string> = {}
  for (const k of FILTER_KEYS) {
    if (dropSet.has(k)) continue
    let value = bucket[k]
    if (shouldSwap) {
      if (k === 'filter_team') value = bucket.filter_opponent
      else if (k === 'filter_opponent') value = bucket.filter_team
    }
    if (value !== null && value !== undefined && value !== '') p[k] = value
  }
  return p
}

/** Same-URL check. When two letters resolve to the same params (e.g. (e)
 *  == (t) when season range is empty), the component hides one to avoid
 *  visual duplication. */
export function sameParams(a: Record<string, string>, b: Record<string, string>): boolean {
  const ak = Object.keys(a).sort()
  const bk = Object.keys(b).sort()
  if (ak.length !== bk.length) return false
  for (const k of ak) if (a[k] !== b[k]) return false
  return true
}

// ─── Tooltip text ──────────────────────────────────────────────────────

/** Human-readable season tag: "2024" if from==to, "2023–2024" if both
 *  set and different, "2023+" if only from, "≤2024" if only to. */
export function seasonTag(
  from: string | null | undefined,
  to: string | null | undefined,
): string {
  if (from && to) return from === to ? from : `${from}–${to}`
  if (from) return `${from}+`
  if (to) return `≤${to}`
  return ''
}

/** Tooltip text per tier. Pulls tournament / season / venue / rivalry
 *  from the bucket so the reader can tell at a glance what scope each
 *  letter will land them in. */
export function tierTooltip(
  bucket: SubscriptBucket,
  tier: SubscriptTier,
  swapForTeam?: string,
): string {
  const season = seasonTag(bucket.season_from, bucket.season_to)
  const atVenue = bucket.filter_venue ? ` at ${bucket.filter_venue}` : ''
  if (tier === 'e') {
    const t = bucket.tournament || 'tournament'
    return season ? `${t} (${season})${atVenue} stats` : `${t}${atVenue} stats`
  }
  if (tier === 't') {
    return `${bucket.tournament || 'tournament'}${atVenue} stats (all editions)`
  }
  // s / b
  let team1 = bucket.filter_team
  let team2 = bucket.filter_opponent
  if (swapForTeam && team1 && team2 && swapForTeam === team2) {
    ;[team1, team2] = [team2, team1]
  }
  const pair = team1 && team2 ? `${team1} vs ${team2}` : 'rivalry'
  if (tier === 's') {
    const t = bucket.tournament
    return season
      ? `${pair}, ${t || 'this series'} (${season})${atVenue} stats`
      : t ? `${pair}, ${t}${atVenue} stats` : `${pair}${atVenue} stats`
  }
  return `${pair}${atVenue} stats (all-time)`
}
