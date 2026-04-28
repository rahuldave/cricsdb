import type { ScopeAverageProfile } from '../../types'
import { STAT_ROWS_BY_DISCIPLINE, type TeamDiscipline } from './teamUtils'

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
  // Same subgrid shape as TeamSummaryRow — section spans (1+statRows)
  // tracks; the dl spans statRows. The avg col's section-head doesn't
  // render the "(open ↗)" link (no team page exists for "average team")
  // but the row track is sized to the parent grid's natural max content
  // height across columns, so the team col's link line determines the
  // shared row height. No height-matching hacks needed.
  const statRows = STAT_ROWS_BY_DISCIPLINE[discipline]
  const sectionRows = 1 + statRows

  return (
    <section
      className="wisden-player-section"
      style={{
        display: 'grid',
        gridTemplateRows: 'subgrid',
        gridRow: `span ${sectionRows}`,
      }}
    >
      <div className="wisden-player-section-head">
        <h3 className="wisden-player-section-label">{LABEL[discipline]}</h3>
      </div>
      {placeholder ? (
        <div
          className="wisden-empty-compare"
          style={{ gridRow: `span ${statRows}` }}
        >
          — no {discipline} in scope —
        </div>
      ) : (
        renderStats(discipline, profile, statRows)
      )}
    </section>
  )
}

function renderStats(
  discipline: TeamDiscipline,
  profile: ScopeAverageProfile,
  statRows: number,
) {
  const stats = statsFor(discipline, profile)
  if (!stats) return null
  return (
    <dl
      className="wisden-player-compact"
      style={{
        display: 'grid',
        gridTemplateRows: 'subgrid',
        gridRow: `span ${statRows}`,
      }}
    >
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
    // Two-row layout (spec-avg-column-per-innings.md Commit 5):
    // pool row blank on avg col; /inn row carries the per-innings
    // value (already per-innings post-Commit 2).
    return [
      ['Economy',         fmt(b.economy)],
      ['SR',              fmt(b.strike_rate)],
      ['Dot %',           b.dot_pct == null ? '-' : `${b.dot_pct.toFixed(1)}`],
      // "Avg opposition total" is per-team-vs-opponent — not
      // meaningful for the league average (would equal the league's
      // own innings total). Render dash.
      ['Avg opp. total',  '-'],
      ['Wickets',         '—'],
      ['Wickets/inn',     fmt(b.wickets)],
    ]
  }
  if (discipline === 'fielding') {
    const f = profile.fielding
    if (!f) return null
    // Two-row layout: pool row blank, /inn row carries per-innings
    // value (already per-innings post-Commit 2 — `f.catches` is the
    // per-fielding-innings rate, identical to f.catches_per_match
    // post-halve).
    return [
      ['Catches',        '—'],
      ['Catches/inn',    fmt(f.catches_per_match)],
      ['Stumpings',      '—'],
      ['Stumpings/inn',  fmt(f.stumpings_per_match)],
      ['Run-outs',       '—'],
      ['Run-outs/inn',   fmt(f.run_outs_per_match)],
    ]
  }
  // partnerships — two-row layout for 50+/100+.
  const p = profile.partnerships
  if (!p) return null
  return [
    ['Highest',     p.highest?.runs ?? '-'],
    ['50+',         '—'],
    ['50+/inn',     fmt(p.count_50_plus)],
    ['100+',        '—'],
    ['100+/inn',    fmt(p.count_100_plus)],
    ['Avg',         p.avg_runs == null ? '-' : p.avg_runs.toFixed(1)],
    // No single "best pair" for the league average — there's no
    // canonical pair identity at scope level. Stacked-row layout
    // ensures both cols allocate the same vertical space here.
    ['Best pair',   '—'],
  ]
}
