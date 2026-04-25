import { Link } from 'react-router-dom'
import type { FilterParams, TeamProfile } from '../../types'
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
      {stats.map(([label, value]) => (
        <div key={label} className="wisden-player-compact-row">
          <dt>{label}</dt>
          <dd className="num">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

// Pull `.value` off an envelope, treating null/undefined as null.
const v = (e: { value: number | null } | null | undefined): number | null =>
  e?.value ?? null

function statsFor(
  discipline: TeamDiscipline, profile: TeamProfile,
): [string, string | number][] | null {
  if (discipline === 'results') {
    const s = profile.summary
    if (!s) return null
    const matches = v(s.matches) ?? 0
    const tossWins = v(s.toss_wins) ?? 0
    const tossPct = matches > 0 ? (tossWins * 100 / matches).toFixed(1) : '-'
    const winPct = v(s.win_pct)
    return [
      ['Matches',     matches.toLocaleString()],
      ['W',           v(s.wins) ?? 0],
      ['L',           v(s.losses) ?? 0],
      ['Win %',       winPct == null ? '-' : winPct.toFixed(1)],
      ['Toss won %',  tossPct],
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
      ['Run rate',        fmt(v(b.run_rate))],
      ['Boundary %',      bound == null ? '-' : bound.toFixed(1)],
      ['Avg 1st-inn',     avg1 == null ? '-' : avg1.toFixed(1)],
      ['Highest',         hi],
      ['100s + 50s',      hundreds + fifties],
    ]
  }
  if (discipline === 'bowling') {
    const b = profile.bowling
    if (!b) return null
    const dotp = v(b.dot_pct)
    const avgOpp = v(b.avg_opposition_total)
    const wkts = v(b.wickets) ?? 0
    return [
      ['Economy',         fmt(v(b.economy))],
      ['SR',              fmt(v(b.strike_rate))],
      ['Dot %',           dotp == null ? '-' : dotp.toFixed(1)],
      ['Avg opp. total',  avgOpp == null ? '-' : avgOpp.toFixed(1)],
      ['Wickets',         wkts.toLocaleString()],
    ]
  }
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return null
    return [
      ['Catches',    v(f.catches) ?? 0],
      ['Stumpings',  v(f.stumpings) ?? 0],
      ['Run-outs',   v(f.run_outs) ?? 0],
      ['C / match',  fmt(v(f.catches_per_match))],
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
    ['Highest',     p.highest?.runs ?? '-'],
    ['50+',         v(p.count_50_plus) ?? 0],
    ['100+',        v(p.count_100_plus) ?? 0],
    ['Avg',         avgRuns == null ? '-' : avgRuns.toFixed(1)],
    ['Best pair',   pairName],
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
