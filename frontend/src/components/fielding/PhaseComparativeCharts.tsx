/**
 * Fielding "By Phase" — per-phase catches and run-outs charts.
 * Four PerformanceVsCohort panels stacked vertically:
 *   1. Catches by phase            — raw counts, no cohort.
 *   2. Catches per match by phase  — rate vs cohort tick.
 *   3. Run-outs by phase           — raw counts, no cohort.
 *   4. Run-outs per match by phase — rate vs cohort tick.
 *
 * Cohort comes from the existing
 * /scope/averages/players/fielding/by-phase endpoint that already
 * powers the per-tile chip strip above (no new fetch). The keeper /
 * outfielder partition is automatic on the cohort side via the
 * baseline rows.
 *
 * User-asked 2026-05-22 (catches charts) + follow-up (run-outs).
 */

import PerformanceVsCohort, { type PerfEntry } from '../distribution-charts/PerformanceVsCohort'
import { WISDEN_TIER_TINTS } from '../charts/palette'
import type { FieldingPhase, ScopePlayerFieldingPhase } from '../../types'

interface Props {
  phaseData: FieldingPhase[]
  phaseBaseline: ScopePlayerFieldingPhase[]
}

const PHASE_BUCKET: Record<string, number> = {
  powerplay: 1, middle: 2, death: 3,
  Powerplay: 1, Middle: 2, Death: 3,
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

function fmt0(v: number) { return v.toFixed(0) }
function fmt3(v: number) { return v.toFixed(3) }

export default function PhaseComparativeCharts({ phaseData, phaseBaseline }: Props) {
  if (!phaseData || phaseData.length === 0) return null

  const baseByBucket = new Map<number, ScopePlayerFieldingPhase>()
  for (const b of phaseBaseline) {
    const bucket = PHASE_BUCKET[b.phase] ?? b.phase_bucket
    if (bucket) baseByBucket.set(bucket, b)
  }

  const orderedPhases = phaseData
    .filter(p => PHASE_BUCKET[p.phase] !== undefined)
    .sort((a, b) => (PHASE_BUCKET[a.phase] ?? 99) - (PHASE_BUCKET[b.phase] ?? 99))

  // Per-metric volume + rate builders to keep the four chart series
  // declarations symmetric below.
  function volEntries(getCount: (p: FieldingPhase) => number, label: string): PerfEntry[] {
    return orderedPhases.map(p => {
      const bucket = PHASE_BUCKET[p.phase] ?? 0
      const v = getCount(p)
      return {
        bucket,
        playerValue: v,
        cohortValue: null,
        faded: false,
        tooltip: `${bucketLabel(bucket)}: ${v} ${label}`,
      }
    })
  }
  function rateEntries(
    getPlayerRate: (p: FieldingPhase) => number | null,
    getCohortRate: (b: ScopePlayerFieldingPhase) => number | null,
    label: string,
  ): PerfEntry[] {
    return orderedPhases.map(p => {
      const bucket = PHASE_BUCKET[p.phase] ?? 0
      const playerRate = getPlayerRate(p)
      const base = baseByBucket.get(bucket)
      const cohortRate = base ? getCohortRate(base) : null
      return {
        bucket,
        playerValue: playerRate,
        cohortValue: cohortRate,
        faded: !p.matches || p.matches === 0,
        tooltip: playerRate != null && cohortRate != null
          ? `${bucketLabel(bucket)}: ${playerRate.toFixed(3)} ${label} · cohort ${cohortRate.toFixed(3)}`
          : `${bucketLabel(bucket)}: ${playerRate != null ? playerRate.toFixed(3) + ' ' + label : 'no data'}`,
      }
    })
  }

  const catchVol  = volEntries(p => p.catches ?? 0, 'catches')
  const catchRate = rateEntries(
    p => p.catches_per_match ?? (p.matches && p.matches > 0 ? p.catches / p.matches : null),
    b => b.catches_per_match ?? null,
    'c/match',
  )
  const roVol  = volEntries(p => p.run_outs ?? 0, 'run-outs')
  const roRate = rateEntries(
    p => p.run_outs_per_match ?? (p.matches && p.matches > 0 ? p.run_outs / p.matches : null),
    b => b.run_outs_per_match ?? null,
    'ro/match',
  )

  return (
    <section
      className="wisden-phase-comparative"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem', marginTop: '1.6rem' }}
    >
      <PerformanceVsCohort
        entries={catchVol}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Catches by phase"
        yLabel="catches"
        yFmt={fmt0}
        height={110}
      />
      <PerformanceVsCohort
        entries={catchRate}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Catches per match by phase"
        yLabel="catches / match"
        yFmt={fmt3}
        cohortExplainer="Green tick = average catches per match in this phase across the keeper / outfielder partition the player belongs to."
        height={110}
      />
      <PerformanceVsCohort
        entries={roVol}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Run-outs by phase"
        yLabel="run-outs"
        yFmt={fmt0}
        height={110}
      />
      <PerformanceVsCohort
        entries={roRate}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Run-outs per match by phase"
        yLabel="run-outs / match"
        yFmt={fmt3}
        cohortExplainer="Green tick = average run-outs per match in this phase across the keeper / outfielder partition the player belongs to."
        height={110}
      />
    </section>
  )
}
