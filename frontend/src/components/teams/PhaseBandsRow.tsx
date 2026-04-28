import type { CSSProperties } from 'react'
import type {
  TeamProfile, ScopeAverageProfile,
  MetricEnvelope,
} from '../../types'
import MetricDelta from '../MetricDelta'

interface Props {
  /** Either a team profile (envelope-shape phase rows) or the scope-
   *  average profile (flat-shape — no delta-against-itself). */
  profile: TeamProfile | ScopeAverageProfile
  discipline: 'batting' | 'bowling'
  /** Dim placeholder when this column has no data for the discipline.
   *  Mirrors TeamSummaryRow's placeholder behaviour for alignment. */
  placeholder?: boolean
}

const PHASE_LABEL: Record<string, string> = {
  powerplay: 'PP',
  middle:    'Mid',
  death:     'Death',
}

const fmt2 = (v: number | null | undefined) => v == null ? '-' : v.toFixed(2)
const fmt1 = (v: number | null | undefined) => v == null ? '-' : v.toFixed(1)

/** Read either a flat number or a `.value` off an envelope. */
function rv(x: number | MetricEnvelope | null | undefined): number | null {
  if (x == null) return null
  if (typeof x === 'number') return x
  return x.value
}
/** When x is an envelope, return it; otherwise null (no chip). */
function env(x: number | MetricEnvelope | null | undefined): MetricEnvelope | null {
  if (x == null || typeof x === 'number') return null
  return x
}

interface PhaseRow {
  phase: string
  // Either envelope (team side) or number | null (scope side).
  // Use a permissive type at the row level so the renderer can dispatch.
  run_rate?: number | MetricEnvelope | null
  economy?: number | MetricEnvelope | null
  boundary_pct: number | MetricEnvelope | null
  dot_pct: number | MetricEnvelope | null
  wickets_lost?: number
  wickets?: number
}

function extractPhases(
  profile: TeamProfile | ScopeAverageProfile,
  discipline: 'batting' | 'bowling',
): PhaseRow[] | null {
  const obj = discipline === 'batting' ? profile.batting_by_phase : profile.bowling_by_phase
  if (!obj) return null
  const o = obj as { phases?: PhaseRow[]; by_phase?: PhaseRow[] }
  return o.phases ?? o.by_phase ?? null
}

/** Innings count for the per-innings substat divisor. On TeamProfile
 *  it's an envelope (`.value`); on ScopeAverageProfile it's a flat
 *  number (= scope's total innings, NOT the divisor we want — but
 *  we don't need it on the avg side because the avg endpoint already
 *  returns per-innings phase counts after Commit 2). */
function innsCount(
  profile: TeamProfile | ScopeAverageProfile,
  side: 'batting' | 'bowling',
): number | null {
  const sec = side === 'batting' ? profile.batting : profile.bowling
  if (!sec) return null
  const key = side === 'batting' ? 'innings_batted' : 'innings_bowled'
  const f = (sec as unknown as Record<string, unknown>)[key]
  if (f == null) return null
  if (typeof f === 'number') return f
  return (f as MetricEnvelope).value ?? null
}

/** Whether the row's `wickets` field is already per-innings (avg side
 *  post-Commit 2) or pool (team side). Heuristic: if profile has the
 *  envelope shape on innings_*, we're on team side. */
function isTeamSide(profile: TeamProfile | ScopeAverageProfile, side: 'batting' | 'bowling'): boolean {
  const sec = side === 'batting' ? profile.batting : profile.bowling
  if (!sec) return false
  const key = side === 'batting' ? 'innings_batted' : 'innings_bowled'
  const f = (sec as unknown as Record<string, unknown>)[key]
  return f != null && typeof f !== 'number'  // envelope = team side
}

// 3 phase bands: powerplay, middle, death. Constant — fixed by the
// game's structure. Used as the subgrid row span so the dl reserves
// 3 tracks of the parent grid even when this column is in placeholder
// mode (returns an empty dl that still occupies the 3 rows so the
// next discipline's rows align across columns).
const PHASE_BAND_ROWS = 3

const PHASE_BAND_SUBGRID_STYLE: CSSProperties = {
  display: 'grid',
  gridTemplateRows: 'subgrid',
  gridRow: `span ${PHASE_BAND_ROWS}`,
}

export default function PhaseBandsRow({ profile, discipline, placeholder = false }: Props) {
  if (placeholder) {
    // Empty subgrid still reserves 3 row tracks so other columns'
    // phase rows + everything below stays row-aligned.
    return <dl className="wisden-player-compact wisden-phase-bands" style={PHASE_BAND_SUBGRID_STYLE} />
  }
  const phases = extractPhases(profile, discipline)
  if (!phases || phases.length === 0) {
    return <dl className="wisden-player-compact wisden-phase-bands" style={PHASE_BAND_SUBGRID_STYLE} />
  }

  const ORDER = ['powerplay', 'middle', 'death']
  const sorted = [...phases].sort(
    (a, b) => ORDER.indexOf(a.phase) - ORDER.indexOf(b.phase),
  )

  // Bowling phase `· w` substat: per-innings everywhere
  // (spec-avg-column-per-innings.md Commit 5). Team-side divides pool
  // wickets by innings_bowled; avg-side comes through per-innings.
  const teamSide = isTeamSide(profile, discipline)
  const innings = innsCount(profile, discipline)

  return (
    <dl
      className="wisden-player-compact wisden-phase-bands"
      style={PHASE_BAND_SUBGRID_STYLE}
    >
      {sorted.map(p => {
        const label = PHASE_LABEL[p.phase] ?? p.phase
        if (discipline === 'batting') {
          return (
            <div key={p.phase} className="wisden-player-compact-row">
              <dt>{label} RR</dt>
              <dd className="num">
                {fmt2(rv(p.run_rate))}
                <span style={{ fontSize: '0.75em', marginLeft: '0.4rem' }}>
                  <MetricDelta env={env(p.run_rate)} />
                </span>
                <span style={{ opacity: 0.55, marginLeft: '0.4rem', fontSize: '0.85em' }}>
                  · b {fmt1(rv(p.boundary_pct))}% / d {fmt1(rv(p.dot_pct))}%
                </span>
              </dd>
            </div>
          )
        }
        // Bowling phase: render `· w {wickets/inn}/inn` substat.
        const wicketsRaw = p.wickets ?? 0
        const wicketsPerInn = teamSide && innings && innings > 0
          ? Math.round((wicketsRaw / innings) * 100) / 100
          : wicketsRaw  // avg side: already per-innings
        return (
          <div key={p.phase} className="wisden-player-compact-row">
            <dt>{label} Econ</dt>
            <dd className="num">
              {fmt2(rv(p.economy))}
              <span style={{ fontSize: '0.75em', marginLeft: '0.4rem' }}>
                <MetricDelta env={env(p.economy)} />
              </span>
              <span style={{ opacity: 0.55, marginLeft: '0.4rem', fontSize: '0.85em' }}>
                · w {fmt2(wicketsPerInn)}/inn / d {fmt1(rv(p.dot_pct))}%
              </span>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
