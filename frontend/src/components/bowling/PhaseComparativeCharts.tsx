/**
 * Bowling "By Phase" — per-phase player-vs-cohort comparative charts.
 *
 * Three PerformanceVsCohort panels stacked vertically: Dot %, Strike
 * Rate, and Economy. Same primitive + UX as the batting equivalent,
 * different metrics (and inverted polarity — for bowling, lower SR
 * and economy = better; higher dot% = better).
 *
 * Cohort comes from the existing
 * /scope/averages/players/bowling/by-phase endpoint that already
 * powers the per-tile BaselineChip strip above (no new fetch).
 *
 * User-asked 2026-05-22.
 */

import PerformanceVsCohort, { type PerfEntry } from '../distribution-charts/PerformanceVsCohort'
import { WISDEN_TIER_TINTS } from '../charts/palette'
import type { ScopePlayerBowlingPhase } from '../../types'

interface Props {
  // The bowling /by-phase response carries additional fields beyond
  // the shared PhaseStats interface (economy, runs_conceded, wickets,
  // pp_early / pp_late sub-phases). Accept the raw rows here.
  phaseData: Array<Record<string, any>>
  phaseBaseline: ScopePlayerBowlingPhase[]
}

// Canonical phase order: powerplay → middle → death. Sub-phases
// (pp_early, pp_late) live in the tile grid above; the comparative
// charts collapse to the three main buckets that cohort baselines
// are aggregated at.
const PHASE_BUCKET: Record<string, number> = {
  powerplay: 1, middle: 2, death: 3,
}

function bucketLabel(b: number): string {
  if (b === 1) return 'Powerplay'
  if (b === 2) return 'Middle'
  return 'Death'
}

function phaseTint(b: number): string | null {
  if (b === 1) return WISDEN_TIER_TINTS.sage.bg
  if (b === 3) return WISDEN_TIER_TINTS.ochre.bg
  return null
}

function fmt1(v: number) { return v.toFixed(1) }
function fmt2(v: number) { return v.toFixed(2) }

export default function PhaseComparativeCharts({ phaseData, phaseBaseline }: Props) {
  const baseByBucket = new Map<number, ScopePlayerBowlingPhase>()
  for (const b of phaseBaseline) {
    const bucket = PHASE_BUCKET[b.phase] ?? b.phase_bucket
    if (bucket) baseByBucket.set(bucket, b)
  }

  // Build entries only for the three main phases (skip pp_early /
  // pp_late which the tile grid breaks out separately).
  const mainPhases = phaseData.filter(p => PHASE_BUCKET[p.phase] !== undefined)

  function buildEntries(
    getPlayer: (p: Record<string, any>) => number | null,
    getCohort: (b: ScopePlayerBowlingPhase) => number | null,
    metricLabel: string,
    formatVal: (v: number) => string,
  ): PerfEntry[] {
    return mainPhases.map(p => {
      const bucket = PHASE_BUCKET[p.phase] ?? 0
      const pv = getPlayer(p)
      const baseRow = baseByBucket.get(bucket)
      const cv = baseRow ? getCohort(baseRow) : null
      return {
        bucket,
        playerValue: pv,
        cohortValue: cv,
        faded: (p.balls ?? 0) === 0,
        tooltip: pv != null && cv != null
          ? `${bucketLabel(bucket)}: ${metricLabel} ${formatVal(pv)} · cohort ${formatVal(cv)}`
          : `${bucketLabel(bucket)}: no data`,
      }
    })
  }

  const dotEntries = buildEntries(
    p => p.dot_pct ?? null,
    b => b.dot_pct ?? null,
    'Dot %', fmt1,
  )
  const srEntries = buildEntries(
    p => p.strike_rate ?? null,
    b => b.strike_rate ?? null,
    'SR', fmt2,
  )
  const econEntries = buildEntries(
    p => p.economy ?? null,
    b => b.economy ?? null,
    'Econ', fmt2,
  )
  // Boundaries conceded per over. Player: (fours + sixes) / (balls/6).
  // Cohort: boundary_pct × 6 / 100 (boundary_pct = boundaries/balls × 100).
  // Both denominate by legal balls so DLS-truncated innings stay
  // symmetric. User-asked 2026-05-22 follow-up.
  const bpoEntries = buildEntries(
    p => (p.balls && p.balls > 0 ? ((p.fours ?? 0) + (p.sixes ?? 0)) / (p.balls / 6) : null),
    b => (b.boundary_pct != null ? (b.boundary_pct * 6) / 100 : null),
    'Bdys/over', fmt2,
  )

  return (
    <section
      className="wisden-phase-comparative"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem', marginTop: '1.6rem' }}
    >
      <PerformanceVsCohort
        entries={dotEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Dot % by phase"
        yLabel="% of legal balls"
        yFmt={fmt1}
        cohortExplainer="Green tick = average dot % in this phase across every bowler in the FilterBar scope. Higher is better — more dots starves the batting side."
        height={110}
      />
      <PerformanceVsCohort
        entries={srEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Strike rate by phase"
        yLabel="balls / wicket"
        yFmt={fmt2}
        cohortExplainer="Green tick = average bowling strike rate (balls per wicket) in this phase across every bowler in the FilterBar scope. Lower is better."
        height={110}
      />
      <PerformanceVsCohort
        entries={econEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Economy by phase"
        yLabel="runs / over"
        yFmt={fmt2}
        cohortExplainer="Green tick = average economy rate in this phase across every bowler in the FilterBar scope. Lower is better."
        height={110}
      />
      <PerformanceVsCohort
        entries={bpoEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Boundaries conceded per over by phase"
        yLabel="(4s + 6s) / over"
        yFmt={fmt2}
        cohortExplainer="Green tick = average boundaries conceded per over in this phase across every bowler in the FilterBar scope. Lower is better — cheaper bowlers concede fewer."
        height={110}
      />
    </section>
  )
}
