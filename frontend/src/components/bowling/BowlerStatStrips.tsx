/**
 * Per-metric stat strips + milestone-chip rows for the bowler
 * Distribution panel. Spec: internal_docs/spec-distribution-stats.md
 * §12.2.5.
 *
 * Three small stateless components — one per metric tab. Each
 * renders the metric-specific stat list (left) and milestone chips
 * (right / below) consuming the shared ProbChip component.
 *
 * The container chooses which strip + chip row to render based on
 * the active `dist_metric` tab.
 */

import type { BowlerDossier, BowlerWicketsBlock,
              BowlerEconomyBlock, BowlerRunsConcededBlock } from '../../types'
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

function ConditionalsSeparator() {
  return (
    <div style={{
      width: '100%', display: 'flex', alignItems: 'center',
      gap: '0.5rem', marginTop: '0.45rem', marginBottom: '-0.2rem',
      fontFamily: 'var(--serif)', fontStyle: 'italic',
      fontSize: '0.7rem', color: 'var(--ink-faint)',
    }}>
      <span style={{ flex: 1, height: 1, background: 'var(--ink-faint)',
                     opacity: 0.3 }} />
      <span>conditionals · anchor ≥2</span>
      <span style={{ flex: 1, height: 1, background: 'var(--ink-faint)',
                     opacity: 0.3 }} />
    </div>
  )
}

// ─── Wickets tab ─────────────────────────────────────────────────────

interface WicketsProps {
  block: BowlerWicketsBlock
  dossier: BowlerDossier
  n_innings: number
}

export function WicketsStatStrip({ block, dossier, n_innings }: WicketsProps) {
  return (
    <div>
      <StatRow
        label="Mean wkts" value={fmtNum(block.mean_per_innings, 2)} accent
        tooltip="Average wickets per qualifying spell. Wickets total ÷ number of spells."
      />
      <StatRow
        label="Median wkts" value={fmtNum(block.median, 0)}
        tooltip="Middle value of wickets-per-spell. Less affected by 5-fer outliers than the mean."
      />
      <StatRow
        label="Total wkts" value={fmtNum(block.total, 0)}
        tooltip="Total wickets across all qualifying spells in this scope + window."
      />
      <StatRow
        label="Strike Rate" value={fmtNum(dossier.pool_strike_rate, 1)} accent
        tooltip="Career strike rate in scope: total balls bowled ÷ total wickets. Lower is better."
      />
      <StatRow
        label="Economy" value={fmtNum(dossier.economy.pool, 2)}
        tooltip="Career economy in scope: total runs conceded × 6 ÷ total balls bowled. Lower is better."
      />
      <StatRow
        label="Average" value={fmtNum(dossier.pool_average, 1)}
        tooltip="Career bowling average in scope: total runs conceded ÷ total wickets. Lower is better."
      />
      <div style={{
        fontFamily: 'var(--serif)', fontStyle: 'italic',
        fontSize: '0.7rem', color: 'var(--ink-faint)',
        textAlign: 'right', marginTop: '0.25rem',
      }}>
        {n_innings} qualifying spell{n_innings === 1 ? '' : 's'}
      </div>
    </div>
  )
}

export function WicketsChipsRow({ block }: { block: BowlerWicketsBlock }) {
  const m = block.milestones
  // Wickets palette: 0 = wicketless (indigo) / 1-2 = building (sage) /
  // 3+ = strike (ochre). Conditionals all about reaching strike-tier.
  return (
    <ChipRow>
      <ProbChip label="P(0)"  record={m.p_zero}  tint={T_INDIGO} />
      <ProbChip label="P(≥1)" record={m.p_geq_1} tint={T_SAGE} />
      <ProbChip label="P(≥2)" record={m.p_geq_2} tint={T_SAGE} />
      <ProbChip label="P(≥3)" record={m.p_geq_3} tint={T_OCHRE} />
      <ProbChip label="P(≥4)" record={m.p_geq_4} tint={T_OCHRE} />
      <ProbChip label="P(≥5)" record={m.p_geq_5} tint={T_OCHRE} />
      <ConditionalsSeparator />
      <ProbChip label="P(≥3│≥2)" record={m.p_3_given_2} tint={T_OCHRE} />
      <ProbChip label="P(≥4│≥2)" record={m.p_4_given_2} tint={T_OCHRE} />
      <ProbChip label="P(≥5│≥2)" record={m.p_5_given_2} tint={T_OCHRE} />
    </ChipRow>
  )
}

// ─── Economy tab ─────────────────────────────────────────────────────

interface EconomyProps {
  block: BowlerEconomyBlock
}

export function EconomyStatStrip({ block }: EconomyProps) {
  return (
    <div>
      <StatRow
        label="Economy" value={fmtNum(block.pool, 2)} accent
        tooltip="Career economy in scope: total runs × 6 ÷ total balls. The conventional career RPO."
      />
      <StatRow
        label="Mean / spell" value={fmtNum(block.mean_per_innings, 2)}
        tooltip="Unweighted mean of per-spell economies. Differs from career economy when spells vary in length — each spell here counts equally regardless of how many balls were bowled."
      />
      <StatRow
        label="Median / spell" value={fmtNum(block.median_per_innings, 2)} accent
        tooltip="Middle value of per-spell economies — the histogram's centre of mass. Less affected by one expensive over."
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 2)}
        tooltip="Standard deviation of per-spell economies. Higher std = bowler runs hot-and-cold; lower = consistent night-to-night."
      />
    </div>
  )
}

export function EconomyChipsRow({ block }: EconomyProps) {
  const m = block.milestones
  // Economy is lower-is-better: ≤6/≤7 are tight (ochre = good for
  // bowler); ≥9/≥10 are loose (indigo = poor outcome).
  return (
    <ChipRow>
      <ProbChip label="P(econ ≤6)"  record={m.p_econ_leq_6}  tint={T_OCHRE} />
      <ProbChip label="P(econ ≤7)"  record={m.p_econ_leq_7}  tint={T_OCHRE} />
      <ProbChip label="P(econ ≥9)"  record={m.p_econ_geq_9}  tint={T_INDIGO} />
      <ProbChip label="P(econ ≥10)" record={m.p_econ_geq_10} tint={T_INDIGO} />
    </ChipRow>
  )
}

// ─── Runs conceded tab ──────────────────────────────────────────────

interface RunsConcededProps {
  block: BowlerRunsConcededBlock
}

export function RunsConcededStatStrip({ block }: RunsConcededProps) {
  return (
    <div>
      <StatRow
        label="Total" value={fmtNum(block.total, 0)}
        tooltip="Total runs conceded across all qualifying spells in this scope + window."
      />
      <StatRow
        label="Mean / spell" value={fmtNum(block.mean_per_innings, 1)} accent
        tooltip="Average runs conceded per qualifying spell. Total runs ÷ number of spells."
      />
      <StatRow
        label="Median / spell" value={fmtNum(block.median, 0)} accent
        tooltip="Middle value of runs-per-spell. Less affected by one expensive outing than the mean."
      />
      <StatRow
        label="Std" value={fmtNum(block.std, 1)}
        tooltip="Standard deviation of runs-per-spell. Higher std = swingy outings; lower = predictable spell-to-spell."
      />
    </div>
  )
}

export function RunsConcededChipsRow({ block }: RunsConcededProps) {
  const m = block.milestones
  // Runs conceded is lower-is-better: ≤15/≤25 are tight (ochre);
  // ≥40/≥50 are loose (indigo).
  return (
    <ChipRow>
      <ProbChip label="P(≤15)" record={m.p_leq_15} tint={T_OCHRE} />
      <ProbChip label="P(≤25)" record={m.p_leq_25} tint={T_OCHRE} />
      <ProbChip label="P(≥40)" record={m.p_geq_40} tint={T_INDIGO} />
      <ProbChip label="P(≥50)" record={m.p_geq_50} tint={T_INDIGO} />
    </ChipRow>
  )
}
