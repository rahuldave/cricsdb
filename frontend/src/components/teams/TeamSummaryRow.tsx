import { Link } from 'react-router-dom'
import type { FilterParams, MetricEnvelope, TeamProfile } from '../../types'
import MetricDelta from '../MetricDelta'
import { carryTeamFilters, type TeamDiscipline } from './teamUtils'

interface Props {
  discipline: TeamDiscipline
  profile: TeamProfile
  team: string
  filters: FilterParams
  /** Dim placeholder when a column has no data for this discipline.
   *  Keeps rows aligned across compare columns. */
  placeholder?: boolean
}

const fmt = (v: number | null | undefined, d = 2) =>
  v == null ? '-' : v.toFixed(d)

/** Compact-cell delta chip for the compare grid — a thin wrapper
 *  around the shared MetricDelta that tightens the styling for
 *  inline use next to a stat value (smaller font, no scope_avg
 *  prefix). The single-team tabs use MetricDelta directly with
 *  withScopeAvg + larger sizing. */
function DeltaChip({ env }: { env: MetricEnvelope | null | undefined }) {
  return (
    <span style={{ fontSize: '0.75em', marginLeft: '0.4rem' }}>
      <MetricDelta env={env} />
    </span>
  )
}

const LABEL: Record<TeamDiscipline, string> = {
  results:      'RESULTS',
  batting:      'BATTING',
  bowling:      'BOWLING',
  fielding:     'FIELDING',
  partnerships: 'PARTNERSHIPS',
}

// Tooltip on the compact "(open ↗)" link — full description without
// the screen real estate. The link text itself is intentionally short
// so the section header stays on ONE line in every column at the
// 13rem mobile column floor; if it wraps, the team col's section-head
// becomes 2 lines tall and the avg col stays 1 line, which misaligns
// inner values within each section (subgrid aligns section boxes,
// not their internal content row-by-row). See iPhone-13 regression
// caught 2026-04-27.
const OPEN_TITLE: Record<TeamDiscipline, string> = {
  results:      'Open team page',
  batting:      'Open Batting tab',
  bowling:      'Open Bowling tab',
  fielding:     'Open Fielding tab',
  partnerships: 'Open Partnerships tab',
}

const TAB_FOR: Record<TeamDiscipline, string | null> = {
  results:      null,
  batting:      'Batting',
  bowling:      'Bowling',
  fielding:     'Fielding',
  partnerships: 'Partnerships',
}

export default function TeamSummaryRow({
  discipline, profile, team, filters, placeholder = false,
}: Props) {
  const qs = new URLSearchParams({ team, ...carryTeamFilters(filters) })
  const tab = TAB_FOR[discipline]
  if (tab) qs.set('tab', tab)
  const deepLink = `/teams?${qs}`

  return (
    <section className="wisden-player-section">
      <div className="wisden-player-section-head">
        <h3 className="wisden-player-section-label">{LABEL[discipline]}</h3>
        {!placeholder && (
          <Link
            to={deepLink}
            className="comp-link wisden-player-section-link"
            title={OPEN_TITLE[discipline]}
          >
            (open ↗)
          </Link>
        )}
      </div>
      {placeholder
        ? <div className="wisden-empty-compare">— no {discipline} in scope —</div>
        : renderStats(discipline, profile)}
    </section>
  )
}

function renderStats(discipline: TeamDiscipline, profile: TeamProfile) {
  const stats = statsFor(discipline, profile)
  if (!stats) return null
  return (
    <dl className="wisden-player-compact">
      {stats.map(([label, value, env]) => (
        <div key={label} className="wisden-player-compact-row">
          <dt>{label}</dt>
          <dd className="num">
            {value}
            <DeltaChip env={env} />
          </dd>
        </div>
      ))}
    </dl>
  )
}

// Pull `.value` off an envelope, treating null/undefined as null.
const v = (e: { value: number | null } | null | undefined): number | null =>
  e?.value ?? null

type Row = [string, string | number, MetricEnvelope | null | undefined]

/** Synthesize a per-innings chip envelope from an existing pool-count
 *  envelope. The pool envelope's `scope_avg` is ALREADY per-innings
 *  (after Commit 2 of spec-avg-column-per-innings.md), so we don't
 *  divide it again — only `value` (team's pool count) gets divided
 *  by the team's innings_count.
 *
 *  Direction is inherited from the source envelope. For absolute-count
 *  metrics with direction=None (catches, wickets, count_50_plus), no
 *  chip arrow renders — but the envelope's scope_avg stays available
 *  for tooltips. */
function perInnings(
  env: MetricEnvelope | null | undefined,
  innings: number | null,
): MetricEnvelope | null {
  if (!env || env.value == null || !innings || innings <= 0) return null
  const value = Math.round((env.value / innings) * 100) / 100
  const avg = env.scope_avg
  const delta = avg && avg !== 0
    ? Math.round(((value - avg) / avg) * 1000) / 10
    : null
  return {
    value,
    scope_avg: avg,
    delta_pct: delta,
    direction: env.direction,
    sample_size: env.sample_size,
  }
}

function statsFor(
  discipline: TeamDiscipline, profile: TeamProfile,
): Row[] | null {
  if (discipline === 'results') {
    const s = profile.summary
    if (!s) return null
    const matches = v(s.matches) ?? 0
    const tossWins = v(s.toss_wins) ?? 0
    const tossPct = matches > 0 ? (tossWins * 100 / matches).toFixed(1) : '-'
    const winPct = v(s.win_pct)
    return [
      ['Matches',     matches.toLocaleString(), s.matches],
      ['W',           v(s.wins) ?? 0,           s.wins],
      ['L',           v(s.losses) ?? 0,         s.losses],
      ['Win %',       winPct == null ? '-' : winPct.toFixed(1), s.win_pct],
      ['Toss won %',  tossPct, null],
    ]
  }
  if (discipline === 'batting') {
    const b = profile.batting
    if (!b) return null
    const hi = b.highest_total?.runs != null ? b.highest_total.runs.toString() : '-'
    const bound = v(b.boundary_pct)
    const avg1 = v(b.avg_1st_innings_total)
    const fifties = v(b.fifties) ?? 0
    const hundreds = v(b.hundreds) ?? 0
    return [
      ['Run rate',        fmt(v(b.run_rate)),                                       b.run_rate],
      ['Boundary %',      bound == null ? '-' : bound.toFixed(1),                   b.boundary_pct],
      ['Avg 1st-inn',     avg1 == null ? '-' : avg1.toFixed(1),                     b.avg_1st_innings_total],
      ['Highest',         hi,                                                       null],
      ['100s + 50s',      hundreds + fifties,                                       null],
    ]
  }
  if (discipline === 'bowling') {
    const b = profile.bowling
    if (!b) return null
    const dotp = v(b.dot_pct)
    const avgOpp = v(b.avg_opposition_total)
    const wkts = v(b.wickets) ?? 0
    // Two-row layout for absolute counts (Wickets) per
    // spec-avg-column-per-innings.md Commit 5: pool count + per-innings
    // rate. Per-innings divisor: bowling.innings_bowled (each match is
    // 1 bowling innings for the team).
    const innBowled = v(b.innings_bowled)
    const wktsPerInn = perInnings(b.wickets, innBowled)
    return [
      ['Economy',         fmt(v(b.economy)),                                       b.economy],
      ['SR',              fmt(v(b.strike_rate)),                                   b.strike_rate],
      ['Dot %',           dotp == null ? '-' : dotp.toFixed(1),                    b.dot_pct],
      ['Avg opp. total',  avgOpp == null ? '-' : avgOpp.toFixed(1),                b.avg_opposition_total],
      ['Wickets',         wkts.toLocaleString(),                                   null],
      ['Wickets/inn',     fmt(wktsPerInn?.value),                                  wktsPerInn],
    ]
  }
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return null
    // Two-row layout per spec-avg-column-per-innings.md Commit 5.
    // Per-innings rate uses the existing *_per_match envelope —
    // numerically identical to "per fielding innings" since each team
    // has 1 fielding innings per match. Just relabeled "/inn".
    return [
      ['Catches',        v(f.catches) ?? 0,                            null],
      ['Catches/inn',    fmt(v(f.catches_per_match)),                  f.catches_per_match],
      ['Stumpings',      v(f.stumpings) ?? 0,                          null],
      ['Stumpings/inn',  fmt(v(f.stumpings_per_match)),                f.stumpings_per_match],
      ['Run-outs',       v(f.run_outs) ?? 0,                           null],
      ['Run-outs/inn',   fmt(v(f.run_outs_per_match)),                 f.run_outs_per_match],
    ]
  }
  // partnerships — two-row layout for 50+ / 100+ counts.
  // Per-innings divisor: batting.innings_batted (each partnership
  // belongs to one batting innings).
  const p = profile.partnerships
  if (!p) return null
  const pairName = p.best_pair
    ? `${shortName(p.best_pair.batter1.name)} · ${shortName(p.best_pair.batter2.name)}`
    : '-'
  const avgRuns = v(p.avg_runs)
  const innBatted = v(profile.batting?.innings_batted)
  const fiftyPerInn = perInnings(p.count_50_plus, innBatted)
  const hundredPerInn = perInnings(p.count_100_plus, innBatted)
  return [
    ['Highest',     p.highest?.runs ?? '-',                              null],
    ['50+',         v(p.count_50_plus) ?? 0,                             null],
    ['50+/inn',     fmt(fiftyPerInn?.value),                             fiftyPerInn],
    ['100+',        v(p.count_100_plus) ?? 0,                            null],
    ['100+/inn',    fmt(hundredPerInn?.value),                           hundredPerInn],
    ['Avg',         avgRuns == null ? '-' : avgRuns.toFixed(1),          p.avg_runs],
    ['Best pair',   pairName,                                            null],
  ]
}

// "Shikhar Dhawan" → "S Dhawan" so two cricsheet names fit a narrow
// compare cell. Cricsheet already abbreviates first names ("RG Sharma")
// so this mostly passes them through — only the occasional full first
// name ("Shikhar Dhawan") gets shortened.
function shortName(name: string | null | undefined): string {
  if (!name) return '-'
  const parts = name.trim().split(/\s+/)
  if (parts.length < 2) return name
  const first = parts[0]
  const rest = parts.slice(1).join(' ')
  // Already abbreviated (e.g. "RG", "SV")? Keep as-is.
  if (first.length <= 3 && /^[A-Z]+$/.test(first)) return name
  return `${first[0]} ${rest}`
}
