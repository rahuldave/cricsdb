import type { TeamProfile, ScopeAverageProfile, TeamBattingPhase, TeamBowlingPhase } from '../../types'

interface Props {
  /** Either a team profile or the scope-average profile — both have
   *  the same band shape via parallel by-phase endpoints. */
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

/** Read the by-phase array from either profile shape. Team profile
 *  uses `batting_by_phase: { phases: [...] }`; scope-avg uses
 *  `batting_by_phase: { by_phase: [...] }`. Normalise here. */
function extractPhases(
  profile: TeamProfile | ScopeAverageProfile,
  discipline: 'batting' | 'bowling',
): (TeamBattingPhase | TeamBowlingPhase)[] | null {
  const obj = discipline === 'batting' ? profile.batting_by_phase : profile.bowling_by_phase
  if (!obj) return null
  // Team endpoints return { phases: [...] }, scope-avg returns
  // { by_phase: [...] }. Both paths flatten here.
  const o = obj as { phases?: (TeamBattingPhase | TeamBowlingPhase)[]; by_phase?: (TeamBattingPhase | TeamBowlingPhase)[] }
  return o.phases ?? o.by_phase ?? null
}

export default function PhaseBandsRow({ profile, discipline, placeholder = false }: Props) {
  if (placeholder) {
    return null
  }
  const phases = extractPhases(profile, discipline)
  if (!phases || phases.length === 0) return null

  // Force PP / Mid / Death order — backend already returns them in
  // this order but defensive against future re-ordering.
  const ORDER = ['powerplay', 'middle', 'death']
  const sorted = [...phases].sort(
    (a, b) => ORDER.indexOf(a.phase) - ORDER.indexOf(b.phase),
  )

  return (
    <dl className="wisden-player-compact wisden-phase-bands">
      {sorted.map(p => {
        const label = PHASE_LABEL[p.phase] ?? p.phase
        if (discipline === 'batting') {
          const b = p as TeamBattingPhase
          return (
            <div key={p.phase} className="wisden-player-compact-row">
              <dt>{label} RR</dt>
              <dd className="num">
                {fmt2(b.run_rate)}
                <span style={{ opacity: 0.55, marginLeft: '0.4rem', fontSize: '0.85em' }}>
                  · b{fmt1(b.boundary_pct)}% / d{fmt1(b.dot_pct)}%
                </span>
              </dd>
            </div>
          )
        }
        const b = p as TeamBowlingPhase
        return (
          <div key={p.phase} className="wisden-player-compact-row">
            <dt>{label} Econ</dt>
            <dd className="num">
              {fmt2(b.economy)}
              <span style={{ opacity: 0.55, marginLeft: '0.4rem', fontSize: '0.85em' }}>
                · w{b.wickets} / d{fmt1(b.dot_pct)}%
              </span>
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
