/**
 * ColumnScopeStrip — per-column effective-scope readout under each
 * Compare column's name. Mirrors the global ScopeStatusStrip below
 * the FilterBar (same segLabel / segValue / sep visual primitives)
 * so the user can match a column's scope against the page-wide one
 * at a glance.
 *
 * - Renders for EVERY column (primary, team slot, avg slot) — when a
 *   slot inherits primary fully, its scope strip looks identical to
 *   primary's. Side-by-side that makes "this column matches the
 *   FilterBar" visually obvious.
 * - Overridden segments are prefixed with `✎` (same affordance as the
 *   column-header edit button) and the value is dotted-underlined.
 *   No accent colour — orange/oxblood reads as link.
 * - Wraps naturally; no fixed rectangle. The chip-area subgrid row
 *   sizes to the tallest column's wrapped strip, so columns stay
 *   aligned even when one wraps to 3 lines and another to 1.
 *
 * Spec: user feedback 2026-04-29 (compare-tab "ZERO feedback" issue).
 */
import type { ResolvedSlotScope } from '../../hooks/useCompareSlots'

interface Props {
  scope: ResolvedSlotScope
  overrideKeys: Set<string>
}

interface Segment {
  label: string
  value: string
  overridden: boolean
}

const SERIES_LABEL: Record<string, string> = {
  bilateral: 'bilateral T20Is',
  bilateral_only: 'bilateral T20Is',
  icc: 'ICC events',
  tournament_only: 'ICC events',
  club: 'club tournaments',
}

function formatSeason(from?: string, to?: string): string {
  if (from && to) return from === to ? from : `${from}–${to}`
  if (from) return `${from}+`
  if (to) return `–${to}`
  return ''
}

/** Mirrors the global ScopeStatusStrip's segment building, but feeds
 *  from a single resolved scope (post-override) rather than the
 *  FilterBar + path-identity union. Filter_team/opponent live on
 *  primary only (not slot-overridable), so they don't surface here.
 *
 *  Override-to-empty: when override exists but resolved value is
 *  undefined (the __any__ broaden case), still emit a segment with
 *  value="any" so the user sees what they explicitly broadened. */
export function buildSlotSegments(
  scope: ResolvedSlotScope,
  overrideKeys: Set<string>,
): Segment[] {
  const segs: Segment[] = []
  const ovr = (k: string) => overrideKeys.has(k)

  if (scope.gender) {
    segs.push({
      label: 'Gender',
      value: scope.gender === 'male' ? "men's" : scope.gender === 'female' ? "women's" : scope.gender,
      overridden: false, // gender is bound to primary
    })
  }
  if (scope.team_type) {
    segs.push({
      label: 'Type',
      value: scope.team_type === 'international' ? 'intl' : scope.team_type,
      overridden: false, // team_type is bound to primary
    })
  }

  if (scope.tournament) {
    segs.push({ label: 'Tournament', value: scope.tournament, overridden: ovr('tournament') })
  } else if (ovr('tournament')) {
    segs.push({ label: 'Tournament', value: 'any', overridden: true })
  }

  if (scope.season_from || scope.season_to) {
    const season = formatSeason(scope.season_from, scope.season_to)
    segs.push({
      label: 'Season',
      value: season,
      overridden: ovr('season_from') || ovr('season_to'),
    })
  } else if (ovr('season_from') || ovr('season_to')) {
    segs.push({ label: 'Season', value: 'any', overridden: true })
  }

  if (scope.filter_venue) {
    segs.push({ label: 'Venue', value: scope.filter_venue, overridden: ovr('filter_venue') })
  } else if (ovr('filter_venue')) {
    segs.push({ label: 'Venue', value: 'any', overridden: true })
  }

  if (scope.series_type && scope.series_type !== 'all') {
    segs.push({
      label: 'Series',
      value: SERIES_LABEL[scope.series_type] ?? scope.series_type,
      overridden: ovr('series_type'),
    })
  } else if (ovr('series_type')) {
    segs.push({ label: 'Series', value: 'any', overridden: true })
  }

  if (scope.team_class === 'full_member') {
    segs.push({ label: 'Class', value: 'full members', overridden: ovr('team_class') })
  } else if (scope.team_class === 'primary_club') {
    segs.push({ label: 'Tier', value: 'primary clubs', overridden: ovr('team_class') })
  } else if (scope.team_class === 'secondary_club') {
    segs.push({ label: 'Tier', value: 'secondary clubs', overridden: ovr('team_class') })
  } else if (ovr('team_class')) {
    segs.push({ label: 'Class', value: 'any', overridden: true })
  }

  if (scope.inning === '0') {
    segs.push({ label: 'Innings', value: '1st', overridden: ovr('inning') })
  } else if (scope.inning === '1') {
    segs.push({ label: 'Innings', value: '2nd', overridden: ovr('inning') })
  } else if (ovr('inning')) {
    segs.push({ label: 'Innings', value: 'any', overridden: true })
  }

  // toss_outcome + result are inherited-only aux (never per-slot
  // overridden), so they're never flagged ✎ — but they must surface so
  // the columns' scope strips agree on what's filtered. Spec:
  // spec-compare-toss-result.md §3.
  if (scope.toss_outcome === 'won') {
    segs.push({ label: 'Toss', value: 'won', overridden: false })
  } else if (scope.toss_outcome === 'lost') {
    segs.push({ label: 'Toss', value: 'lost', overridden: false })
  }
  if (scope.result === 'won') {
    segs.push({ label: 'Result', value: 'won', overridden: false })
  } else if (scope.result === 'lost') {
    segs.push({ label: 'Result', value: 'lost', overridden: false })
  } else if (scope.result === 'tied') {
    segs.push({ label: 'Result', value: 'tied/NR', overridden: false })
  }

  return segs
}

export default function ColumnScopeStrip({ scope, overrideKeys }: Props) {
  const segs = buildSlotSegments(scope, overrideKeys)
  if (segs.length === 0) return null
  const hasOverrides = segs.some(s => s.overridden)
  return (
    <div
      className="wisden-col-scope"
      title={
        hasOverrides
          ? '✎ marks fields overridden from the FilterBar above. Click ✎ on the column header to edit.'
          : "This column's effective scope matches the FilterBar."
      }
    >
      {segs.map((s, i) => (
        <span key={`${s.label}-${i}`} className={`wisden-col-scope-seg${s.overridden ? ' is-overridden' : ''}`}>
          {i > 0 && <span className="wisden-col-scope-sep"> · </span>}
          {s.overridden && <span className="wisden-col-scope-edit" aria-hidden>✎ </span>}
          <span className="wisden-col-scope-segLabel">{s.label}:</span>{' '}
          <span className="wisden-col-scope-segValue">{s.value}</span>
        </span>
      ))}
    </div>
  )
}
