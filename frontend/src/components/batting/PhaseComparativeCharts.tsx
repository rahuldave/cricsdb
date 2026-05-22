/**
 * By Phase — per-phase player-vs-cohort comparative charts.
 *
 * Three PerformanceVsCohort panels stacked vertically: Strike Rate,
 * Dot %, and Boundaries per Over. Same primitive as the By Position
 * tab, with 3 phase buckets (powerplay / middle / death) instead of
 * 10 position buckets. Cohort overlay uses the position-flat
 * /scope/averages/players/batting/by-phase endpoint that already
 * powers the per-tile BaselineChip strip above.
 *
 * Boundaries-per-over is derived (not on the payload): player =
 * boundaries / overs-in-phase, cohort = boundary_pct × 6 / 100. Both
 * use legal balls so the denominators are DLS-safe by construction.
 *
 * Spec / context: internal_docs/spec-mix-and-performance-charts.md
 * §M2 pattern, applied to the phase axis. User-asked 2026-05-22.
 */

import PerformanceVsCohort, { type PerfEntry } from '../distribution-charts/PerformanceVsCohort'
import { WISDEN_TIER_TINTS } from '../charts/palette'
import type { PhaseStats, ScopePlayerBattingPhase } from '../../types'

interface Props {
  phaseData: PhaseStats[]
  phaseBaseline: ScopePlayerBattingPhase[]
}

// Canonical phase order: powerplay → middle → death.
const PHASE_BUCKET: Record<string, number> = {
  powerplay: 1, middle: 2, death: 3,
  // Player-side rows arrive title-cased; map both.
  Powerplay: 1, Middle: 2, Death: 3,
}

function bucketLabel(b: number): string {
  if (b === 1) return 'Powerplay'
  if (b === 2) return 'Middle'
  return 'Death'
}

// Phase tints — light sage for powerplay/death (high-attention),
// neutral middle. Mirrors colors.md tier-tint convention so the
// reader's eye groups the same phases across charts.
function phaseTint(b: number): string | null {
  if (b === 1) return WISDEN_TIER_TINTS.sage.bg
  if (b === 3) return WISDEN_TIER_TINTS.ochre.bg
  return null
}

function fmt1(v: number) { return v.toFixed(1) }
function fmt2(v: number) { return v.toFixed(2) }

export default function PhaseComparativeCharts({ phaseData, phaseBaseline }: Props) {
  // Build a baseline lookup keyed by phase bucket so we can join the
  // player's per-phase row to the cohort's row case-insensitively
  // (player rows are title-cased, cohort rows lowercase).
  const baseByBucket = new Map<number, ScopePlayerBattingPhase>()
  for (const b of phaseBaseline) {
    const bucket = PHASE_BUCKET[b.phase] ?? b.phase_bucket
    if (bucket) baseByBucket.set(bucket, b)
  }

  // Common entry builder per metric. Each phase becomes a perf-entry
  // (player bar + cohort tick at the same bucket).
  function buildEntries(
    getPlayer: (p: PhaseStats) => number | null,
    getCohort: (b: ScopePlayerBattingPhase) => number | null,
    metricLabel: string,
    formatVal: (v: number) => string,
  ): PerfEntry[] {
    return phaseData.map(p => {
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

  const srEntries = buildEntries(
    p => p.strike_rate ?? null,
    b => b.strike_rate ?? null,
    'SR', fmt2,
  )
  const dotEntries = buildEntries(
    p => p.dot_pct ?? null,
    b => b.dot_pct ?? null,
    'Dot %', fmt1,
  )
  // Boundaries per over: player = (4s + 6s) / (balls/6), cohort =
  // boundary_pct (= boundaries/balls × 100) × 6 / 100. Both
  // denominate by legal balls so DLS-truncated innings stay symmetric.
  const bpoEntries = buildEntries(
    p => (p.balls && p.balls > 0 ? (p.fours + p.sixes) / (p.balls / 6) : null),
    b => (b.boundary_pct != null ? (b.boundary_pct * 6) / 100 : null),
    'Boundaries/over', fmt2,
  )

  return (
    <section
      className="wisden-phase-comparative"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem', marginTop: '1.6rem' }}
    >
      <PerformanceVsCohort
        entries={srEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Strike rate by phase"
        yLabel="runs / 100 balls"
        yFmt={fmt2}
        cohortExplainer="Green tick = average strike rate in this phase across every batter in the FilterBar scope."
        height={110}
      />
      <PerformanceVsCohort
        entries={dotEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Dot % by phase"
        yLabel="% of legal balls"
        yFmt={fmt1}
        cohortExplainer="Green tick = average dot % in this phase across every batter in the FilterBar scope. Lower is better — fewer dots means rotating the strike more."
        height={110}
      />
      <PerformanceVsCohort
        entries={bpoEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Boundaries per over by phase"
        yLabel="4s + 6s / over"
        yFmt={fmt2}
        cohortExplainer="Green tick = average boundaries per over in this phase across every batter in the FilterBar scope."
        height={110}
      />
    </section>
  )
}
