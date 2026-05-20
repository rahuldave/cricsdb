import { Link } from 'react-router-dom'
import StatCard from '../StatCard'
import type { PlayerProfile, FilterParams } from '../../types'
import {
  hasBatting, hasBowling, hasFielding, hasKeeping, carryFilters,
} from './roleUtils'

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
      {stats.map(([label, value]) => (
        <div key={label} className="wisden-player-compact-row">
          <dt>{label}</dt>
          <dd className="num">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function compactStatsFor(
  discipline: Discipline, profile: PlayerProfile,
): [string, string | number][] | null {
  if (discipline === 'batting') {
    const b = profile.batting; if (!b) return null
    return [
      ['Runs',  (b.runs.value ?? 0).toLocaleString()],
      ['Avg',   fmt(b.average.value)],
      ['SR',    fmt(b.strike_rate.value)],
      ['100s',  b.hundreds.value ?? 0],
      ['50s',   b.fifties.value ?? 0],
      ['HS',    b.highest_score],
    ]
  }
  if (discipline === 'bowling') {
    const b = profile.bowling; if (!b) return null
    return [
      ['Wickets', b.wickets.value ?? 0],
      ['Avg',     fmt(b.average.value)],
      ['Econ',    fmt(b.economy.value)],
      ['SR',      fmt(b.strike_rate.value)],
    ]
  }
  if (discipline === 'fielding') {
    const f = profile.fielding; if (!f) return null
    return [
      ['Catches',   f.catches.value ?? 0],
      ['Stumpings', f.stumpings.value ?? 0],
      ['Run-outs',  f.run_outs.value ?? 0],
      ['Total',     f.total_dismissals.value ?? 0],
    ]
  }
  const k = profile.keeping; if (!k) return null
  return [
    ['Innings kept', k.innings_kept.value ?? 0],
    ['Stumpings',    k.stumpings.value ?? 0],
    ['Catches',      k.keeping_catches.value ?? 0],
    ['Byes',         k.byes_conceded.value ?? 0],
    ['Byes / inn',   fmt(k.byes_per_innings.value)],
  ]
}

function renderCards(discipline: Discipline, profile: PlayerProfile) {
  if (discipline === 'batting') {
    const b = profile.batting
    if (!b) return null
    return (
      <div className="wisden-statrow cols-5" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
        <StatCard label="Runs"  value={b.runs.value} />
        <StatCard label="Avg"   value={fmt(b.average.value)} />
        <StatCard label="SR"    value={fmt(b.strike_rate.value)} />
        <StatCard label="100s"  value={b.hundreds.value} />
        <StatCard label="50s"   value={b.fifties.value} />
        <StatCard label="HS"    value={b.highest_score} />
      </div>
    )
  }

  if (discipline === 'bowling') {
    const b = profile.bowling
    if (!b) return null
    return (
      <div className="wisden-statrow">
        <StatCard label="Wickets" value={b.wickets.value ?? 0} />
        <StatCard label="Avg"     value={fmt(b.average.value)} />
        <StatCard label="Econ"    value={fmt(b.economy.value)} />
        <StatCard label="SR"      value={fmt(b.strike_rate.value)} />
      </div>
    )
  }

  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return null
    return (
      <div className="wisden-statrow">
        <StatCard label="Catches"    value={f.catches.value ?? 0} />
        <StatCard label="Stumpings"  value={f.stumpings.value ?? 0} />
        <StatCard label="Run-outs"   value={f.run_outs.value ?? 0} />
        <StatCard label="Total"      value={f.total_dismissals.value ?? 0} />
      </div>
    )
  }

  // keeping
  const k = profile.keeping
  if (!k) return null
  return (
    <div className="wisden-statrow cols-5">
      <StatCard label="Innings kept" value={k.innings_kept.value ?? 0} />
      <StatCard label="Stumpings"    value={k.stumpings.value ?? 0} />
      <StatCard label="Catches"      value={k.keeping_catches.value ?? 0} />
      <StatCard label="Byes"         value={k.byes_conceded.value ?? 0} />
      <StatCard label="Byes / inn"   value={fmt(k.byes_per_innings.value)} />
    </div>
  )
}
