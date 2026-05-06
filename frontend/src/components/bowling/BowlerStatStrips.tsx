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

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(digits)
}

function StatRow({ label, value, accent }: {
  label: string; value: string; accent?: boolean
}) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between',
      alignItems: 'baseline', padding: '0.25rem 0',
    }}>
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
      <StatRow label="Mean wkts" value={fmtNum(block.mean_per_innings, 2)} accent />
      <StatRow label="Median wkts" value={fmtNum(block.median, 0)} />
      <StatRow label="Total wkts" value={fmtNum(block.total, 0)} />
      <StatRow label="Pool SR" value={fmtNum(dossier.pool_strike_rate, 1)} accent />
      <StatRow label="Pool econ" value={fmtNum(dossier.economy.pool, 2)} />
      <StatRow label="Pool average" value={fmtNum(dossier.pool_average, 1)} />
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
  return (
    <ChipRow>
      <ProbChip label="P(0)"  record={m.p_zero}  polarity="negative" />
      <ProbChip label="P(≥1)" record={m.p_geq_1} polarity="positive" />
      <ProbChip label="P(≥2)" record={m.p_geq_2} polarity="positive" />
      <ProbChip label="P(≥3)" record={m.p_geq_3} polarity="positive" />
      <ProbChip label="P(≥4)" record={m.p_geq_4} polarity="positive" />
      <ProbChip label="P(≥5)" record={m.p_geq_5} polarity="positive" />
      <ConditionalsSeparator />
      <ProbChip label="P(≥3│≥2)" record={m.p_3_given_2} polarity="neutral" />
      <ProbChip label="P(≥4│≥2)" record={m.p_4_given_2} polarity="neutral" />
      <ProbChip label="P(≥5│≥2)" record={m.p_5_given_2} polarity="neutral" />
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
      <StatRow label="Pool econ" value={fmtNum(block.pool, 2)} accent />
      <StatRow label="Mean / inn" value={fmtNum(block.mean_per_innings, 2)} />
      <StatRow label="Median / inn" value={fmtNum(block.median_per_innings, 2)} accent />
      <StatRow label="Std" value={fmtNum(block.std, 2)} />
    </div>
  )
}

export function EconomyChipsRow({ block }: EconomyProps) {
  const m = block.milestones
  return (
    <ChipRow>
      <ProbChip label="P(econ ≤6)"  record={m.p_econ_leq_6}  polarity="positive" />
      <ProbChip label="P(econ ≤7)"  record={m.p_econ_leq_7}  polarity="positive" />
      <ProbChip label="P(econ ≥9)"  record={m.p_econ_geq_9}  polarity="negative" />
      <ProbChip label="P(econ ≥10)" record={m.p_econ_geq_10} polarity="negative" />
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
      <StatRow label="Total" value={fmtNum(block.total, 0)} />
      <StatRow label="Mean / inn" value={fmtNum(block.mean_per_innings, 1)} accent />
      <StatRow label="Median / inn" value={fmtNum(block.median, 0)} accent />
      <StatRow label="Std" value={fmtNum(block.std, 1)} />
    </div>
  )
}

export function RunsConcededChipsRow({ block }: RunsConcededProps) {
  const m = block.milestones
  return (
    <ChipRow>
      <ProbChip label="P(≤15)" record={m.p_leq_15} polarity="positive" />
      <ProbChip label="P(≤25)" record={m.p_leq_25} polarity="positive" />
      <ProbChip label="P(≥40)" record={m.p_geq_40} polarity="negative" />
      <ProbChip label="P(≥50)" record={m.p_geq_50} polarity="negative" />
    </ChipRow>
  )
}
