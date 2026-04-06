import type { InningsGridInnings, InningsGridDelivery } from '../../types'

interface Props {
  innings: InningsGridInnings
}

const CELL = 16          // px width and height of one batter cell
const BOWLER_W = 110     // bowler-name column
const OVER_W = 32        // over.ball column
const HIST_CELL = 9      // each histogram cell
const HIST_CELLS = 7     // up to 7 runs (covers boundary off no-ball: 5)
const HIST_W = HIST_CELLS * HIST_CELL
const SCORE_W = 44       // cum-score column
const WKT_W = 180        // wicket-text column

// Off-bat runs → shades of green. Light gray for dot.
function offBatColor(runs: number): string {
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

interface CellInfo {
  bg: string
  text: string
  color: string
  noBallMark: boolean   // small "n" overlay for no-balls with off-bat runs
}

function cellInfo(d: InningsGridDelivery, isDismissedColumn: boolean): CellInfo {
  // The dismissed batter's column always wins — wicket marker.
  if (isDismissedColumn) {
    return { bg: '#dc2626', text: 'W', color: '#fff', noBallMark: false }
  }
  // Off-bat runs take precedence over wide/no-ball framing — if the
  // batter actually scored runs, show that as the primary signal.
  // A no-ball with a boundary off the bat is a 4 first and a no-ball
  // second; we mark the no-ball with a small "n" overlay.
  if (d.runs_batter > 0) {
    return {
      bg: offBatColor(d.runs_batter),
      text: String(d.runs_batter),
      color: d.runs_batter >= 4 ? '#fff' : '#1f2937',
      noBallMark: d.extras_noballs > 0,
    }
  }
  // No off-bat runs. Now categorize by extras.
  if (d.extras_wides > 0) {
    // Total - 1 = extra wide runs (e.g., wide + 2 ran = "w2")
    const extra = d.runs_total - 1
    return {
      bg: '#fde047',
      text: extra > 0 ? `w${extra}` : 'w',
      color: '#1f2937',
      noBallMark: false,
    }
  }
  if (d.extras_noballs > 0) {
    return {
      bg: '#fde047',
      text: 'n',
      color: '#1f2937',
      noBallMark: false,
    }
  }
  if (d.extras_byes > 0 || d.extras_legbyes > 0) {
    const tag = d.extras_byes > 0 ? 'b' : 'lb'
    const total = d.runs_extras
    return {
      bg: '#fb923c',
      text: total > 0 ? `${tag}${total}` : tag,
      color: '#1f2937',
      noBallMark: false,
    }
  }
  // True dot ball.
  return { bg: '#f3f4f6', text: '·', color: '#9ca3af', noBallMark: false }
}

export default function InningsGridChart({ innings }: Props) {
  const N = innings.batters.length
  const headerHeight = 70

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
        <Legend color={offBatColor(0)} label="dot" />
        <Legend color={offBatColor(1)} label="1" />
        <Legend color={offBatColor(2)} label="2" />
        <Legend color={offBatColor(4)} label="4" />
        <Legend color={offBatColor(6)} label="6" />
        <Legend color="#fb923c" label="byes / leg-byes" />
        <Legend color="#fde047" label="wides / no-balls" />
        <Legend color="#dc2626" label="wicket" />
        <span className="text-gray-500">
          (a small <span className="font-bold text-orange-600">n</span> on a green
          cell = no-ball with runs off the bat)
        </span>
      </div>

      <div className="overflow-x-auto">
        <div style={{ display: 'inline-block', minWidth: '100%' }}>
          {/* Header row: rotated batter names */}
          <div className="flex" style={{ height: headerHeight }}>
            <div style={{ width: OVER_W }} />
            <div style={{ width: BOWLER_W }} />
            {innings.batters.map((name, i) => (
              <div
                key={i}
                style={{ width: CELL, height: headerHeight, position: 'relative' }}
                className="border-b border-gray-200"
              >
                <div
                  style={{
                    position: 'absolute',
                    bottom: 4,
                    left: CELL / 2,
                    transformOrigin: '0 0',
                    transform: 'rotate(-60deg)',
                    whiteSpace: 'nowrap',
                    fontSize: 10,
                    color: '#374151',
                  }}
                  title={name}
                >
                  {name}
                </div>
              </div>
            ))}
            {/* histogram + score + wicket headers */}
            <div
              style={{ width: HIST_W }}
              className="text-[9px] text-gray-400 self-end border-b border-gray-200 px-1 pb-1 text-right"
            >
              runs
            </div>
            <div
              style={{ width: SCORE_W }}
              className="text-[9px] text-gray-400 self-end border-b border-gray-200 pl-2 pb-1"
            >
              score
            </div>
            <div
              style={{ width: WKT_W }}
              className="text-[9px] text-gray-400 self-end border-b border-gray-200 pl-2 pb-1"
            >
              wicket
            </div>
          </div>

          {/* Ball rows */}
          {innings.deliveries.map((d, i) => {
            const prev = i > 0 ? innings.deliveries[i - 1] : null
            const newOver = !prev || prev.over_ball.split('.')[0] !== d.over_ball.split('.')[0]
            const newBowler = !prev || prev.bowler !== d.bowler
            // Which column does the colored cell belong to?
            // - Wicket: dismissed batter's column (might be non-striker for run-out)
            // - Otherwise: on-strike batter's column
            const markerCol = d.wicket_player_out_index != null
              ? d.wicket_player_out_index
              : d.batter_index
            return (
              <div
                key={i}
                className="flex items-center"
                style={{
                  height: CELL,
                  borderTop: newOver ? '1px solid #e5e7eb' : '1px solid #f9fafb',
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
                {/* batter cells — special-case the marker column */}
                {Array.from({ length: N }).map((_, b) => {
                  if (b !== markerCol) {
                    return (
                      <div
                        key={b}
                        style={{ width: CELL, height: CELL }}
                        className="border-r border-gray-100"
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
                      }}
                      className="border-r border-gray-100 flex items-center justify-center text-[9px] font-semibold"
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
                            top: -1,
                            right: 1,
                            fontSize: 8,
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
                {/* per-ball runs histogram */}
                <div
                  style={{ width: HIST_W, display: 'flex', alignItems: 'center' }}
                  className="pl-1"
                >
                  {Array.from({ length: HIST_CELLS }).map((_, k) => {
                    const filled = k < d.runs_total
                    return (
                      <div
                        key={k}
                        style={{
                          width: HIST_CELL - 1,
                          height: CELL - 4,
                          backgroundColor: filled ? offBatColor(Math.min(d.runs_total, 6)) : 'transparent',
                          borderRight: '1px solid #f3f4f6',
                          position: 'relative',
                        }}
                      >
                        {/* numeric label in the leftmost filled cell */}
                        {k === 0 && d.runs_total > 0 && (
                          <span
                            style={{
                              position: 'absolute',
                              left: 1,
                              top: -1,
                              fontSize: 9,
                              color: '#000',
                              fontWeight: 600,
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
                  style={{ width: SCORE_W }}
                  className="text-[10px] tabular-nums pl-2 text-gray-600"
                >
                  {d.cumulative_runs}/{d.cumulative_wickets}
                </div>
                <div
                  style={{ width: WKT_W }}
                  className="text-[10px] pl-2 text-red-700 font-medium truncate"
                  title={d.wicket_text || ''}
                >
                  {d.wicket_text
                    ? `${d.wicket_player_out}: ${d.wicket_text}`
                    : ''}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-3 text-xs text-gray-500">
        Each row is one delivery. The colored cell is in the on-strike batter's
        column (or the dismissed batter's column for a wicket — including
        non-striker run-outs). The histogram to the right shows runs scored on
        that ball; cumulative score and wicket details follow.
      </div>
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        style={{
          backgroundColor: color,
          width: 12,
          height: 12,
          display: 'inline-block',
          border: '1px solid #e5e7eb',
        }}
      />
      {label}
    </span>
  )
}
