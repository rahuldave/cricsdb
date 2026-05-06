/**
 * Stat strip for the batter Distribution panel — the right-hand
 * column beside the histogram, plus a separate full-width milestone-
 * chips row exported alongside. Spec:
 * internal_docs/spec-distribution-stats.md §9.2.3.
 *
 * The point summaries (Mean / Median / Std / CV / Average) live
 * adjacent to the histogram. Milestone chips (simples + conditionals,
 * 6 total) render as a separate full-width flex-wrap row OUTSIDE the
 * histogram-grid so the panel reads less vertically asymmetric — see
 * MilestoneChipsRow below.
 *
 * Pure presentational — reads `dossier` props only.
 */

import type { DistributionDossier } from '../../types'
import ProbChip from '../distribution/ProbChip'
import { WISDEN_TIER_TINTS } from '../charts/palette'

const T_INDIGO = WISDEN_TIER_TINTS.indigo
const T_SAGE   = WISDEN_TIER_TINTS.sage
const T_OCHRE  = WISDEN_TIER_TINTS.ochre

interface Props {
  dossier: DistributionDossier
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(digits)
}

function StatRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '0.25rem 0' }}>
      <span style={{
        fontFamily: 'var(--serif)', fontStyle: 'italic',
        fontSize: '0.78rem', color: 'var(--ink-faint)',
      }}>{label}</span>
      <span className="num" style={{
        fontFamily: 'var(--serif)',
        fontSize: accent ? '1.15rem' : '1rem',
        fontWeight: accent ? 600 : 500,
        color: 'var(--ink)',
      }}>{value}</span>
    </div>
  )
}

// MilestoneChip removed — replaced by the shared ProbChip component
// at components/distribution/ProbChip.tsx (post-§13 retrofit).
// Single source of truth across batter + bowler panels for
// Wilson-CI tooltip + small-n fade + null handling.

export default function DistributionStatStrip({ dossier }: Props) {
  const { runs, n_innings, n_dismissals } = dossier
  const cv = (runs.mean_per_innings && runs.mean_per_innings > 0 && runs.std !== null)
    ? runs.std / runs.mean_per_innings
    : null

  return (
    <div>
      <StatRow label="Mean / inn" value={fmtNum(runs.mean_per_innings, 1)} />
      <StatRow label="Median" value={fmtNum(runs.median, 0)} accent />
      <StatRow label="Std" value={fmtNum(runs.std, 1)} />
      <StatRow label="CV" value={fmtNum(cv, 2)} accent />
      <StatRow label="Average" value={fmtNum(runs.average, 2)} />
      <div style={{
        fontFamily: 'var(--serif)', fontStyle: 'italic',
        fontSize: '0.7rem', color: 'var(--ink-faint)',
        textAlign: 'right', marginTop: '0.25rem',
      }}>
        {n_innings} inns · {n_dismissals} outs · {n_innings - n_dismissals} not out
      </div>
    </div>
  )
}

/**
 * Full-width milestone-probability chip row. Renders all six
 * probabilities (4 simples + 2 conditionals) in a single
 * flex-wrap container so on wide viewports they sit on one line
 * across the panel, and on narrow viewports they wrap naturally.
 * Order: simples (P(≤10), P(≥30), P(≥50), P(≥100)) first,
 * conditionals (P(≥50│≥30), P(≥70│≥50)) last.
 */
export function MilestoneChipsRow({ dossier }: Props) {
  const { milestones } = dossier
  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      gap: '0.35rem',
      marginTop: '0.85rem',
    }}>
      {/* Runs palette: 0-9 = failure (indigo) / 10-49 = building
          (sage) / 50+ = impact (ochre). Conditionals reach the
          impact tier (50+ / 70+) so they're ochre. */}
      <ProbChip label="P(≤10)"     record={milestones.p_failure_10}  tint={T_INDIGO} />
      <ProbChip label="P(≥30)"     record={milestones.p_30_plus}     tint={T_SAGE} />
      <ProbChip label="P(≥50)"     record={milestones.p_50_plus}     tint={T_OCHRE} />
      <ProbChip label="P(≥100)"    record={milestones.p_100_plus}    tint={T_OCHRE} />
      <ProbChip label="P(≥50│≥30)" record={milestones.p_50_given_30} tint={T_OCHRE} />
      <ProbChip label="P(≥70│≥50)" record={milestones.p_70_given_50} tint={T_OCHRE} />
    </div>
  )
}
