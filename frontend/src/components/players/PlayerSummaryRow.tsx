import type React from 'react'
import { Link } from 'react-router-dom'
import StatCard from '../StatCard'
import MetricDelta from '../MetricDelta'
import type {
  PlayerProfile, FilterParams, MetricEnvelope,
  BattingCohortMeta, BowlingCohortMeta, FieldingCohortMeta, KeepingCohortMeta,
} from '../../types'
import {
  hasBatting, hasBowling, hasFielding, hasKeeping, carryFilters,
} from './roleUtils'
import {
  battingCohortTooltip, bowlingCohortTooltip,
  fieldingCohortTooltip, keepingCohortTooltip,
} from './cohortTooltip'

type Discipline = 'batting' | 'bowling' | 'fielding' | 'keeping'

interface Props {
  discipline: Discipline
  profile: PlayerProfile
  playerId: string
  filters: FilterParams
  /** When true, render a dim placeholder in place of the stat cards
   *  (used in compare mode to keep rows visually aligned across
   *  columns). Ignored in single-player mode. */
  placeholder?: boolean
  /** Compact mode renders a label/value list instead of big StatCards.
   *  Used by PlayerCompareGrid where each column is narrow — 6 batting
   *  StatCards overflow a 1/3-width column. */
  compact?: boolean
}

const fmt = (v: number | null | undefined, d = 2) =>
  v == null ? '-' : v.toFixed(d)

const DISCIPLINE_TO_PATH: Record<Discipline, string> = {
  batting:  '/batting',
  bowling:  '/bowling',
  fielding: '/fielding',
  keeping:  '/fielding',   // keeping lives on the fielding page as a tab
}

const DISCIPLINE_LABEL: Record<Discipline, string> = {
  batting:  'BATTING',
  bowling:  'BOWLING',
  fielding: 'FIELDING',
  keeping:  'KEEPING',
}

const OPEN_LABEL: Record<Discipline, string> = {
  batting:  'Open Batting page',
  bowling:  'Open Bowling page',
  fielding: 'Open Fielding page',
  keeping:  'Open Fielding › Keeping',
}

/** Returns true when this discipline has data in scope. Exposed so
 *  the compare grid can decide per-discipline whether to render the
 *  band across all columns or hide it entirely. */
export function disciplineHasData(
  discipline: Discipline, profile: PlayerProfile,
): boolean {
  if (discipline === 'batting')  return hasBatting(profile)
  if (discipline === 'bowling')  return hasBowling(profile)
  if (discipline === 'fielding') return hasFielding(profile)
  return hasKeeping(profile)
}

export default function PlayerSummaryRow({
  discipline, profile, playerId, filters, placeholder = false, compact = false,
}: Props) {
  const deepLinkQs = new URLSearchParams({
    player: playerId, ...carryFilters(filters),
  })
  // Keeping tab is a sub-tab on the fielding page.
  if (discipline === 'keeping') deepLinkQs.set('tab', 'Keeping')
  const deepLink = `${DISCIPLINE_TO_PATH[discipline]}?${deepLinkQs}`

  return (
    <section className="wisden-player-section">
      <div className="wisden-player-section-head">
        <h3 className="wisden-player-section-label">{DISCIPLINE_LABEL[discipline]}</h3>
        {!placeholder && (
          <Link to={deepLink} className="comp-link wisden-player-section-link">
            → {OPEN_LABEL[discipline]}
          </Link>
        )}
      </div>
      {placeholder
        ? <div className="wisden-empty-compare">— no {discipline} in scope —</div>
        : compact
          ? renderCompact(discipline, profile)
          : renderCards(discipline, profile)}
    </section>
  )
}

function renderCompact(discipline: Discipline, profile: PlayerProfile) {
  const stats = compactStatsFor(discipline, profile)
  if (!stats) return null
  return (
    <dl className="wisden-player-compact">
      {stats.map(({ label, value, delta }) => (
        <div key={label} className="wisden-player-compact-row">
          <dt>{label}</dt>
          <dd className="num">
            {value}
            {delta != null && <span style={{ marginLeft: '0.4rem' }}>{delta}</span>}
          </dd>
        </div>
      ))}
    </dl>
  )
}

/** One compact-mode row entry. `delta` is an optional MetricDelta
 *  chip rendered to the right of the value — direction-coloured.
 *  Per spec §3.2: each compare-grid column's baseline is derived
 *  independently from that column's primary (mix vector / partition).
 */
interface CompactStat {
  label: string
  value: React.ReactNode
  delta?: React.ReactNode
}

function compactStatsFor(
  discipline: Discipline, profile: PlayerProfile,
): CompactStat[] | null {
  if (discipline === 'batting') {
    const b = profile.batting; if (!b) return null
    return [
      { label: 'Runs',  value: (b.runs.value ?? 0).toLocaleString() },
      { label: 'Avg',   value: fmt(b.average.value),      delta: <MetricDelta env={b.average} /> },
      { label: 'SR',    value: fmt(b.strike_rate.value),  delta: <MetricDelta env={b.strike_rate} /> },
      { label: '100s',  value: b.hundreds.value ?? 0 },
      { label: '50s',   value: b.fifties.value ?? 0 },
      { label: 'HS',    value: b.highest_score },
    ]
  }
  if (discipline === 'bowling') {
    const b = profile.bowling; if (!b) return null
    return [
      { label: 'Wickets', value: b.wickets.value ?? 0 },
      { label: 'Avg',     value: fmt(b.average.value),      delta: <MetricDelta env={b.average} /> },
      { label: 'Econ',    value: fmt(b.economy.value),      delta: <MetricDelta env={b.economy} /> },
      { label: 'SR',      value: fmt(b.strike_rate.value),  delta: <MetricDelta env={b.strike_rate} /> },
    ]
  }
  if (discipline === 'fielding') {
    const f = profile.fielding; if (!f) return null
    return [
      { label: 'Catches',   value: f.catches.value ?? 0 },
      { label: 'Stumpings', value: f.stumpings.value ?? 0 },
      { label: 'Run-outs',  value: f.run_outs.value ?? 0 },
      { label: 'Total',     value: f.total_dismissals.value ?? 0 },
      { label: 'Dis/M',     value: fmt(f.dismissals_per_match.value, 3),
                            delta: <MetricDelta env={f.dismissals_per_match} /> },
    ]
  }
  const k = profile.keeping; if (!k) return null
  return [
    { label: 'Innings kept', value: k.innings_kept.value ?? 0 },
    { label: 'Stumpings',    value: k.stumpings.value ?? 0 },
    { label: 'Catches',      value: k.keeping_catches.value ?? 0 },
    { label: 'Byes',         value: k.byes_conceded.value ?? 0 },
    { label: 'Byes / inn',   value: fmt(k.byes_per_innings.value) },
  ]
}

/** Render a MetricEnvelope as a StatCard subtitle ready to slot under
 *  the bold value. Tier 2 ("vs base N") + tier 3 (delta chip) auto-
 *  hide when scope_avg/delta_pct are null. */
function baselineSub(
  env: MetricEnvelope | undefined | null,
  cohortTooltip: string | undefined,
  fmtDigits = 2,
): React.ReactNode {
  if (!env) return undefined
  if (env.scope_avg == null && env.delta_pct == null) return undefined
  return (
    <MetricDelta
      env={env}
      withScopeAvg={true}
      label="base"
      fmt={fmtDigits}
      scopeAvgTooltip={cohortTooltip}
    />
  )
}


function renderCards(discipline: Discipline, profile: PlayerProfile) {
  if (discipline === 'batting') {
    const b = profile.batting
    if (!b) return null
    const tt = b.cohort ? battingCohortTooltip(b.cohort as BattingCohortMeta) : undefined
    // Two-row layout (Phase F of spec-player-baseline-parity.md §4.1
    // + Q6 (ii)). Row 1: existing kernel tiles. Row 2: per-innings
    // rate tiles surfacing the Q6 envelopes shipped session 1 in
    // commit 55c890a (boundaries/innings, sixes/innings, fours/
    // innings, milestone-per-innings).
    return (
      <>
        <div className="wisden-statrow cols-6">
          <StatCard label="Runs"  value={b.runs.value} subtitle={baselineSub(b.runs, tt, 0)} />
          <StatCard label="Avg"   value={fmt(b.average.value)} subtitle={baselineSub(b.average, tt, 2)} />
          <StatCard label="SR"    value={fmt(b.strike_rate.value)} subtitle={baselineSub(b.strike_rate, tt, 1)} />
          <StatCard label="100s"  value={b.hundreds.value} subtitle={baselineSub(b.hundreds_per_innings, tt, 3)} />
          <StatCard label="50s"   value={b.fifties.value} subtitle={baselineSub(b.fifties_per_innings, tt, 3)} />
          <StatCard label="HS"    value={b.highest_score} />
        </div>
        <div className="wisden-statrow cols-6">
          <StatCard label="4s/Inn"   value={fmt(b.fours_per_innings.value, 2)}
            subtitle={baselineSub(b.fours_per_innings, tt, 2)} />
          <StatCard label="6s/Inn"   value={fmt(b.sixes_per_innings.value, 2)}
            subtitle={baselineSub(b.sixes_per_innings, tt, 2)} />
          <StatCard label="Bndr/Inn" value={fmt(b.boundaries_per_innings.value, 2)}
            subtitle={baselineSub(b.boundaries_per_innings, tt, 2)} />
          <StatCard label="30s/Inn"  value={fmt(b.thirties_per_innings.value, 3)}
            subtitle={baselineSub(b.thirties_per_innings, tt, 3)} />
          <StatCard label="Dot%"     value={b.dot_pct.value != null ? `${b.dot_pct.value}%` : '-'}
            subtitle={baselineSub(b.dot_pct, tt, 1)} />
          <StatCard label="B/Bndry"  value={fmt(b.balls_per_boundary.value, 2)}
            subtitle={baselineSub(b.balls_per_boundary, tt, 2)} />
        </div>
      </>
    )
  }

  if (discipline === 'bowling') {
    const b = profile.bowling
    if (!b) return null
    const tt = b.cohort ? bowlingCohortTooltip(b.cohort as BowlingCohortMeta) : undefined
    // Six tiles. Phase F adds Wkts/Inn + Maidens/Inn to the existing
    // four (Wickets, Avg, Econ, SR) — Q6 envelopes shipped session 1.
    return (
      <div className="wisden-statrow cols-6">
        <StatCard label="Wickets" value={b.wickets.value ?? 0} />
        <StatCard label="Avg"     value={fmt(b.average.value)} subtitle={baselineSub(b.average, tt, 2)} />
        <StatCard label="Econ"    value={fmt(b.economy.value)} subtitle={baselineSub(b.economy, tt, 2)} />
        <StatCard label="SR"      value={fmt(b.strike_rate.value)} subtitle={baselineSub(b.strike_rate, tt, 2)} />
        <StatCard label="Wkts/Inn"    value={fmt(b.wickets_per_innings.value, 2)}
          subtitle={baselineSub(b.wickets_per_innings, tt, 2)} />
        <StatCard label="Maidens/Inn" value={fmt(b.maidens_per_innings.value, 3)}
          subtitle={baselineSub(b.maidens_per_innings, tt, 3)} />
      </div>
    )
  }

  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return null
    const tt = f.cohort ? fieldingCohortTooltip(f.cohort as FieldingCohortMeta) : undefined
    // Phase F: Catches/Stumpings/Run-outs tiles gain per-match-rate
    // chip subtitles surfacing the envelopes Phase E added to
    // /fielders/{id}/summary. Volume stays bold; rate vs cohort is
    // the chip context. Stumpings chip is suppressed when value=0
    // (non-keeper).
    return (
      <div className="wisden-statrow cols-5">
        <StatCard label="Catches"    value={f.catches.value ?? 0}
          subtitle={baselineSub(f.catches_per_match, tt, 3)} />
        <StatCard label="Stumpings"  value={f.stumpings.value ?? 0}
          subtitle={f.stumpings_per_match.value
            ? baselineSub(f.stumpings_per_match, tt, 3) : undefined} />
        <StatCard label="Run-outs"   value={f.run_outs.value ?? 0}
          subtitle={baselineSub(f.run_outs_per_match, tt, 3)} />
        <StatCard label="Total"      value={f.total_dismissals.value ?? 0} />
        <StatCard label="Dis/Match"  value={fmt(f.dismissals_per_match.value, 3)}
          subtitle={baselineSub(f.dismissals_per_match, tt, 3)} />
      </div>
    )
  }

  // keeping
  const k = profile.keeping
  if (!k) return null
  const tt = k.cohort ? keepingCohortTooltip(k.cohort as KeepingCohortMeta) : undefined
  return (
    <div className="wisden-statrow cols-5">
      <StatCard label="Innings kept" value={k.innings_kept.value ?? 0} />
      <StatCard label="Stumpings"    value={k.stumpings.value ?? 0} />
      <StatCard label="Catches"      value={k.keeping_catches.value ?? 0} />
      <StatCard label="Byes"         value={k.byes_conceded.value ?? 0} />
      <StatCard label="Byes / inn"   value={fmt(k.byes_per_innings.value)}
        subtitle={tt ? <span style={{ opacity: 0.65 }} title={tt}>(keeping cohort)</span> : undefined} />
    </div>
  )
}
