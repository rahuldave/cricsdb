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

interface Props {
  dossier: DistributionDossier
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(digits)
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${(v * 100).toFixed(0)}%`
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

function MilestoneChip({ label, value, polarity }: {
  label: string
  value: string
  polarity: 'positive' | 'negative' | 'neutral'
}) {
  // Wisden palette slate + sage / oxblood — translucent fills so the
  // page background still reads through.
  const bg =
    polarity === 'positive' ? 'rgba(122, 142, 106, 0.14)'
    : polarity === 'negative' ? 'rgba(160, 59, 59, 0.12)'
    : 'rgba(60, 91, 122, 0.10)'  // neutral: faint slate
  const fg =
    polarity === 'positive' ? '#3F5A2F'
    : polarity === 'negative' ? '#7A1F1F'
    : '#3C5B7A'  // neutral slate
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'baseline', gap: '0.35rem',
      padding: '0.18rem 0.55rem', borderRadius: '999px',
      background: bg, color: fg,
      fontSize: '0.72rem',
      fontFamily: 'var(--serif)', fontStyle: 'italic',
    }}>
      <span>{label}</span>
      <span className="num" style={{ fontStyle: 'normal', fontWeight: 600, fontSize: '0.82rem' }}>{value}</span>
    </span>
  )
}

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
      <MilestoneChip label="P(≤10)"     value={fmtPct(milestones.p_failure_10)}  polarity="negative" />
      <MilestoneChip label="P(≥30)"     value={fmtPct(milestones.p_30_plus)}     polarity="positive" />
      <MilestoneChip label="P(≥50)"     value={fmtPct(milestones.p_50_plus)}     polarity="positive" />
      <MilestoneChip label="P(≥100)"    value={fmtPct(milestones.p_100_plus)}    polarity="positive" />
      <MilestoneChip label="P(≥50│≥30)" value={fmtPct(milestones.p_50_given_30)} polarity="neutral" />
      <MilestoneChip label="P(≥70│≥50)" value={fmtPct(milestones.p_70_given_50)} polarity="neutral" />
    </div>
  )
}
