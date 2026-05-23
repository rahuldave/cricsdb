/**
 * Per-metric stat strip + milestone-chip row for the fielder
 * Distribution panel. Spec: internal_docs/spec-distribution-stats.md
 * §14.2.4.
 *
 * Uniform schema across all three tabs — Matches / Total / Median /
 * Mean per match / Std. Earlier draft hid Mean on catches+run-outs
 * (the value is small at ~0.3 for non-keepers and looks
 * uninformative), but the Std row is meaningless without a centre
 * to anchor it; quoting one without the other is incoherent.
 * (Revised 2026-05-07.) All three tabs share the three-chip row
 * P(=0)/P(=1)/P(≥2) tinted to the matching histogram bars.
 */

import type { FielderCountBlock } from '../../types'
import ProbChip from '../distribution/ProbChip'
import CohortRowPrefix from '../distribution/CohortRowPrefix'
import WindowBadge, { type DistWindow } from '../distribution/WindowBadge'
import CohortNarrowNudge from '../distribution/CohortNarrowNudge'
import { WISDEN_TIER_TINTS } from '../charts/palette'

const T_INDIGO = WISDEN_TIER_TINTS.indigo
const T_SAGE   = WISDEN_TIER_TINTS.sage
const T_OCHRE  = WISDEN_TIER_TINTS.ochre

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(digits)
}

function StatRow({ label, value, accent, tooltip }: {
  label: string; value: string; accent?: boolean; tooltip?: string
}) {
  return (
    <div
      title={tooltip}
      style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'baseline', padding: '0.25rem 0',
        cursor: tooltip ? 'help' : undefined,
      }}
    >
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

interface StripProps {
  block: FielderCountBlock
  metricLabel: string  // "Catches" / "Run-outs" / "Stumpings"
  nMatches: number
  /** Substitute catches surfaced as a footnote on the catches tab only. */
  substituteCatches?: number
}

export function FielderStatStrip({
  block, metricLabel, nMatches, substituteCatches,
}: StripProps) {
  return (
    <div>
      <StatRow
        label="Matches" value={fmtNum(nMatches, 0)}
        tooltip="Matches the player appeared on the team sheet in this scope + window. Denominator for every probability below."
      />
      <StatRow
        label={`Total ${metricLabel.toLowerCase()}`}
        value={fmtNum(block.total, 0)} accent
        tooltip={`Total ${metricLabel.toLowerCase()} across all matches in this scope + window.`}
      />
      <StatRow
        label="Mean / match" value={fmtNum(block.mean_per_match, 2)} accent
        tooltip={`Average ${metricLabel.toLowerCase()} per match. Total ÷ matches.`}
      />
      <StatRow
        label="Median" value={fmtNum(block.median, 0)}
        tooltip={`Middle value of ${metricLabel.toLowerCase()}-per-match. Usually 0 — the long zero-tail dominates.`}
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 2)}
        tooltip={`Standard deviation of ${metricLabel.toLowerCase()}-per-match.`}
      />
      {substituteCatches !== undefined && substituteCatches > 0 && (
        <div style={{
          fontFamily: 'var(--serif)', fontStyle: 'italic',
          fontSize: '0.7rem', color: 'var(--ink-faint)',
          textAlign: 'right', marginTop: '0.25rem',
        }}>
          + {substituteCatches} substitute catch{substituteCatches === 1 ? '' : 'es'} (excluded)
        </div>
      )}
    </div>
  )
}

interface ChipsProps {
  block: FielderCountBlock
}

export function FielderChipsRow({
  block, window = 'scope', playerId,
}: ChipsProps & { window?: DistWindow; playerId?: string }) {
  const m = block.milestones
  // 0 = blanked (indigo), 1 = ticked over (sage), ≥2 = multi-event (ochre).
  return (
    <>
      <WindowBadge window={window} />
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '0.35rem',
        marginTop: '0.85rem',
        // flex-start aligns the pill tops so the descriptive
        // P(=1) chip (no cohort caption — direction === null) stays
        // level with the P(=0) / P(≥2) chips that DO render a
        // caption beneath. flex-end aligned bottoms which dropped
        // the lone pill below its peers — user-flagged 2026-05-22.
        alignItems: 'flex-start',
      }}>
        <CohortRowPrefix />
        <ProbChip label="P(=0)"  record={m.p_zero}  tint={T_INDIGO} />
        <ProbChip label="P(=1)"  record={m.p_one}   tint={T_SAGE} />
        <ProbChip label="P(≥2)"  record={m.p_geq_2} tint={T_OCHRE} />
        {playerId && <CohortNarrowNudge window={window} playerId={playerId} />}
      </div>
    </>
  )
}
