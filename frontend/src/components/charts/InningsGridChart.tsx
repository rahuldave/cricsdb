import type { InningsGridInnings, InningsGridDelivery } from '../../types'
import { DELIVERY, deliveryRunColor } from './palette'

interface Props {
  innings: InningsGridInnings
}

// Sizing in rem so it respects the user's root font scale.
// 1rem = 16px at default browser settings.
const CELL = '1rem'           // batter cell width and row height
const BOWLER_W = '7rem'       // bowler-name column
const OVER_W = '2rem'         // over.ball column
const HIST_CELL = '0.625rem'  // each histogram cell (10px)
const HIST_CELLS = 7          // up to 7 runs (covers boundary off no-ball = 5)
const HIST_W = `calc(${HIST_CELL} * ${HIST_CELLS} + 0.25rem)`
const SCORE_W = '3rem'        // cum-score column
const WKT_W = '18rem'         // wicket-text + partnership column

// Source colors — all from the semantic DELIVERY palette in palette.ts.
const COLOR_OFFBAT = deliveryRunColor
const COLOR_WIDE   = DELIVERY.wide
const COLOR_NOBALL = DELIVERY.noball
const COLOR_BYE    = DELIVERY.bye
const COLOR_LEGBYE = DELIVERY.legbye
const COLOR_WICKET = DELIVERY.wicket
// Two alternating tints for the at-crease stripe — one per partnership
// "slot". When a batter gets out, the new batter inherits the slot (and
// shade) of the partner they replaced. Both are faint cream tints so
// they recede behind the saturated run/extras/wicket colors but stay
// distinct from each other.
const COLOR_AT_CREASE_A = DELIVERY.atCreaseA
const COLOR_AT_CREASE_B = DELIVERY.atCreaseB
const COLOR_AT_CREASE = COLOR_AT_CREASE_A  // for the legend swatch

interface CellInfo {
  bg: string
  text: string
  color: string
  noBallMark: boolean
}

function cellInfo(d: InningsGridDelivery, isDismissedColumn: boolean): CellInfo {
  if (isDismissedColumn) {
    return { bg: COLOR_WICKET, text: 'W', color: 'var(--bg)', noBallMark: false }
  }
  if (d.runs_batter > 0) {
    return {
      bg: COLOR_OFFBAT(d.runs_batter),
      text: String(d.runs_batter),
      color: d.runs_batter >= 4 ? 'var(--bg)' : 'var(--ink)',
      noBallMark: d.extras_noballs > 0,
    }
  }
  if (d.extras_wides > 0) {
    const extra = d.runs_total - 1
    return {
      bg: COLOR_WIDE,
      text: extra > 0 ? `w${extra}` : 'w',
      color: 'var(--ink)',
      noBallMark: false,
    }
  }
  if (d.extras_noballs > 0) {
    // No-ball with no off-bat runs (might still have byes/legbyes)
    return {
      bg: COLOR_NOBALL,
      text: 'n',
      color: 'var(--ink)',
      noBallMark: false,
    }
  }
  if (d.extras_byes > 0 || d.extras_legbyes > 0) {
    const tag = d.extras_byes > 0 ? 'b' : 'lb'
    const total = d.runs_extras
    return {
      bg: d.extras_byes > 0 ? COLOR_BYE : COLOR_LEGBYE,
      text: total > 0 ? `${tag}${total}` : tag,
      color: 'var(--ink)',
      noBallMark: false,
    }
  }
  return { bg: 'var(--bg-soft)', text: '·', color: 'var(--ink-faint)', noBallMark: false }
}

/**
 * Decompose a ball's total runs into colored "run units" so the
 * histogram can show the exact breakdown of where the runs came from.
 * Order: off-bat first, then no-ball penalty, then wides, then byes/legbyes.
 */
function runUnits(d: InningsGridDelivery): string[] {
  const units: string[] = []
  // Off-bat
  for (let i = 0; i < d.runs_batter; i++) {
    units.push(COLOR_OFFBAT(d.runs_batter))
  }
  // No-ball penalty (always 1)
  if (d.extras_noballs > 0) units.push(COLOR_NOBALL)
  // Wides — note cricsheet codes the FULL wide+run total in extras_wides
  for (let i = 0; i < d.extras_wides; i++) units.push(COLOR_WIDE)
  // Byes
  for (let i = 0; i < d.extras_byes; i++) units.push(COLOR_BYE)
  // Legbyes
  for (let i = 0; i < d.extras_legbyes; i++) units.push(COLOR_LEGBYE)
  return units.slice(0, HIST_CELLS)
}

interface OverSummary {
  over: number
  runs: number
  wickets: number
  balls: number
}

function summarizeOvers(deliveries: InningsGridDelivery[]): Map<number, OverSummary> {
  const m = new Map<number, OverSummary>()
  for (const d of deliveries) {
    const overNum = parseInt(d.over_ball.split('.')[0], 10)
    if (!m.has(overNum)) {
      m.set(overNum, { over: overNum, runs: 0, wickets: 0, balls: 0 })
    }
    const s = m.get(overNum)!
    s.runs += d.runs_total
    if (d.wicket_kind) s.wickets++
    s.balls++
  }
  return m
}

interface Partnership {
  endIndex: number
  number: number
  runs: number
  balls: number
}

/**
 * Assign a "slot" (A or B) to each batter index. Initial: first ball's
 * batter is A, non-striker is B. On every wicket, find the next batter
 * index that hasn't been assigned a slot yet, and give them the
 * dismissed batter's slot. Result: at any moment, the two at-crease
 * batters always have one A and one B — and a batter inherits the
 * shade of the partner they replaced.
 */
function assignBatterSlots(
  deliveries: InningsGridDelivery[],
): Map<number, 'A' | 'B'> {
  const slots = new Map<number, 'A' | 'B'>()
  if (deliveries.length === 0) return slots
  const first = deliveries[0]
  slots.set(first.batter_index, 'A')
  if (first.non_striker_index != null) slots.set(first.non_striker_index, 'B')
  for (let i = 0; i < deliveries.length; i++) {
    const d = deliveries[i]
    if (!d.wicket_kind || d.wicket_player_out_index == null) continue
    const dismissedSlot = slots.get(d.wicket_player_out_index)
    if (!dismissedSlot) continue
    // Find the next not-yet-assigned batter, looking forward
    for (let j = i + 1; j < deliveries.length; j++) {
      const dj = deliveries[j]
      if (!slots.has(dj.batter_index)) {
        slots.set(dj.batter_index, dismissedSlot)
        break
      }
      if (dj.non_striker_index != null && !slots.has(dj.non_striker_index)) {
        slots.set(dj.non_striker_index, dismissedSlot)
        break
      }
    }
  }
  return slots
}

/**
 * Walk through deliveries and identify partnership boundaries.
 * A partnership ends on a wicket OR at the final ball of the innings.
 * Returned map: delivery index → the partnership that ended at that index.
 */
function summarizePartnerships(
  deliveries: InningsGridDelivery[],
): Map<number, Partnership> {
  const result = new Map<number, Partnership>()
  let runs = 0
  let balls = 0
  let n = 1
  for (let i = 0; i < deliveries.length; i++) {
    const d = deliveries[i]
    runs += d.runs_total
    balls++
    const isLast = i === deliveries.length - 1
    if (d.wicket_kind || isLast) {
      result.set(i, { endIndex: i, number: n, runs, balls })
      n++
      runs = 0
      balls = 0
    }
  }
  return result
}

/**
 * Per-batter running tally up to the moment of dismissal.
 * Returns map: delivery index → { runs, balls } for the batter who
 * was dismissed on that delivery. Used to surface the dismissed
 * batter's individual score in the wicket text column.
 *
 * Tracks each batter_index's accumulating runs (off the bat) and
 * legal balls faced (excluding wides + no-balls per the project's
 * legal-balls convention).
 */
function summarizeDismissalScores(
  deliveries: InningsGridDelivery[],
): Map<number, { runs: number; balls: number }> {
  const result = new Map<number, { runs: number; balls: number }>()
  const tally = new Map<number, { runs: number; balls: number }>()
  for (let i = 0; i < deliveries.length; i++) {
    const d = deliveries[i]
    // Accrue to the striker.
    let t = tally.get(d.batter_index)
    if (!t) { t = { runs: 0, balls: 0 }; tally.set(d.batter_index, t) }
    t.runs += d.runs_batter
    if (d.extras_wides === 0 && d.extras_noballs === 0) t.balls += 1
    // On a wicket, snapshot the dismissed batter's totals (which may
    // be the non-striker on a run-out).
    if (d.wicket_kind && d.wicket_player_out_index != null) {
      const dt = tally.get(d.wicket_player_out_index)
      if (dt) result.set(i, { runs: dt.runs, balls: dt.balls })
    }
  }
  return result
}

export default function InningsGridChart({ innings }: Props) {
  const N = innings.batters.length
  const headerHeight = '4.5rem'
  const overSummaries = summarizeOvers(innings.deliveries)
  const partnerships = summarizePartnerships(innings.deliveries)
  const dismissalScores = summarizeDismissalScores(innings.deliveries)
  const slots = assignBatterSlots(innings.deliveries)
  const slotColor = (b: number): string | undefined => {
    const s = slots.get(b)
    return s === 'A' ? COLOR_AT_CREASE_A : s === 'B' ? COLOR_AT_CREASE_B : undefined
  }
  const SUMMARY_H = '0.875rem'

  return (
    <div>
      <div className="section-head">
        <span className="section-label">{innings.team} — innings grid</span>
        <span className="wisden-chart-sub num">
          {innings.total_runs}/{innings.total_wickets} · {innings.total_balls} balls
        </span>
      </div>
      <div className="rule" />

      {/* Color legend */}
      <div className="flex flex-wrap gap-3 text-[10px] mb-3" style={{ color: 'var(--ink-faint)', fontFamily: 'var(--sans)' }}>
        <Legend color={COLOR_AT_CREASE} label="at crease (not facing)" />
        <Legend color={COLOR_OFFBAT(0)} label="dot" />
        <Legend color={COLOR_OFFBAT(1)} label="1" />
        <Legend color={COLOR_OFFBAT(2)} label="2" />
        <Legend color={COLOR_OFFBAT(4)} label="4" />
        <Legend color={COLOR_OFFBAT(6)} label="6" />
        <Legend color={COLOR_BYE} label="byes" />
        <Legend color={COLOR_LEGBYE} label="leg-byes" />
        <Legend color={COLOR_WIDE} label="wide" />
        <Legend color={COLOR_NOBALL} label="no-ball" />
        <Legend color={COLOR_WICKET} label="wicket" />
        <span style={{ color: 'var(--ink-faint)' }}>
          (small <span style={{ color: 'var(--accent)', fontWeight: 700 }}>n</span> on a green
          cell = no-ball with off-bat runs)
        </span>
      </div>

      <div className="wisden-scroll-hint">← swipe to scroll →</div>
      <div className="overflow-x-auto">
        <div style={{ display: 'inline-block', minWidth: '100%' }}>
          {/* Header row */}
          <div className="flex" style={{ height: headerHeight }}>
            <div style={{ width: OVER_W }} />
            <div style={{ width: BOWLER_W }} />
            {innings.batters.map((name, i) => (
              <div
                key={i}
                style={{
                  width: CELL,
                  height: headerHeight,
                  position: 'relative',
                  // Subtle vertical separator between batter columns
                  borderRight: i === N - 1 ? '1px solid var(--rule)' : undefined,
                }}
                className="wisden-grid-cell-bottom"
              >
                <div
                  style={{
                    position: 'absolute',
                    bottom: '0.25rem',
                    left: `calc(${CELL} / 2)`,
                    transformOrigin: '0 0',
                    transform: 'rotate(-60deg)',
                    whiteSpace: 'nowrap',
                    fontSize: '0.625rem',
                    color: 'var(--ink-soft)',
                    fontFamily: 'var(--serif)',
                    fontStyle: 'italic',
                  }}
                  title={name}
                >
                  {name}
                </div>
              </div>
            ))}
            {/* histogram column header */}
            <div
              style={{ width: HIST_W, borderRight: '1px solid var(--rule)' }}
              className="text-[9px] wisden-grid-label self-end wisden-grid-cell-bottom px-1 pb-1 text-right"
            >
              runs
            </div>
            {/* score column header */}
            <div
              style={{ width: SCORE_W, borderRight: '1px solid var(--rule)' }}
              className="text-[9px] wisden-grid-label self-end wisden-grid-cell-bottom pl-2 pb-1"
            >
              score
            </div>
            {/* wicket text header — hidden on small viewports */}
            <div
              style={{ width: WKT_W }}
              className="text-[9px] wisden-grid-label self-end wisden-grid-cell-bottom pl-2 pb-1 hidden md:block"
            >
              wicket
            </div>
          </div>

          {/* Ball rows + over summaries interleaved */}
          {innings.deliveries.map((d, i) => {
            const prev = i > 0 ? innings.deliveries[i - 1] : null
            const next = i < innings.deliveries.length - 1 ? innings.deliveries[i + 1] : null
            const overNum = parseInt(d.over_ball.split('.')[0], 10)
            const newOver = !prev || parseInt(prev.over_ball.split('.')[0], 10) !== overNum
            const lastOfOver = !next || parseInt(next.over_ball.split('.')[0], 10) !== overNum
            const newBowler = !prev || prev.bowler !== d.bowler
            const markerCol = d.wicket_player_out_index != null
              ? d.wicket_player_out_index
              : d.batter_index
            const summary = lastOfOver ? overSummaries.get(overNum) : null
            const units = runUnits(d)

            return (
              <div key={i}>
                {/* Ball row */}
                <div
                  className="flex items-center"
                  style={{
                    height: CELL,
                    borderTop: newOver ? '1px solid var(--rule-soft)' : '1px solid transparent',
                  }}
                >
                  <div
                    style={{ width: OVER_W }}
                    className={`text-[9px] tabular-nums pr-1 text-right ${
                      newOver ? 'wisden-grid-meta font-medium' : 'wisden-grid-faint'
                    }`}
                  >
                    {d.over_ball}
                  </div>
                  <div
                    style={{ width: BOWLER_W }}
                    className={`text-[10px] truncate pr-2 text-right ${
                      newBowler ? 'wisden-grid-strong font-medium' : 'wisden-grid-faint'
                    }`}
                    title={d.bowler}
                  >
                    {newBowler ? d.bowler : '·'}
                  </div>
                  {/* batter cells */}
                  {Array.from({ length: N }).map((_, b) => {
                    const isLastBatter = b === N - 1
                    if (b !== markerCol) {
                      // Tint cells where this batter is at the crease but
                      // not facing this ball. Each batter has a "slot"
                      // (A or B), giving them one of two pale shades —
                      // alternating per partnership so adjacent batters
                      // are always distinguishable.
                      const atCrease = b === d.non_striker_index
                      return (
                        <div
                          key={b}
                          style={{
                            width: CELL,
                            height: CELL,
                            backgroundColor: atCrease ? slotColor(b) : undefined,
                            borderRight: isLastBatter ? '1px solid var(--rule)' : undefined,
                          }}
                          className={isLastBatter ? '' : 'wisden-grid-cell-right'}
                        />
                      )
                    }
                    const cellData = cellInfo(d, b === d.wicket_player_out_index)
                    return (
                      <div
                        key={b}
                        style={{
                          width: CELL,
                          height: CELL,
                          backgroundColor: cellData.bg,
                          color: cellData.color,
                          position: 'relative',
                          borderRight: isLastBatter ? '1px solid var(--rule)' : undefined,
                        }}
                        className={`${isLastBatter ? '' : 'wisden-grid-cell-right'} flex items-center justify-center text-[9px] font-semibold`}
                        title={`${d.over_ball}  ${d.bowler} to ${d.batter}: ${
                          d.wicket_text ? `OUT — ${d.wicket_text}` :
                          d.runs_total === 0 ? 'dot' :
                          `${d.runs_total} run${d.runs_total === 1 ? '' : 's'}`
                        }`}
                      >
                        {cellData.text}
                        {cellData.noBallMark && (
                          <span
                            style={{
                              position: 'absolute',
                              top: '-0.0625rem',
                              right: '0.0625rem',
                              fontSize: '0.5rem',
                              color: 'var(--accent)',
                              fontWeight: 700,
                              lineHeight: 1,
                            }}
                          >
                            n
                          </span>
                        )}
                      </div>
                    )
                  })}
                  {/* per-ball runs histogram with breakdown coloring */}
                  <div
                    style={{ width: HIST_W, display: 'flex', alignItems: 'center', borderRight: '1px solid var(--rule)', height: CELL }}
                    className="pl-1"
                  >
                    {Array.from({ length: HIST_CELLS }).map((_, k) => {
                      const unitColor = units[k]
                      return (
                        <div
                          key={k}
                          style={{
                            width: `calc(${HIST_CELL} - 1px)`,
                            height: `calc(${CELL} - 0.25rem)`,
                            backgroundColor: unitColor || 'transparent',
                            borderRight: '1px solid var(--rule-soft)',
                            position: 'relative',
                          }}
                        >
                          {k === 0 && d.runs_total > 0 && (
                            <span
                              style={{
                                position: 'absolute',
                                left: '0.0625rem',
                                top: '-0.0625rem',
                                fontSize: '0.5625rem',
                                color: 'var(--ink)',
                                fontWeight: 700,
                                lineHeight: 1,
                              }}
                            >
                              {d.runs_total}
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                  <div
                    style={{ width: SCORE_W, borderRight: '1px solid var(--rule)', height: CELL }}
                    className="text-[10px] tabular-nums pl-2 wisden-grid-meta flex items-center"
                  >
                    {d.cumulative_runs}/{d.cumulative_wickets}
                  </div>
                  <div
                    style={{ height: CELL, color: 'var(--accent)', whiteSpace: 'nowrap', flex: '0 0 auto' }}
                    className="text-[10px] pl-2 pr-3 font-medium hidden md:flex items-center"
                    title={(() => {
                      const p = partnerships.get(i)
                      const ds = dismissalScores.get(i)
                      const score = ds ? ` ${ds.runs}(${ds.balls})` : ''
                      const wkt = d.wicket_text ? `${d.wicket_player_out}${score}: ${d.wicket_text}` : ''
                      const pship = p ? `partnership ${p.number}: ${p.runs} runs (${p.balls} balls)` : ''
                      return [wkt, pship].filter(Boolean).join(' · ')
                    })()}
                  >
                    {(() => {
                      const p = partnerships.get(i)
                      const ds = dismissalScores.get(i)
                      if (d.wicket_text && p) {
                        return (
                          <>
                            {d.wicket_player_out}
                            {ds && (
                              <span className="num" style={{ color: 'var(--ink)', marginLeft: 3 }}>
                                {ds.runs}({ds.balls})
                              </span>
                            )}
                            : {d.wicket_text}
                            <span style={{ color: 'var(--ink-faint)', fontStyle: 'italic', marginLeft: 4 }}>
                              · p{p.number} {p.runs}({p.balls})
                            </span>
                          </>
                        )
                      }
                      if (d.wicket_text) {
                        return (
                          <>
                            {d.wicket_player_out}
                            {ds && (
                              <span className="num" style={{ color: 'var(--ink)', marginLeft: 3 }}>
                                {ds.runs}({ds.balls})
                              </span>
                            )}
                            : {d.wicket_text}
                          </>
                        )
                      }
                      if (p) {
                        return (
                          <span style={{ color: 'var(--ink-faint)', fontStyle: 'italic' }}>
                            p{p.number} {p.runs}({p.balls})
                          </span>
                        )
                      }
                      return ''
                    })()}
                  </div>
                </div>

                {/* Over summary row, after the last ball of each over.
                    Renders the same cell layout so the at-crease stripes
                    pass through it without breaking. */}
                {summary && (
                  <SummaryRow
                    label={`end of over ${summary.over}`}
                    detail={`${summary.runs} run${summary.runs === 1 ? '' : 's'}${summary.wickets > 0 ? `, ${summary.wickets} wkt${summary.wickets === 1 ? '' : 's'}` : ''}`}
                    score={`${d.cumulative_runs}/${d.cumulative_wickets}`}
                    striperBatterIdx={d.batter_index}
                    striperNonStrikerIdx={d.non_striker_index}
                    slotColor={slotColor}
                    N={N}
                    height={SUMMARY_H}
                    accent="gray"
                  />
                )}
              </div>
            )
          })}
        </div>
      </div>

      <div className="wisden-chart-help">
        Each row is one delivery. The colored cell sits in the on-strike batter's
        column (or the dismissed batter's column for a wicket — including
        non-striker run-outs). The histogram to the right decomposes the ball's
        runs by source: green for off the bat, yellow for wides/no-balls,
        orange for byes/leg-byes. Over summary rows mark each over's end.
      </div>
    </div>
  )
}

/**
 * A slim summary row that preserves the per-batter cell layout (so the
 * at-crease stripes pass through continuously) and overlays a label,
 * detail, and the cumulative score.
 */
function SummaryRow({
  label, detail, score,
  striperBatterIdx, striperNonStrikerIdx,
  slotColor,
  N, height, accent,
}: {
  label: string
  detail: string
  score: string
  striperBatterIdx: number | null
  striperNonStrikerIdx: number | null
  slotColor: (b: number) => string | undefined
  N: number
  height: string
  accent: 'gray' | 'blue'
}) {
  const labelClass = accent === 'blue' ? 'wisden-grid-label-blue' : 'wisden-grid-label'
  const borderTop = accent === 'blue' ? '1px solid var(--accent-soft)' : '1px solid var(--rule-soft)'
  return (
    <div
      className="flex items-center"
      style={{ height, borderTop, borderBottom: borderTop }}
    >
      <div style={{ width: OVER_W }} />
      <div
        style={{ width: BOWLER_W }}
        className={`text-[9px] italic pr-2 text-right truncate ${labelClass}`}
        title={`${label} — ${detail}`}
      >
        {label}
      </div>
      {/* batter cells: preserve the per-slot at-crease tint so each
          stripe stays continuous through the summary row. */}
      {Array.from({ length: N }).map((_, b) => {
        const isLastBatter = b === N - 1
        const atCrease = b === striperBatterIdx || b === striperNonStrikerIdx
        return (
          <div
            key={b}
            style={{
              width: CELL,
              height,
              backgroundColor: atCrease ? slotColor(b) : undefined,
              borderRight: isLastBatter ? '1px solid var(--rule)' : undefined,
            }}
            className={isLastBatter ? '' : 'wisden-grid-cell-right'}
          />
        )
      })}
      {/* histogram column: empty but bordered */}
      <div
        style={{ width: HIST_W, borderRight: '1px solid var(--rule)', height }}
        className={`text-[9px] italic pl-1 flex items-center truncate ${labelClass}`}
      >
        {detail}
      </div>
      <div
        style={{ width: SCORE_W, borderRight: '1px solid var(--rule)', height }}
        className="text-[9px] tabular-nums pl-2 wisden-grid-strong font-semibold flex items-center"
      >
        {score}
      </div>
      <div style={{ width: WKT_W, height }} className="hidden md:block" />
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        style={{
          backgroundColor: color,
          width: '0.75rem',
          height: '0.75rem',
          display: 'inline-block',
          border: '1px solid var(--rule-soft)',
        }}
      />
      {label}
    </span>
  )
}
