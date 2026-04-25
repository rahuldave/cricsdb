import { Link } from 'react-router-dom'
import type { FilterParams, MetricEnvelope, TeamProfile } from '../../types'
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

/** Tiny chip rendered next to a numeric value showing its delta vs
 *  the in-scope league baseline. Color-coded by direction so the
 *  reader doesn't have to remember which way is "good" for each
 *  metric (econ lower = good, RR higher = good, etc.). */
function DeltaChip({ env }: { env: MetricEnvelope | null | undefined }) {
  if (!env || env.delta_pct == null || env.direction == null) return null
  const d = env.delta_pct
  const aligned =
    (env.direction === 'higher_better' && d > 0) ||
    (env.direction === 'lower_better' && d < 0)
  // For lower_better metrics, a negative delta is GOOD — but the
  // arrow shows numerical direction (↑ for positive value vs avg),
  // not goodness. Color carries the goodness.
  const color = d === 0
    ? 'rgb(120,120,120)'
    : aligned ? 'rgb(36,128,68)' : 'rgb(170,52,52)'
  const arrow = d > 0 ? '↑' : d < 0 ? '↓' : '·'
  const sign = d > 0 ? '+' : ''
  const tip = `${env.value} vs scope avg ${env.scope_avg} — ${sign}${d.toFixed(1)}% ${aligned ? '(better)' : '(worse)'}`
  return (
    <span
      title={tip}
      style={{
        fontSize: '0.75em',
        marginLeft: '0.4rem',
        color,
        whiteSpace: 'nowrap',
        fontWeight: 500,
      }}
    >
      {arrow} {sign}{d.toFixed(1)}%
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

const OPEN_TEXT: Record<TeamDiscipline, string> = {
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
          <Link to={deepLink} className="comp-link wisden-player-section-link">
            → {OPEN_TEXT[discipline]}
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
    return [
      ['Economy',         fmt(v(b.economy)),                                       b.economy],
      ['SR',              fmt(v(b.strike_rate)),                                   b.strike_rate],
      ['Dot %',           dotp == null ? '-' : dotp.toFixed(1),                    b.dot_pct],
      ['Avg opp. total',  avgOpp == null ? '-' : avgOpp.toFixed(1),                b.avg_opposition_total],
      ['Wickets',         wkts.toLocaleString(),                                   b.wickets],
    ]
  }
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return null
    return [
      ['Catches',    v(f.catches) ?? 0,                          f.catches],
      ['Stumpings',  v(f.stumpings) ?? 0,                        f.stumpings],
      ['Run-outs',   v(f.run_outs) ?? 0,                         f.run_outs],
      ['C / match',  fmt(v(f.catches_per_match)),                f.catches_per_match],
    ]
  }
  // partnerships
  const p = profile.partnerships
  if (!p) return null
  const pairName = p.best_pair
    ? `${shortName(p.best_pair.batter1.name)} · ${shortName(p.best_pair.batter2.name)}`
    : '-'
  const avgRuns = v(p.avg_runs)
  return [
    ['Highest',     p.highest?.runs ?? '-',                              null],
    ['50+',         v(p.count_50_plus) ?? 0,                             p.count_50_plus],
    ['100+',        v(p.count_100_plus) ?? 0,                            p.count_100_plus],
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
