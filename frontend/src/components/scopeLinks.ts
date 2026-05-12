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
  'team_class',
  'series_type',
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

/** Stat discipline used for POV-aware inning phrasing. Null = no
 *  clear discipline; abbreviation falls back to batting-POV defaults. */
export type Discipline = 'batting' | 'bowling' | 'fielding' | null

/**
 * Compact one-line summary of the active scope, suitable for inline
 * display next to a page title. Used to give the user an at-a-glance
 * "what am I looking at" without consulting the status strip.
 *
 * Order: gender · (tournament OR team_type as fallback) · season ·
 * rivalry · venue. Empty axes are skipped; returns "" for an unfiltered
 * scope (caller hides the element).
 *
 * Mirrors the segment ordering of ScopeStatusStrip but in shorter form
 * (no labels, just values, " · " separator). The status strip is the
 * authoritative read; this is the glance read.
 *
 * `opts.discipline` flips the inning POV: 'bowling' or 'fielding'
 * renders `?inning=0/1` as "bowled first/second"; anything else
 * (batting / null / undefined) renders "batted first/second".
 * Source-of-truth for callers is the `useDiscipline()` hook.
 */
export function abbreviateScope(
  scope: Partial<FilterParams>,
  opts?: { discipline?: Discipline },
): string {
  const parts: string[] = []

  if (scope.gender === 'male') parts.push("men's")
  else if (scope.gender === 'female') parts.push("women's")

  if (scope.tournament) parts.push(scope.tournament)
  else if (scope.team_type === 'club') parts.push('club')
  else if (scope.team_type === 'international') parts.push('international')

  const season = seasonTag(scope.season_from, scope.season_to)
  if (season) parts.push(season)

  if (scope.filter_team && scope.filter_opponent) {
    parts.push(`${scope.filter_team} vs ${scope.filter_opponent}`)
  } else if (scope.filter_team) {
    parts.push(scope.filter_team)
  } else if (scope.filter_opponent) {
    parts.push(`vs ${scope.filter_opponent}`)
  }

  if (scope.filter_venue) parts.push(`at ${scope.filter_venue}`)

  if (scope.team_class === 'full_member') parts.push('full members')
  else if (scope.team_class === 'primary_club') parts.push('primary clubs')
  else if (scope.team_class === 'secondary_club') parts.push('secondary clubs')

  if (scope.series_type && scope.series_type !== 'all') {
    const st = scope.series_type
    parts.push(
      st === 'bilateral' || st === 'bilateral_only' ? 'bilateral'
      : st === 'icc' || st === 'tournament_only' ? 'ICC'
      : st === 'club' ? 'club competitions'
      : st,
    )
  }

  // Inning aux — page-local 1st/2nd-innings filter. NOT in
  // FILTER_KEYS (it's an AuxParam, not a FilterBar key) but it's a
  // genuine scope narrowing the user sees, so it belongs in the
  // abbreviation alongside the FilterBar axes. POV-aware: bowling /
  // fielding discipline flips the verb to "bowled first/second" so the
  // subtitle matches the side of the ball the user is reading. See
  // project_inning_pov_conventions for the decision history.
  const bowlPov = opts?.discipline === 'bowling' || opts?.discipline === 'fielding'
  if (scope.inning === '0') parts.push(bowlPov ? 'bowled first' : 'batted first')
  else if (scope.inning === '1') parts.push(bowlPov ? 'bowled second' : 'batted second')

  // Splits Mosaic aux — match-outcome (result) and toss-outcome
  // narrowings from the path team's POV. Same AuxParam treatment
  // as inning. Spec: internal_docs/spec-splits-mosaic.md §2.1.
  if (scope.toss_outcome === 'won') parts.push('won toss')
  else if (scope.toss_outcome === 'lost') parts.push('lost toss')

  if (scope.result === 'won') parts.push('won the game')
  else if (scope.result === 'lost') parts.push('lost the game')
  else if (scope.result === 'tied') parts.push('tied')

  return parts.join(' · ')
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

// ─── Suggested splits — scope-derived navigation hints ─────────────────
//
// Mirror of `api/scope_links.py::suggested_splits`. Walks the active
// scope and emits an ordered list of `(label, params)` pairs — each is
// a one-click navigation hint to a related scope the user is likely
// to want next ("Kohli IPL 2024 vs Kohli all IPL").
//
// Lockstep-tested with the Python implementation against the shared
// fixture at `tests/sanity/scope_splits_fixtures.json`. Every change
// here MUST be mirrored in api/scope_links.py + the fixture.
//
// Spec: internal_docs/spec-distribution-stats.md §8.7.

// Gender only — team_type is a narrowing axis, NOT identity. See the
// Python mirror for the rationale (api/scope_links.py).
const IDENTITY_KEYS_FOR_SPLITS = ['gender'] as const

export interface SplitSuggestion {
  label: string
  params: Record<string, string>
}

function _truthy(v: string | null | undefined): v is string {
  return v !== null && v !== undefined && v !== ''
}

function _identityForSplits(scope: Partial<FilterParams>): Record<string, string> {
  const id: Record<string, string> = {}
  for (const k of IDENTITY_KEYS_FOR_SPLITS) {
    const v = scope[k]
    if (_truthy(v as string | null | undefined)) id[k] = v as string
  }
  return id
}

function _identityWithType(scope: Partial<FilterParams>): Record<string, string> {
  const id = _identityForSplits(scope)
  const tt = scope.team_type
  if (_truthy(tt as string | null | undefined)) id.team_type = tt as string
  return id
}

function _seriesLabel(seriesType: string): string {
  if (seriesType === 'bilateral') return 'bilaterals'
  if (seriesType === 'icc') return 'ICC events'
  if (seriesType === 'club') return 'club competitions'
  return seriesType
}

function _withoutKeys(
  scope: Partial<FilterParams>,
  ...drop: string[]
): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [k, v] of Object.entries(scope)) {
    if (drop.includes(k)) continue
    if (_truthy(v as string | null | undefined)) out[k] = String(v)
  }
  return out
}

export function suggestedSplits(scope: Partial<FilterParams>): SplitSuggestion[] {
  const splits: SplitSuggestion[] = []
  const identity = _identityForSplits(scope)
  const identityWithType = _identityWithType(scope)

  const tournament = _truthy(scope.tournament) ? scope.tournament! : null
  const seriesType = _truthy(scope.series_type) ? scope.series_type! : null
  const teamType = _truthy(scope.team_type) ? scope.team_type! : null
  const seasonFrom = _truthy(scope.season_from) ? scope.season_from! : null
  const seasonTo = _truthy(scope.season_to) ? scope.season_to! : null
  const hasTournament = !!tournament
  const hasSeriesType = !!seriesType
  const hasTeamType = !!teamType
  const hasAnySeason = !!seasonFrom || !!seasonTo

  const opponent = _truthy(scope.filter_opponent) ? scope.filter_opponent! : null
  const venue = _truthy(scope.filter_venue) ? scope.filter_venue! : null

  function seasonParams(): Record<string, string> {
    const p: Record<string, string> = {}
    if (seasonFrom) p.season_from = seasonFrom
    if (seasonTo) p.season_to = seasonTo
    return p
  }

  const seasonLabel = seasonTag(seasonFrom, seasonTo)
  const seasonSuffix = hasAnySeason ? ` in ${seasonLabel}` : ''

  // Four-tier broadening ladder. See api/scope_links.py for the full
  // rationale; behavior is lockstep-tested with the Python mirror via
  // tests/sanity/scope_splits_fixtures.json.

  // T1 — specific (tournament wins; series_type fallback).
  if (hasTournament && hasAnySeason && tournament) {
    const p: Record<string, string> = { ...identity }
    if (hasTeamType) p.team_type = teamType!
    if (hasSeriesType) p.series_type = seriesType!
    p.tournament = tournament
    splits.push({ label: `All ${tournament}`, params: p })
  } else if (hasSeriesType && hasAnySeason && !hasTournament && seriesType) {
    const p: Record<string, string> = { ...identity }
    if (hasTeamType) p.team_type = teamType!
    p.series_type = seriesType
    splits.push({ label: `All ${_seriesLabel(seriesType)}`, params: p })
  }

  // T2 — type-only (drop tournament + series_type; keep team_type + season).
  if (hasTeamType && (hasTournament || hasSeriesType) && teamType) {
    const typeLbl = teamType === 'club' ? 'club' : 'international'
    splits.push({
      label: `All ${typeLbl} cricket${seasonSuffix}`,
      params: { ...identity, team_type: teamType, ...seasonParams() },
    })
  }

  // T3 — all cricket in season (drop type + tournament + series_type).
  if (hasAnySeason && (hasTeamType || hasTournament || hasSeriesType)) {
    splits.push({
      label: `All cricket${seasonSuffix}`,
      params: { ...identity, ...seasonParams() },
    })
  }

  // T4 — all-time.
  if (hasTournament || hasSeriesType || hasTeamType || hasAnySeason) {
    splits.push({ label: 'All-time', params: { ...identity } })
  }

  // Opponent axis (independent — keeps team_type so "vs Australia"
  // reads in the international context the user is in).
  if (opponent) {
    splits.push({
      label: `vs ${opponent}, all-time`,
      params: { ...identityWithType, filter_opponent: opponent },
    })
    splits.push({
      label: 'vs all opponents',
      params: _withoutKeys(scope, 'filter_opponent'),
    })
  }

  // Venue axis (same shape).
  if (venue) {
    splits.push({
      label: `at ${venue}, all-time`,
      params: { ...identityWithType, filter_venue: venue },
    })
    splits.push({
      label: 'at all venues',
      params: _withoutKeys(scope, 'filter_venue'),
    })
  }

  // Gender flip — only on women's scope (men's is the asymmetric default;
  // flipping male → female would zero out most player profiles).
  if (scope.gender === 'female') {
    const flipped: Record<string, string> = {}
    for (const [k, v] of Object.entries(scope)) {
      if (_truthy(v as string | null | undefined)) flipped[k] = String(v)
    }
    flipped.gender = 'male'
    splits.push({ label: "Switch to men's", params: flipped })
  }

  return splits
}
