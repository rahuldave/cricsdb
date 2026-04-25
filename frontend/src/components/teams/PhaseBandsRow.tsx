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

export default function PhaseBandsRow({ profile, discipline, placeholder = false }: Props) {
  if (placeholder) return null
  const phases = extractPhases(profile, discipline)
  if (!phases || phases.length === 0) return null

  const ORDER = ['powerplay', 'middle', 'death']
  const sorted = [...phases].sort(
    (a, b) => ORDER.indexOf(a.phase) - ORDER.indexOf(b.phase),
  )

  return (
    <dl className="wisden-player-compact wisden-phase-bands">
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
        return (
          <div key={p.phase} className="wisden-player-compact-row">
            <dt>{label} Econ</dt>
            <dd className="num">
              {fmt2(rv(p.economy))}
              <span style={{ fontSize: '0.75em', marginLeft: '0.4rem' }}>
                <MetricDelta env={env(p.economy)} />
              </span>
              <span style={{ opacity: 0.55, marginLeft: '0.4rem', fontSize: '0.85em' }}>
                · w {p.wickets ?? 0} / d {fmt1(rv(p.dot_pct))}%
              </span>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
