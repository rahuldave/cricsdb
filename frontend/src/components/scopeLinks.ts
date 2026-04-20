/**
 * Shared scope-link helpers used by PlayerLink and TeamLink.
 *
 * Model
 * -----
 * - **Name link**: identity only (gender; +team_type for TeamLink). See `nameParams`.
 * - **Phrase subscripts**: small-caps descriptive phrases that chain
 *   container + rivalry + season. TeamLink passes `keepRivalry: false`
 *   (destination is a single-team page, so rivalry always drops).
 *   PlayerLink passes `keepRivalry: true` (a player's "vs Opp" axis is
 *   meaningful). See `resolveScopePhrases`.
 *
 * Extensibility
 * -------------
 * Adding a new filter to the FilterBar is ONE edit here: append it to
 * `FILTER_KEYS`. It auto-rides through every phrase URL. Only touch
 * `SOURCE_MAP` if the filter needs a per-row override path.
 *
 * This guarantees no tab falls out of sync when a filter is added — the
 * "explicit, per-page, easy to under-wire" landmine documented in
 * internal_docs/design-decisions.md doesn't reappear on link URLs.
 */
import { createContext, useContext } from 'react'
import type { FilterParams } from '../types'
import { useFilters } from '../hooks/useFilters'

// ─── Filter registry ───────────────────────────────────────────────────
//
// Single source of truth for which FilterBar fields appear in subscript
// link URLs. Every one rides through by default.
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
 *  merged on top. Phrase subscript URLs are this bucket minus whichever
 *  keys the tier wants to drop. */
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

// ─── Name-link params ──────────────────────────────────────────────────

/** Name link params — carries only the entity's identity attributes.
 *  Narrowings (tournament, season, venue, rivalry) are the job of the
 *  phrase subscripts and are intentionally dropped here.
 *
 *  `identityKeys` differs by entity type: players have one identity
 *  attribute (gender); teams have two (gender AND team_type, since
 *  "Australia men's international side" is a distinct entity from
 *  "Australia women" and there is no Australia club side).
 *  PlayerLink uses the default; TeamLink passes ['gender','team_type']. */
export function nameParams(
  filters: FilterParams,
  identityKeys: readonly FilterKey[] = ['gender'],
): Record<string, string> {
  const p: Record<string, string> = {}
  for (const k of identityKeys) {
    const v = filters[k]
    if (v) p[k] = String(v)
  }
  return p
}

// ─── Phrase-based subscript API ────────────────────────────────────────

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

export interface PhraseTier {
  /** Phrase text, e.g. "at T20 World Cup" or "vs Australia" or "at IPL, 2024 vs CSK". */
  label: string
  /** URL params for the destination page (player= / team= is added by the caller). */
  params: Record<string, string>
  /** Full tooltip for hover. */
  tooltip: string
}

/** Generate scope phrases for a link rendered at a given scope.
 *
 * Two call-site flavours, driven by `keepRivalry`:
 *
 *   - `keepRivalry: false` (TeamLink default) — destination is a single-
 *     team page, so the rivalry pair ALWAYS drops from the URL and the
 *     subscript never says "vs X". Up to 2 tiers: container broad +
 *     container narrow-with-season.
 *
 *   - `keepRivalry: true` (PlayerLink) — a player's "vs Opp" axis is
 *     meaningful. Up to 3 tiers when rivalry + tournament + season are
 *     all set: rivalry-only / container+rivalry broad / container+rivalry+season.
 *     Tournament is kept as a container even when the rivalry pair is
 *     present (the rivalry-specific-bilateral-series concern doesn't
 *     apply to a player's own stats — see Series audit, 2026-04-20).
 *
 * Container resolution for TeamLink:
 *   series_type=icc/club + tournament → "at <T>" (tournament kept in URL)
 *   series_type=icc/club + no tournament → "at ICC events" / "in club tournaments"
 *   series_type=bilateral → "in bilaterals" (tournament dropped — bilateral
 *     tournaments are rivalry-specific and don't carry a single-team scope)
 *   series_type unset/all + tournament + no rivalry → "at <T>"
 *   series_type unset/all + rivalry pair set → no container (the tournament,
 *     if any, is likely a rivalry-specific bilateral series)
 *
 * `swapForTeam` is used by TeamLink: when the linked team IS the bucket's
 *   `filter_opponent`, the (rivalry-mode, unused for TeamLink today) swap
 *   orients filter_team to the linked team. PlayerLink doesn't need it —
 *   `rowSubscriptSource` pre-orients the bucket per row.
 *
 * Identity keys (gender, team_type) + filter_venue ride through silently
 * on every tier URL. */
export function resolveScopePhrases(
  bucket: SubscriptBucket,
  options: {
    swapForTeam?: string
    seriesType?: string | null
    /** Preserve rivalry pair in URL + emit "vs <Opp>" phrase (PlayerLink). */
    keepRivalry?: boolean
  } = {},
): PhraseTier[] {
  const seriesType = options.seriesType
  const keepRivalry = options.keepRivalry ?? false
  const hasTournament = !!bucket.tournament
  const hasRivalryPair = !!(bucket.filter_team && bucket.filter_opponent)
  const season = seasonTag(bucket.season_from, bucket.season_to)
  const hasSeason = !!season
  const shouldKeepRivalry = keepRivalry && hasRivalryPair

  // ── Container (tournament/series-type-based) ─────────────────────────
  let containerLabel: string | null = null
  let keepTournamentInUrl = false
  let keepSeriesTypeInUrl = false

  if (seriesType === 'icc' || seriesType === 'club') {
    if (hasTournament) {
      containerLabel = `at ${bucket.tournament}`
      keepTournamentInUrl = true
    } else {
      containerLabel = seriesType === 'icc' ? 'at ICC events' : 'in club tournaments'
      keepSeriesTypeInUrl = true
    }
  } else if (seriesType === 'bilateral') {
    containerLabel = 'in bilaterals'
    keepSeriesTypeInUrl = true
  } else if (hasTournament && (shouldKeepRivalry || !hasRivalryPair)) {
    // TeamLink drops the tournament when rivalry is set (bilateral-series
    // concern). PlayerLink keeps it — "Kohli at IPL vs CSK" is meaningful.
    containerLabel = `at ${bucket.tournament}`
    keepTournamentInUrl = true
  }

  // ── Rivalry phrase ───────────────────────────────────────────────────
  const swap = !!(
    options.swapForTeam
    && bucket.filter_team
    && bucket.filter_opponent
    && options.swapForTeam === bucket.filter_opponent
  )
  let rivalryLabel: string | null = null
  if (shouldKeepRivalry) {
    const opp = swap ? bucket.filter_team : bucket.filter_opponent
    rivalryLabel = `vs ${opp}`
  }

  if (!containerLabel && !rivalryLabel && !hasSeason) return []

  // ── URL param builder ────────────────────────────────────────────────
  const buildParams = (spec: {
    withSeason: boolean; withContainer: boolean; withRivalry: boolean
  }): Record<string, string> => {
    const p: Record<string, string> = {}
    for (const k of FILTER_KEYS) {
      if (!spec.withSeason && (k === 'season_from' || k === 'season_to')) continue
      if (!spec.withRivalry && (k === 'filter_team' || k === 'filter_opponent')) continue
      if (k === 'tournament' && (!spec.withContainer || !keepTournamentInUrl)) continue
      let value: string | null | undefined = bucket[k]
      if (spec.withRivalry && swap) {
        if (k === 'filter_team') value = bucket.filter_opponent
        else if (k === 'filter_opponent') value = bucket.filter_team
      }
      if (value) p[k] = String(value)
    }
    if (spec.withContainer && keepSeriesTypeInUrl && seriesType) p['series_type'] = seriesType
    return p
  }

  // ── Label composer ───────────────────────────────────────────────────
  const joinLabel = (
    container: string | null,
    rivalry: string | null,
    seasonPart: string | null,
  ): string => {
    let base = ''
    if (container) base = seasonPart ? `${container}, ${seasonPart}` : container
    else if (seasonPart) base = `in ${seasonPart}`
    return rivalry ? (base ? `${base} ${rivalry}` : rivalry) : base
  }

  const atVenue = bucket.filter_venue ? ` at ${bucket.filter_venue}` : ''
  const tiers: PhraseTier[] = []

  // Order: NARROWEST FIRST, then widening. The phrase immediately after
  // a stat (e.g. PlayerLink with trailingContent="· 197 runs") must match
  // the stat's scope, otherwise readers mis-attribute the number. After
  // that anchor, subsequent phrases offer step-up broader alternatives.
  //
  // Tier A — narrow: container + rivalry + season
  // Tier B — mid:    container + rivalry (drop season)
  // Tier C — broad:  rivalry alone (drop container + season)
  //
  // TeamLink (keepRivalry: false) collapses to A and B only (no rivalry
  // phrase). Empty axes are skipped, so a rivalry-only page (no
  // container, no season) produces the single rivalry-only phrase via
  // the fallback at the end.

  // Tier A — narrowest (season + whatever else is set).
  if (hasSeason) {
    const label = joinLabel(containerLabel, rivalryLabel, season)
    tiers.push({
      label,
      params: buildParams({
        withSeason: true, withContainer: true, withRivalry: !!rivalryLabel,
      }),
      tooltip: `${label}${atVenue}`,
    })
  }

  // Tier B — container broad (+ rivalry if kept).
  if (containerLabel) {
    const label = joinLabel(containerLabel, rivalryLabel, null)
    tiers.push({
      label,
      params: buildParams({
        withSeason: false, withContainer: true, withRivalry: !!rivalryLabel,
      }),
      tooltip: `${label}, all editions${atVenue}`,
    })
  }

  // Tier C — rivalry alone (drop container + season). Only emitted when
  // there's a narrower tier above it — otherwise the rivalry-only label
  // IS the single tier, added by the fallback below.
  if (rivalryLabel && (containerLabel || hasSeason)) {
    tiers.push({
      label: rivalryLabel,
      params: buildParams({ withSeason: false, withContainer: false, withRivalry: true }),
      tooltip: `${rivalryLabel}, all-time${atVenue}`,
    })
  }

  // Fallback: rivalry alone with nothing to narrow against.
  if (tiers.length === 0 && rivalryLabel) {
    tiers.push({
      label: rivalryLabel,
      params: buildParams({ withSeason: false, withContainer: false, withRivalry: true }),
      tooltip: `${rivalryLabel}, all-time${atVenue}`,
    })
  }

  return tiers
}
