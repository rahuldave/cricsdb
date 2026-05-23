/**
 * Fielding "By Phase" — per-phase catches (volume) + catches-per-match
 * (rate) charts. User-asked 2026-05-22.
 *
 * Two charts stacked vertically:
 *   1. Catches by phase — raw counts, no cohort comparison (volume).
 *   2. Catches per match by phase — player rate vs cohort tick.
 *
 * Cohort comes from the existing
 * /scope/averages/players/fielding/by-phase endpoint that already
 * powers the per-tile chip strip above (no new fetch). The keeper /
 * outfielder partition is automatic on the cohort side via the
 * baseline rows.
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

  // Chart 1 — Catches by phase (volume). cohortValue null on every
  // entry so PerformanceVsCohort renders just the player bars; no
  // cohort tick is meaningful for a raw count.
  const volEntries: PerfEntry[] = orderedPhases.map(p => {
    const bucket = PHASE_BUCKET[p.phase] ?? 0
    return {
      bucket,
      playerValue: p.catches ?? 0,
      cohortValue: null,
      faded: false,
      tooltip: `${bucketLabel(bucket)}: ${p.catches} catches`,
    }
  })

  // Chart 2 — Catches per match by phase (rate vs cohort).
  // Player.catches_per_match optional on the row; fall back to
  // catches / matches if needed.
  const rateEntries: PerfEntry[] = orderedPhases.map(p => {
    const bucket = PHASE_BUCKET[p.phase] ?? 0
    const playerRate = p.catches_per_match != null
      ? p.catches_per_match
      : (p.matches && p.matches > 0 ? p.catches / p.matches : null)
    const base = baseByBucket.get(bucket)
    const cohortRate = base?.catches_per_match ?? null
    return {
      bucket,
      playerValue: playerRate,
      cohortValue: cohortRate,
      faded: !p.matches || p.matches === 0,
      tooltip: playerRate != null && cohortRate != null
        ? `${bucketLabel(bucket)}: ${playerRate.toFixed(3)} c/match · cohort ${cohortRate.toFixed(3)}`
        : `${bucketLabel(bucket)}: ${playerRate != null ? playerRate.toFixed(3) + ' c/match' : 'no data'}`,
    }
  })

  return (
    <section
      className="wisden-phase-comparative"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem', marginTop: '1.6rem' }}
    >
      <PerformanceVsCohort
        entries={volEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Catches by phase"
        yLabel="catches"
        yFmt={fmt0}
        height={110}
      />
      <PerformanceVsCohort
        entries={rateEntries}
        bucketLabel={bucketLabel}
        phaseTint={phaseTint}
        title="Catches per match by phase"
        yLabel="catches / match"
        yFmt={fmt3}
        cohortExplainer="Green tick = average catches per match in this phase across the keeper / outfielder partition the player belongs to."
        height={110}
      />
    </section>
  )
}
