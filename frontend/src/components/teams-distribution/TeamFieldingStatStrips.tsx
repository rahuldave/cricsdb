/**
 * Per-metric stat strips + milestone-chip rows for the team-fielding
 * Distribution panel. Spec: internal_docs/spec-distribution-stats.md
 * §17.5.
 *
 * Three metric tabs: Catches (default), Run-outs, Stumpings. Uniform
 * stat-strip schema across all three (per CLAUDE.md "stat strip Mean ↔
 * Std must travel together") — Innings fielded / Total / Mean / Median /
 * Std. The Catches tab additionally renders a footer footnote with the
 * scope's substitute-catch count (excluded from the totals per
 * §16.4).
 *
 * Chip palette: 3-tier polarity-aware (CLAUDE.md). All three tabs use
 * the OUTCOME-ASCENDING tinting (low count = INDIGO, high = OCHRE) —
 * fielding events are always good for the fielding side.
 */

import type {
  TeamFieldingCatchesBlock,
  TeamFieldingCountBlock,
} from '../../types'
import ProbChip from '../distribution/ProbChip'
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

function ChipRow({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: '0.35rem',
      marginTop: '0.85rem',
    }}>
      {children}
    </div>
  )
}

// ─── Catches tab ────────────────────────────────────────────────────

interface CatchesProps {
  block: TeamFieldingCatchesBlock
  n_innings_fielded: number
  substitute_catches: number
}

export function CatchesStatStrip({ block, n_innings_fielded, substitute_catches }: CatchesProps) {
  return (
    <div>
      <StatRow
        label="Innings fielded" value={fmtNum(n_innings_fielded, 0)}
        tooltip="Innings the team was in the field in this scope + window. Denominator for every probability below."
      />
      <StatRow
        label="Mean / innings" value={fmtNum(block.mean_per_innings, 2)} accent
        tooltip="Average catches per innings fielded. Total catches ÷ innings fielded. Substitute catches excluded."
      />
      <StatRow
        label="Median" value={fmtNum(block.median, 0)}
        tooltip="Middle value of catches-per-innings — less affected by outlier high-catch innings than the mean."
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 2)}
        tooltip="Standard deviation of per-innings catches. Higher = swingy fielding nights; lower = consistent."
      />
      <StatRow
        label="Total" value={fmtNum(block.total, 0)}
        tooltip="Total catches across all innings in this scope + window. Substitute catches excluded."
      />
      {substitute_catches > 0 && (
        <div style={{
          padding: '0.25rem 0',
          fontFamily: 'var(--serif)', fontStyle: 'italic',
          fontSize: '0.75rem', color: 'var(--ink-faint)',
        }} title="Substitute catches are credited to the team but excluded from the per-innings totals above. Surfaced here for reconciliation against /fielding/summary.">
          + {substitute_catches} substitute catch{substitute_catches === 1 ? '' : 'es'} (excluded)
        </div>
      )}
    </div>
  )
}

export function CatchesChipsRow({ block }: { block: TeamFieldingCatchesBlock }) {
  const m = block.milestones
  // Per spec §17.5 chips table: P(=0) INDIGO (no catches),
  // P(≥3) SAGE (typical), P(≥5) OCHRE (sharp), P(≥7) OCHRE (elite).
  return (
    <ChipRow>
      <ProbChip label="P(=0)" record={m.p_eq_0}  tint={T_INDIGO} />
      <ProbChip label="P(≥3)" record={m.p_geq_3} tint={T_SAGE} />
      <ProbChip label="P(≥5)" record={m.p_geq_5} tint={T_OCHRE} />
      <ProbChip label="P(≥7)" record={m.p_geq_7} tint={T_OCHRE} />
    </ChipRow>
  )
}

// ─── Run-outs / Stumpings tabs ──────────────────────────────────────
//
// Identical shape: 3-chip partition over P(=0) / P(=1) / P(≥2).

interface CountProps {
  block: TeamFieldingCountBlock
  n_innings_fielded: number
  /** Label noun for the stat strip ("Run-out" / "Stumping"). */
  noun: string
}

export function CountStatStrip({ block, n_innings_fielded, noun }: CountProps) {
  return (
    <div>
      <StatRow
        label="Innings fielded" value={fmtNum(n_innings_fielded, 0)}
        tooltip="Innings the team was in the field in this scope + window."
      />
      <StatRow
        label="Mean / innings" value={fmtNum(block.mean_per_innings, 2)} accent
        tooltip={`Average ${noun.toLowerCase()}s per innings fielded. Total ÷ innings.`}
      />
      <StatRow
        label="Median" value={fmtNum(block.median, 0)}
        tooltip={`Middle value of ${noun.toLowerCase()}s-per-innings.`}
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 2)}
        tooltip="Standard deviation of per-innings counts."
      />
      <StatRow
        label="Total" value={fmtNum(block.total, 0)}
        tooltip={`Total ${noun.toLowerCase()}s across all innings in this scope + window.`}
      />
    </div>
  )
}

export function CountChipsRow({ block }: { block: TeamFieldingCountBlock }) {
  const m = block.milestones
  // Per spec §17.5 chips table: P(=0) INDIGO / P(=1) SAGE / P(≥2) OCHRE.
  return (
    <ChipRow>
      <ProbChip label="P(=0)" record={m.p_eq_0}  tint={T_INDIGO} />
      <ProbChip label="P(=1)" record={m.p_eq_1}  tint={T_SAGE} />
      <ProbChip label="P(≥2)" record={m.p_geq_2} tint={T_OCHRE} />
    </ChipRow>
  )
}
