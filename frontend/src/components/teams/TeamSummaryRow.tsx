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

function statsFor(
  discipline: TeamDiscipline, profile: TeamProfile,
): [string, string | number][] | null {
  if (discipline === 'results') {
    const s = profile.summary
    if (!s) return null
    const tossPct = s.matches > 0 ? (s.toss_wins * 100 / s.matches).toFixed(1) : '-'
    return [
      ['Matches',     s.matches.toLocaleString()],
      ['W',           s.wins],
      ['L',           s.losses],
      ['Win %',       s.win_pct == null ? '-' : `${s.win_pct.toFixed(1)}`],
      ['Toss won %',  tossPct],
    ]
  }
  if (discipline === 'batting') {
    const b = profile.batting
    if (!b) return null
    const hi = b.highest_total?.runs != null ? b.highest_total.runs.toString() : '-'
    return [
      ['Run rate',        fmt(b.run_rate)],
      ['Boundary %',      b.boundary_pct == null ? '-' : `${b.boundary_pct.toFixed(1)}`],
      ['Avg 1st-inn',     b.avg_1st_innings_total == null ? '-' : b.avg_1st_innings_total.toFixed(1)],
      ['Highest',         hi],
      ['100s + 50s',      b.hundreds + b.fifties],
    ]
  }
  if (discipline === 'bowling') {
    const b = profile.bowling
    if (!b) return null
    return [
      ['Economy',         fmt(b.economy)],
      ['SR',              fmt(b.strike_rate)],
      ['Dot %',           b.dot_pct == null ? '-' : `${b.dot_pct.toFixed(1)}`],
      ['Avg opp. total',  b.avg_opposition_total == null ? '-' : b.avg_opposition_total.toFixed(1)],
      ['Wickets',         b.wickets.toLocaleString()],
    ]
  }
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return null
    return [
      ['Catches',    f.catches],
      ['Stumpings',  f.stumpings],
      ['Run-outs',   f.run_outs],
      ['C / match',  fmt(f.catches_per_match)],
    ]
  }
  // partnerships
  const p = profile.partnerships
  if (!p) return null
  const pairName = p.best_pair
    ? `${shortName(p.best_pair.batter1.name)} · ${shortName(p.best_pair.batter2.name)}`
    : '-'
  return [
    ['Highest',     p.highest?.runs ?? '-'],
    ['50+',         p.count_50_plus],
    ['100+',        p.count_100_plus],
    ['Avg',         p.avg_runs == null ? '-' : p.avg_runs.toFixed(1)],
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
