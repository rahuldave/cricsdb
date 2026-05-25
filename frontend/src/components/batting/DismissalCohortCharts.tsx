/**
 * Dismissals tab — three player-vs-cohort distribution charts.
 *
 * The donut above shows the player's absolute mode breakdown; these
 * normalize so the player can be compared against the scope cohort
 * (every batter at the FilterBar scope), same as the By Over / By
 * Phase tabs. Reuses PerformanceVsCohort (player bar + green cohort
 * tick per bucket).
 *
 * Denominators (user-specified):
 *  - Mode of dismissal: ÷ innings played, with NOT-OUT as its own
 *    modality, so the modalities partition every innings (sums to 1).
 *  - By over / by phase: ÷ out-innings (= total dismissals); not-outs
 *    have no over/phase, so these condition on having been dismissed
 *    (sums to 1).
 *
 * Cohort: pooled scope from /scope/averages/batting/dismissals, scope-
 * aligned with the player's /batters/{id}/dismissals by construction.
 */

import PerformanceVsCohort, { type PerfEntry } from '../distribution-charts/PerformanceVsCohort'
import { WISDEN_TIER_TINTS } from '../charts/palette'
import type { DismissalAnalysis, ScopeDismissals } from '../../types'

interface Props {
  player: DismissalAnalysis
  cohort: ScopeDismissals | null
}

// Canonical batting dismissal modalities, in reading order, plus the
// not-out modality. Rare kinds (hit wicket, obstructing, etc. — ~0.1%
// of the cohort) are intentionally omitted; the seven shown are the
// ones a reader expects and they account for >99.8% of innings.
const KIND_ORDER = ['caught', 'caught and bowled', 'bowled', 'lbw', 'stumped', 'run out'] as const
const MODE_LABELS = [...KIND_ORDER, 'not out']

function modeBucketLabel(b: number): string {
  // 1-indexed into MODE_LABELS.
  const label = MODE_LABELS[b - 1] ?? ''
  // Title-case for display; keep "lbw" upper.
  if (label === 'lbw') return 'LBW'
  return label.replace(/\b\w/g, c => c.toUpperCase())
}

function overBucketLabel(b: number): string {
  return String(b)
}

function phaseBucketLabel(b: number): string {
  return b === 1 ? 'Powerplay' : b === 2 ? 'Middle' : 'Death'
}

// Phase tint so the over chart visually bands powerplay / death,
// matching the By Over tab.
function overPhaseTint(over: number): string | null {
  if (over <= 6) return WISDEN_TIER_TINTS.sage.bg
  if (over >= 16) return WISDEN_TIER_TINTS.ochre.bg
  return null
}
function phaseTint(b: number): string | null {
  if (b === 1) return WISDEN_TIER_TINTS.sage.bg
  if (b === 3) return WISDEN_TIER_TINTS.ochre.bg
  return null
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`

export default function DismissalCohortCharts({ player, cohort }: Props) {
  // --- Mode of dismissal: each modality ÷ innings (not-out included) ---
  const pInn = player.innings || 0
  const cInn = cohort?.innings || 0
  const modeEntries: PerfEntry[] = MODE_LABELS.map((label, i) => {
    const bucket = i + 1
    const pCount = label === 'not out' ? player.not_outs : (player.by_kind[label] ?? 0)
    const cCount = label === 'not out' ? (cohort?.not_outs ?? 0) : (cohort?.by_kind[label] ?? 0)
    const pv = pInn > 0 ? pCount / pInn : null
    const cv = cInn > 0 ? cCount / cInn : null
    return {
      bucket,
      playerValue: pv,
      cohortValue: cv,
      faded: pCount === 0,
      tooltip: `${modeBucketLabel(bucket)}: ${pv != null ? pct(pv) : '—'} of innings`
        + (cv != null ? ` · cohort ${pct(cv)}` : ''),
    }
  })

  // --- By over: dismissals-in-over ÷ out-innings (= total dismissals) ---
  const pTot = player.total_dismissals || 0
  const cTot = cohort?.total_dismissals || 0
  const cohortOverShare = new Map<number, number>()
  if (cohort && cTot > 0) {
    for (const r of cohort.by_over) cohortOverShare.set(r.over_number, r.dismissals / cTot)
  }
  const playerOverByNum = new Map<number, number>()
  for (const r of player.by_over) playerOverByNum.set(r.over_number, r.dismissals)
  const overEntries: PerfEntry[] = Array.from({ length: 20 }, (_, i) => {
    const over = i + 1
    const pCount = playerOverByNum.get(over) ?? 0
    const pv = pTot > 0 ? pCount / pTot : null
    const cv = cohortOverShare.has(over) ? (cohortOverShare.get(over) as number) : null
    return {
      bucket: over,
      playerValue: pv,
      cohortValue: cv,
      faded: pCount === 0,
      tooltip: `Over ${over}: ${pv != null ? pct(pv) : '—'} of dismissals`
        + (cv != null ? ` · cohort ${pct(cv)}` : ''),
    }
  })

  // --- By phase: dismissals-in-phase ÷ out-innings ---
  const PHASES: [string, number][] = [['powerplay', 1], ['middle', 2], ['death', 3]]
  const phaseEntries: PerfEntry[] = PHASES.map(([name, bucket]) => {
    const pCount = player.by_phase[name] ?? 0
    const cCount = cohort?.by_phase[name] ?? 0
    const pv = pTot > 0 ? pCount / pTot : null
    const cv = cohort && cTot > 0 ? cCount / cTot : null
    return {
      bucket,
      playerValue: pv,
      cohortValue: cv,
      faded: pCount === 0,
      tooltip: `${phaseBucketLabel(bucket)}: ${pv != null ? pct(pv) : '—'} of dismissals`
        + (cv != null ? ` · cohort ${pct(cv)}` : ''),
    }
  })

  return (
    <section
      className="wisden-dismissal-cohort"
      style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem', marginTop: '1.6rem' }}
    >
      <PerformanceVsCohort
        entries={modeEntries}
        bucketLabel={modeBucketLabel}
        title="How you get out vs the cohort"
        subtitle="share of innings ending each way (not-out included)"
        yLabel="% of innings"
        yFmt={pct}
        cohortExplainer="Green tick = the same modality's share of innings across every batter in the FilterBar scope."
        height={150}
      />
      <PerformanceVsCohort
        entries={overEntries}
        bucketLabel={overBucketLabel}
        phaseTint={overPhaseTint}
        title="When you get out, by over"
        subtitle="share of dismissals in each over (÷ out-innings)"
        yLabel="% of dismissals"
        yFmt={pct}
        cohortExplainer="Green tick = share of dismissals in this over across every batter in the FilterBar scope."
        height={150}
      />
      <PerformanceVsCohort
        entries={phaseEntries}
        bucketLabel={phaseBucketLabel}
        phaseTint={phaseTint}
        title="When you get out, by phase"
        subtitle="share of dismissals in each phase (÷ out-innings)"
        yLabel="% of dismissals"
        yFmt={pct}
        cohortExplainer="Green tick = share of dismissals in this phase across every batter in the FilterBar scope."
        height={130}
      />
    </section>
  )
}
