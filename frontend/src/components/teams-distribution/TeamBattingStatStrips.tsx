/**
 * Per-metric stat strips + milestone-chip rows for the team-batting
 * Distribution panel. Spec: internal_docs/spec-distribution-stats.md
 * §17.3.
 *
 * Two metric tabs: Runs (default) + Run Rate. Uniform stat-strip
 * schema across both — Innings / Mean / Median / Std (per CLAUDE.md
 * "stat strip Mean ↔ Std must travel together"). The Total runs
 * line is a footer accent on the Runs tab.
 *
 * Chip palette: 3-tier polarity-aware (CLAUDE.md "Distribution-panel
 * color discipline (3-tier palette)") — INDIGO low / SAGE typical /
 * OCHRE high. Run Rate chips use POLARITY-FLIPPED tints relative to
 * bowler economy: low RR is bad for the batter, so P(RR ≤ 7) is
 * INDIGO, P(RR ≥ 9) is OCHRE.
 */

import type { TeamBattingRunsBlock, TeamBattingRunRateBlock } from '../../types'
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

// ─── Runs tab ────────────────────────────────────────────────────────

interface RunsProps {
  block: TeamBattingRunsBlock
  n_innings: number
}

export function RunsStatStrip({ block, n_innings }: RunsProps) {
  return (
    <div>
      <StatRow
        label="Innings" value={fmtNum(n_innings, 0)}
        tooltip="Team innings in this scope + window. Denominator for every probability below."
      />
      <StatRow
        label="Mean / innings" value={fmtNum(block.mean_per_innings, 1)} accent
        tooltip="Average runs per team innings. Total runs ÷ number of innings."
      />
      <StatRow
        label="Median" value={fmtNum(block.median, 0)}
        tooltip="Middle value of runs-per-innings — less affected by 200+ outliers than the mean."
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 1)}
        tooltip="Standard deviation of per-innings runs. Higher std = swingy team totals; lower = predictable innings to innings."
      />
      <StatRow
        label="Total" value={fmtNum(block.total, 0)}
        tooltip="Total runs across all innings in this scope + window."
      />
    </div>
  )
}

export function RunsChipsRow({ block }: { block: TeamBattingRunsBlock }) {
  const m = block.milestones
  // Tier discipline per spec §17.2: <100 INDIGO (low) / 100-199 SAGE
  // (typical) / ≥200 OCHRE (explosive). Chain-ladder conditionals
  // tinted at the threshold being reached. Doubling-at-10 chip is
  // OCHRE — doubling the over-10 score is a strong escalation signal.
  return (
    <ChipRow>
      <ProbChip label="P(<100)" record={m.p_lt_100}  tint={T_INDIGO} />
      <ProbChip label="P(≥100)" record={m.p_geq_100} tint={T_SAGE} />
      <ProbChip label="P(≥150)" record={m.p_geq_150} tint={T_SAGE} />
      <ProbChip label="P(≥200)" record={m.p_geq_200} tint={T_OCHRE} />
      <ProbChip label="P(≥230)" record={m.p_geq_230} tint={T_OCHRE} />
      <ProbChip label="P(≥150│≥100)" record={m.p_150_given_100} tint={T_SAGE} />
      <ProbChip label="P(≥200│≥150)" record={m.p_200_given_150} tint={T_OCHRE} />
      <ProbChip label="P(≥230│≥200)" record={m.p_230_given_200} tint={T_OCHRE} />
      <ProbChip label="P(2× final│at 10)" record={m.p_double_at_10} tint={T_OCHRE} />
    </ChipRow>
  )
}

// ─── Run Rate tab ────────────────────────────────────────────────────

interface RRProps {
  block: TeamBattingRunRateBlock
  n_innings: number
}

export function RRStatStrip({ block, n_innings }: RRProps) {
  return (
    <div>
      <StatRow
        label="Innings" value={fmtNum(n_innings, 0)}
        tooltip="Team innings in this scope + window."
      />
      <StatRow
        label="Pool RR" value={fmtNum(block.pool, 2)} accent
        tooltip="Career RR in scope: total runs × 6 ÷ total balls. The conventional career run rate."
      />
      <StatRow
        label="Mean / innings" value={fmtNum(block.mean_per_innings, 2)}
        tooltip="Unweighted mean of per-innings RRs. Differs from pool RR when innings vary in length."
      />
      <StatRow
        label="Median / innings" value={fmtNum(block.median_per_innings, 2)} accent
        tooltip="Middle value of per-innings RRs — the histogram's centre of mass. Less affected by one explosive innings."
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 2)}
        tooltip="Standard deviation of per-innings RRs. Higher std = swingy tempo; lower = consistent night-to-night."
      />
    </div>
  )
}

export function RRChipsRow({ block }: { block: TeamBattingRunRateBlock }) {
  const m = block.milestones
  // Polarity-flipped from bowler economy (CLAUDE.md "Distribution-
  // panel color discipline"): low RR is bad for the batter (INDIGO),
  // high RR is good (OCHRE). The threshold is the same 7 / 9 RPO
  // ladder as bowler economy — only the tints flip.
  return (
    <ChipRow>
      <ProbChip label="P(RR ≤7)"  record={m.p_rr_leq_7}  tint={T_INDIGO} />
      <ProbChip label="P(RR ≤8)"  record={m.p_rr_leq_8}  tint={T_INDIGO} />
      <ProbChip label="P(RR ≥9)"  record={m.p_rr_geq_9}  tint={T_OCHRE} />
      <ProbChip label="P(RR ≥10)" record={m.p_rr_geq_10} tint={T_OCHRE} />
    </ChipRow>
  )
}
