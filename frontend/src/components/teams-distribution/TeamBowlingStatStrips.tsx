/**
 * Per-metric stat strips + milestone-chip rows for the team-bowling
 * Distribution panel. Spec: internal_docs/spec-distribution-stats.md
 * §17.4.
 *
 * Three metric tabs: Wickets (default), Runs Conceded, Economy.
 * Uniform stat-strip schema across all three (per CLAUDE.md "stat
 * strip Mean ↔ Std must travel together") — Innings / Mean / Median /
 * Std plus a metric-specific accent line.
 *
 * Chip palette: 3-tier polarity-aware (CLAUDE.md). On the Runs
 * Conceded tab the polarity FLIPS — low conceded is OCHRE (good
 * for the bowler), high conceded is INDIGO. Wickets and Economy
 * tabs use the bowler-conventional tinting.
 */

import type {
  TeamBowlingWicketsBlock,
  TeamBowlingRunsConcededBlock,
  TeamBowlingEconomyBlock,
} from '../../types'
import AvgRowPrefix from '../distribution/AvgRowPrefix'
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

// ─── Wickets tab ─────────────────────────────────────────────────────

interface WicketsProps {
  block: TeamBowlingWicketsBlock
  /** Server-computed Pool SR (balls/wkt) on the parent dossier — added
   *  audit §4.3 to remove the cascade derivation that previously
   *  reconstructed balls via runs_conceded * 6 / economy.pool. */
  pool_strike_rate: number | null
  n_innings: number
}

export function WicketsStatStrip({ block, pool_strike_rate, n_innings }: WicketsProps) {
  return (
    <div>
      <StatRow
        label="Innings bowled" value={fmtNum(n_innings, 0)}
        tooltip="Team innings bowled in this scope + window. Denominator for every probability below."
      />
      <StatRow
        label="Mean wickets" value={fmtNum(block.mean_per_innings, 2)} accent
        tooltip="Average wickets credited per team innings. Total wickets ÷ number of innings. Includes run-outs (team-credited; diverges from bowler-credited /summary)."
      />
      <StatRow
        label="Median" value={fmtNum(block.median, 0)}
        tooltip="Middle value of wickets-per-innings — less affected by outlier innings than the mean."
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 2)}
        tooltip="Standard deviation of per-innings wickets. Higher = unpredictable; lower = consistent."
      />
      <StatRow
        label="Wickets total" value={fmtNum(block.total, 0)}
        tooltip="Total wickets credited across all innings in this scope + window."
      />
      <StatRow
        label="Pool SR (balls/wkt)" value={fmtNum(pool_strike_rate, 1)}
        tooltip="Balls bowled per wicket taken across the full sample. Lower = stronger strike rate."
      />
    </div>
  )
}

export function WicketsChipsRow({ block }: { block: TeamBowlingWicketsBlock }) {
  const m = block.milestones
  // Tier discipline per spec §17.4: ≤3 INDIGO (poor) / 4-6 SAGE
  // (typical) / ≥7 OCHRE (strong). Conditionals tinted at the
  // threshold being reached (≥7│≥5 = OCHRE; =10│≥5 = OCHRE).
  // Over-aware breakthrough chip is OCHRE; finishing rate is OCHRE
  // (both are good outcomes for the bowler).
  return (
    <ChipRow>
      <AvgRowPrefix />
      <ProbChip label="P(≤3)" record={m.p_leq_3} tint={T_INDIGO} />
      <ProbChip label="P(≥5)" record={m.p_geq_5} tint={T_SAGE} />
      <ProbChip label="P(≥7)" record={m.p_geq_7} tint={T_OCHRE} />
      <ProbChip label="P(=10)" record={m.p_eq_10} tint={T_OCHRE} />
      <ProbChip label="P(≥7│≥5)"  record={m.p_7_given_5}  tint={T_OCHRE} />
      <ProbChip label="P(=10│≥5)" record={m.p_10_given_5} tint={T_OCHRE} />
      <ProbChip label="P(≥3 at 10)"        record={m.p_geq_3_at_10}        tint={T_OCHRE} />
      <ProbChip label="P(=10│≥3 at 10)"    record={m.p_eq_10_given_3_at_10} tint={T_OCHRE} />
    </ChipRow>
  )
}

// ─── Runs Conceded tab ──────────────────────────────────────────────

interface RunsConcededProps {
  block: TeamBowlingRunsConcededBlock
  n_innings: number
}

export function RunsConcededStatStrip({ block, n_innings }: RunsConcededProps) {
  return (
    <div>
      <StatRow
        label="Innings bowled" value={fmtNum(n_innings, 0)}
        tooltip="Team innings bowled in this scope + window."
      />
      <StatRow
        label="Mean / innings" value={fmtNum(block.mean_per_innings, 1)} accent
        tooltip="Average runs conceded per innings. Lower is better for the bowling team."
      />
      <StatRow
        label="Median" value={fmtNum(block.median, 0)}
        tooltip="Middle value of runs-conceded per innings — less affected by one big total than the mean."
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 1)}
        tooltip="Standard deviation of per-innings runs conceded. Higher = swingy; lower = consistent."
      />
      <StatRow
        label="Total" value={fmtNum(block.total, 0)}
        tooltip="Total runs conceded across all innings in this scope + window."
      />
      <StatRow
        label="Escalation × at 10"
        value={block.escalation_ratio_median !== null ? `${fmtNum(block.escalation_ratio_median, 2)}×` : '—'}
        tooltip="Median ratio of final runs conceded ÷ runs conceded at end of over 10. 2.0× means the opposition typically doubled their over-10 score; lower = better death overs."
      />
    </div>
  )
}

export function RunsConcededChipsRow({ block }: { block: TeamBowlingRunsConcededBlock }) {
  const m = block.milestones
  // FLIPPED polarity per spec §17.2 + §17.4: low conceded = OCHRE
  // (good outcome for the bowler), high conceded = INDIGO. The
  // chain-ladder conditionals are climbing the ladder of bad — all
  // INDIGO. Doubling-at-10 is INDIGO (leakage signal).
  return (
    <ChipRow>
      <AvgRowPrefix />
      <ProbChip label="P(<100)" record={m.p_lt_100} tint={T_OCHRE} />
      <ProbChip label="P(<150)" record={m.p_lt_150} tint={T_SAGE} />
      <ProbChip label="P(≥150)" record={m.p_geq_150} tint={T_SAGE} />
      <ProbChip label="P(≥200)" record={m.p_geq_200} tint={T_INDIGO} />
      <ProbChip label="P(≥230)" record={m.p_geq_230} tint={T_INDIGO} />
      <ProbChip label="P(≥150│≥100)" record={m.p_150_given_100} tint={T_INDIGO} />
      <ProbChip label="P(≥200│≥150)" record={m.p_200_given_150} tint={T_INDIGO} />
      <ProbChip label="P(≥230│≥200)" record={m.p_230_given_200} tint={T_INDIGO} />
      <ProbChip label="P(2× final│at 10)" record={m.p_double_at_10} tint={T_INDIGO} />
    </ChipRow>
  )
}

// ─── Economy tab ────────────────────────────────────────────────────

interface EconomyProps {
  block: TeamBowlingEconomyBlock
  n_innings: number
}

export function EconomyStatStrip({ block, n_innings }: EconomyProps) {
  return (
    <div>
      <StatRow
        label="Innings bowled" value={fmtNum(n_innings, 0)}
        tooltip="Team innings bowled in this scope + window."
      />
      <StatRow
        label="Pool RPO" value={fmtNum(block.pool, 2)} accent
        tooltip="Career economy in scope: total runs conceded × 6 ÷ total balls. Conventional career RPO."
      />
      <StatRow
        label="Mean / innings" value={fmtNum(block.mean_per_innings, 2)}
        tooltip="Unweighted mean of per-innings RPO. Differs from Pool RPO when innings vary in length."
      />
      <StatRow
        label="Median / innings" value={fmtNum(block.median_per_innings, 2)} accent
        tooltip="Middle value of per-innings RPO — the histogram's centre of mass."
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 2)}
        tooltip="Standard deviation of per-innings RPO. Higher = swingy; lower = consistent."
      />
    </div>
  )
}

export function EconomyChipsRow({ block }: { block: TeamBowlingEconomyBlock }) {
  const m = block.milestones
  // Bowler-conventional polarity: low RPO is OCHRE (tight), high is
  // INDIGO (loose). Same as the per-bowler v1 panel.
  return (
    <ChipRow>
      <AvgRowPrefix />
      <ProbChip label="P(econ ≤6)"  record={m.p_econ_leq_6}  tint={T_OCHRE} />
      <ProbChip label="P(econ ≤7)"  record={m.p_econ_leq_7}  tint={T_SAGE} />
      <ProbChip label="P(econ ≥9)"  record={m.p_econ_geq_9}  tint={T_INDIGO} />
      <ProbChip label="P(econ ≥10)" record={m.p_econ_geq_10} tint={T_INDIGO} />
    </ChipRow>
  )
}
