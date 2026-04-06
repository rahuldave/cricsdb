import type { InningsGridInnings, InningsGridDelivery } from '../../types'

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
const WKT_W = '12rem'         // wicket-text column

// Source colors
const COLOR_OFFBAT = (runs: number): string => {
  switch (runs) {
    case 0: return '#f3f4f6'
    case 1: return '#bbf7d0'
    case 2: return '#86efac'
    case 3: return '#4ade80'
    case 4: return '#22c55e'
    case 5: return '#16a34a'
    case 6: return '#15803d'
    default: return '#166534'
  }
}
const COLOR_WIDE = '#fde047'    // yellow
const COLOR_NOBALL = '#facc15'  // slightly darker yellow
const COLOR_BYE = '#fb923c'     // orange
const COLOR_LEGBYE = '#fdba74'  // light orange
const COLOR_WICKET = '#dc2626'  // red
const COLOR_AT_CREASE = '#dbeafe' // pale blue: batter is at the crease but not facing this ball

interface CellInfo {
  bg: string
  text: string
  color: string
  noBallMark: boolean
}

function cellInfo(d: InningsGridDelivery, isDismissedColumn: boolean): CellInfo {
  if (isDismissedColumn) {
    return { bg: COLOR_WICKET, text: 'W', color: '#fff', noBallMark: false }
  }
  if (d.runs_batter > 0) {
    return {
      bg: COLOR_OFFBAT(d.runs_batter),
      text: String(d.runs_batter),
      color: d.runs_batter >= 4 ? '#fff' : '#1f2937',
      noBallMark: d.extras_noballs > 0,
    }
  }
  if (d.extras_wides > 0) {
    const extra = d.runs_total - 1
    return {
      bg: COLOR_WIDE,
      text: extra > 0 ? `w${extra}` : 'w',
      color: '#1f2937',
      noBallMark: false,
    }
  }
  if (d.extras_noballs > 0) {
    // No-ball with no off-bat runs (might still have byes/legbyes)
    return {
      bg: COLOR_NOBALL,
      text: 'n',
      color: '#1f2937',
      noBallMark: false,
    }
  }
  if (d.extras_byes > 0 || d.extras_legbyes > 0) {
    const tag = d.extras_byes > 0 ? 'b' : 'lb'
    const total = d.runs_extras
    return {
      bg: d.extras_byes > 0 ? COLOR_BYE : COLOR_LEGBYE,
      text: total > 0 ? `${tag}${total}` : tag,
      color: '#1f2937',
      noBallMark: false,
    }
  }
  return { bg: '#f3f4f6', text: '·', color: '#9ca3af', noBallMark: false }
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

export default function InningsGridChart({ innings }: Props) {
  const N = innings.batters.length
  const headerHeight = '4.5rem'
  const overSummaries = summarizeOvers(innings.deliveries)
  const partnerships = summarizePartnerships(innings.deliveries)
  const SUMMARY_H = '0.875rem'

  return (
    <div className="bg-white rounded-lg border shadow-sm p-4">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="font-semibold text-gray-900">
          {innings.team} — innings grid
        </h3>
        <div className="text-sm text-gray-600 tabular-nums">
          {innings.total_runs}/{innings.total_wickets} · {innings.total_balls} balls
        </div>
      </div>

      {/* Color legend */}
      <div className="flex flex-wrap gap-3 text-[10px] text-gray-600 mb-3">
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
        <span className="text-gray-500">
          (small <span className="font-bold text-orange-600">n</span> on a green
          cell = no-ball with off-bat runs)
        </span>
      </div>

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
                  borderRight: i === N - 1 ? '2px solid #d1d5db' : undefined,
                }}
                className="border-b border-gray-200"
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
                    color: '#374151',
                  }}
                  title={name}
                >
                  {name}
                </div>
              </div>
            ))}
            {/* histogram column header */}
            <div
              style={{ width: HIST_W, borderRight: '2px solid #d1d5db' }}
              className="text-[9px] text-gray-400 self-end border-b border-gray-200 px-1 pb-1 text-right"
            >
              runs
            </div>
            {/* score column header */}
            <div
              style={{ width: SCORE_W, borderRight: '2px solid #d1d5db' }}
              className="text-[9px] text-gray-400 self-end border-b border-gray-200 pl-2 pb-1"
            >
              score
            </div>
            {/* wicket text header — hidden on small viewports */}
            <div
              style={{ width: WKT_W }}
              className="text-[9px] text-gray-400 self-end border-b border-gray-200 pl-2 pb-1 hidden md:block"
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
                    borderTop: newOver ? '1px solid #d1d5db' : '1px solid #f9fafb',
                  }}
                >
                  <div
                    style={{ width: OVER_W }}
                    className={`text-[9px] tabular-nums pr-1 text-right ${
                      newOver ? 'text-gray-600 font-medium' : 'text-gray-300'
                    }`}
                  >
                    {d.over_ball}
                  </div>
                  <div
                    style={{ width: BOWLER_W }}
                    className={`text-[10px] truncate pr-2 text-right ${
                      newBowler ? 'text-gray-700 font-medium' : 'text-gray-300'
                    }`}
                    title={d.bowler}
                  >
                    {newBowler ? d.bowler : '·'}
                  </div>
                  {/* batter cells */}
                  {Array.from({ length: N }).map((_, b) => {
                    const isLastBatter = b === N - 1
                    if (b !== markerCol) {
                      // Faint blue tint when this batter is at the crease
                      // but not facing the current ball (i.e., they're the
                      // non-striker). Renders a continuous "presence stripe"
                      // for each batter from arrival to dismissal.
                      const atCrease = b === d.non_striker_index
                      return (
                        <div
                          key={b}
                          style={{
                            width: CELL,
                            height: CELL,
                            backgroundColor: atCrease ? COLOR_AT_CREASE : undefined,
                            borderRight: isLastBatter ? '2px solid #d1d5db' : undefined,
                          }}
                          className={isLastBatter ? '' : 'border-r border-gray-100'}
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
                          borderRight: isLastBatter ? '2px solid #d1d5db' : undefined,
                        }}
                        className={`${isLastBatter ? '' : 'border-r border-gray-100'} flex items-center justify-center text-[9px] font-semibold`}
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
                              color: '#ea580c',
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
                    style={{ width: HIST_W, display: 'flex', alignItems: 'center', borderRight: '2px solid #d1d5db', height: CELL }}
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
                            borderRight: '1px solid #f3f4f6',
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
                                color: '#000',
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
                    style={{ width: SCORE_W, borderRight: '2px solid #d1d5db', height: CELL }}
                    className="text-[10px] tabular-nums pl-2 text-gray-600 flex items-center"
                  >
                    {d.cumulative_runs}/{d.cumulative_wickets}
                  </div>
                  <div
                    style={{ width: WKT_W, height: CELL }}
                    className="text-[10px] pl-2 text-red-700 font-medium truncate hidden md:flex items-center"
                    title={d.wicket_text || ''}
                  >
                    {d.wicket_text
                      ? `${d.wicket_player_out}: ${d.wicket_text}`
                      : ''}
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
                    N={N}
                    height={SUMMARY_H}
                    accent="gray"
                  />
                )}

                {/* Partnership summary row, after a wicket OR after the
                    final ball of the innings. */}
                {partnerships.has(i) && (() => {
                  const p = partnerships.get(i)!
                  // For the partnership-end row, the stripes are for the
                  // two batters who just FINISHED the partnership. After a
                  // wicket the player_out is no longer at crease, but the
                  // partnership *ended* with both still in our visualization
                  // — show their stripe one last time.
                  return (
                    <SummaryRow
                      label={`partnership ${p.number}`}
                      detail={`${p.runs} run${p.runs === 1 ? '' : 's'} (${p.balls} ball${p.balls === 1 ? '' : 's'})`}
                      score={`${d.cumulative_runs}/${d.cumulative_wickets}`}
                      striperBatterIdx={d.batter_index}
                      striperNonStrikerIdx={d.non_striker_index}
                      N={N}
                      height={SUMMARY_H}
                      accent="blue"
                    />
                  )
                })()}
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-3 text-xs text-gray-500">
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
  N, height, accent,
}: {
  label: string
  detail: string
  score: string
  striperBatterIdx: number | null
  striperNonStrikerIdx: number | null
  N: number
  height: string
  accent: 'gray' | 'blue'
}) {
  const labelClass = accent === 'blue' ? 'text-blue-700' : 'text-gray-500'
  const borderTop = accent === 'blue' ? '1px solid #bfdbfe' : '1px solid #e5e7eb'
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
      {/* batter cells: preserve the at-crease tint so the stripe stays continuous */}
      {Array.from({ length: N }).map((_, b) => {
        const isLastBatter = b === N - 1
        const atCrease = b === striperBatterIdx || b === striperNonStrikerIdx
        return (
          <div
            key={b}
            style={{
              width: CELL,
              height,
              backgroundColor: atCrease ? COLOR_AT_CREASE : undefined,
              borderRight: isLastBatter ? '2px solid #d1d5db' : undefined,
            }}
            className={isLastBatter ? '' : 'border-r border-gray-100'}
          />
        )
      })}
      {/* histogram column: empty but bordered */}
      <div
        style={{ width: HIST_W, borderRight: '2px solid #d1d5db', height }}
        className={`text-[9px] italic pl-1 flex items-center truncate ${labelClass}`}
      >
        {detail}
      </div>
      <div
        style={{ width: SCORE_W, borderRight: '2px solid #d1d5db', height }}
        className="text-[9px] tabular-nums pl-2 text-gray-700 font-semibold flex items-center"
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
          border: '1px solid #e5e7eb',
        }}
      />
      {label}
    </span>
  )
}
