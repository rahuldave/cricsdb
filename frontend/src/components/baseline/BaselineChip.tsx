import MetricDelta from '../MetricDelta'

/** Per-tile "vs base N — ↑+M%" subtitle component.
 *
 *  Synthesises a MetricEnvelope from (player value, cohort value,
 *  polarity) and routes through MetricDelta. Used in places where the
 *  player API returns SCALAR rate fields (not envelopes) — e.g.
 *  /batters/{id}/by-phase, /bowlers/{id}/by-phase — so the chip can
 *  still be rendered against the cohort's per-phase scalar.
 *
 *  Centralises the helper that previously lived as `PhaseChip` in
 *  three near-identical copies inside Batting.tsx / Bowling.tsx /
 *  Fielding.tsx (Phase G of spec-player-baseline-parity.md §5.1).
 *
 *  `tooltip` is the optional hover phrase explaining what `base`
 *  means at the current scope — typically the cohort's position-mix
 *  / over-mix / keeper-binary description (see
 *  `components/players/cohortTooltip.ts`). When omitted, the chip
 *  renders unannotated.
 */
export default function BaselineChip({
  v, base, dir, fmt: digits = 1, tooltip,
}: {
  v: number | null | undefined
  base: number | null | undefined
  dir: 'higher_better' | 'lower_better'
  fmt?: number
  tooltip?: string
}) {
  if (v == null || base == null || base === 0) return null
  const env = {
    value: v,
    scope_avg: base,
    delta_pct: ((v - base) / base) * 100,
    direction: dir,
    sample_size: null,
  }
  return (
    <div style={{ fontSize: '0.7rem', marginTop: '0.15rem', fontWeight: 400 }}>
      <MetricDelta
        env={env}
        withScopeAvg
        label="cohort"
        fmt={digits}
        scopeAvgTooltip={tooltip}
      />
    </div>
  )
}
