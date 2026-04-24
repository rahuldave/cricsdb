import type { ScopeAverageProfile } from '../../types'
import type { TeamDiscipline } from './teamUtils'

interface Props {
  discipline: TeamDiscipline
  profile: ScopeAverageProfile
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

export default function AvgSummaryRow({
  discipline, profile, placeholder = false,
}: Props) {
  return (
    <section className="wisden-player-section">
      <div className="wisden-player-section-head">
        <h3 className="wisden-player-section-label">{LABEL[discipline]}</h3>
        {/* No "Open …" link for the average column — there's no
            single-page surface for "average team". */}
      </div>
      {placeholder
        ? <div className="wisden-empty-compare">— no {discipline} in scope —</div>
        : renderStats(discipline, profile)}
    </section>
  )
}

function renderStats(discipline: TeamDiscipline, profile: ScopeAverageProfile) {
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
  discipline: TeamDiscipline, profile: ScopeAverageProfile,
): [string, string | number][] | null {
  // Row LABELS mirror TeamSummaryRow exactly so the avg column lines
  // up vertically with team columns. Where a row doesn't apply to the
  // league-average (Wins, Losses, "Best pair" etc.), value is "-".
  if (discipline === 'results') {
    const s = profile.summary
    if (!s) return null
    const tossPct = s.matches > 0 ? (s.toss_decided * 100 / s.matches).toFixed(1) : '-'
    return [
      ['Matches',     s.matches.toLocaleString()],
      ['W',           '-'],
      ['L',           '-'],
      // Win % isn't meaningful for the league average (collapses to
      // ~50%). Repurpose the slot for the league's bat-first win%
      // signal — same row position, different metric. Tooltip on the
      // header explains.
      ['Win %',       s.bat_first_win_pct == null ? '-' : `${s.bat_first_win_pct.toFixed(1)}`],
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
      // Per-team 100s+50s doesn't translate; show dot % which is the
      // most informative pool-weighted stat in the same row position.
      ['100s + 50s',      '-'],
    ]
  }
  if (discipline === 'bowling') {
    const b = profile.bowling
    if (!b) return null
    return [
      ['Economy',         fmt(b.economy)],
      ['SR',              fmt(b.strike_rate)],
      ['Dot %',           b.dot_pct == null ? '-' : `${b.dot_pct.toFixed(1)}`],
      // "Avg opposition total" is per-team-vs-opponent — not
      // meaningful for the league average (would equal the league's
      // own innings total). Render dash.
      ['Avg opp. total',  '-'],
      ['Wickets',         b.wickets.toLocaleString()],
    ]
  }
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return null
    return [
      ['Catches',    f.catches.toLocaleString()],
      ['Stumpings',  f.stumpings],
      ['Run-outs',   f.run_outs],
      ['C / match',  fmt(f.catches_per_match)],
    ]
  }
  // partnerships
  const p = profile.partnerships
  if (!p) return null
  return [
    ['Highest',     p.highest?.runs ?? '-'],
    ['50+',         p.count_50_plus],
    ['100+',        p.count_100_plus],
    ['Avg',         p.avg_runs == null ? '-' : p.avg_runs.toFixed(1)],
    // No single "best pair" for the league average — there's no
    // canonical pair identity at scope level.
    ['Best pair',   '-'],
  ]
}
