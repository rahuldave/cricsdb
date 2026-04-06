import type { InningsGridInnings, InningsGridDelivery } from '../../types'

interface Props {
  innings: InningsGridInnings
}

const CELL = 16        // px width and height of one batter cell
const BOWLER_W = 110   // px width of the bowler-name column
const OVER_W = 32      // px width of the over.ball column
const SCORE_W = 56     // px width of the score column on the right

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
  ring?: string  // optional ring color (for wickets on top of an extras color)
}

function cellInfo(d: InningsGridDelivery): CellInfo {
  const isWide = d.extras_wides > 0
  const isNoBall = d.extras_noballs > 0
  const isBye = d.extras_byes > 0
  const isLegBye = d.extras_legbyes > 0
  const isWicket = d.wicket_kind != null

  // Wicket is the most important — it always wins the background.
  if (isWicket) {
    return { bg: '#dc2626', text: 'W' }
  }
  // Wides / no-balls → yellow. Show w/n + run total if any.
  if (isWide || isNoBall) {
    const tag = isWide ? 'w' : 'n'
    const total = d.runs_total
    return { bg: '#fde047', text: total > 1 ? `${tag}${total - 1}` : tag }
  }
  // Byes / leg-byes → orange. Show b/lb + count.
  if (isBye || isLegBye) {
    const tag = isBye ? 'b' : 'lb'
    const total = d.runs_extras  // bye/legbye runs
    return { bg: '#fb923c', text: total > 0 ? `${tag}${total}` : tag }
  }
  // Off-bat runs.
  return {
    bg: offBatColor(d.runs_batter),
    text: d.runs_batter > 0 ? String(d.runs_batter) : '·',
  }
}

export default function InningsGridChart({ innings }: Props) {
  const N = innings.batters.length
  const headerHeight = 70  // tall enough for rotated batter names

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
      </div>

      <div className="overflow-x-auto">
        <div style={{ display: 'inline-block', minWidth: '100%' }}>
          {/* Header row: batter names rotated */}
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
                }}
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
            <div style={{ width: SCORE_W }} className="border-b border-gray-200" />
          </div>

          {/* Ball rows */}
          {innings.deliveries.map((d, i) => {
            const prev = i > 0 ? innings.deliveries[i - 1] : null
            const newOver = !prev || prev.over_ball.split('.')[0] !== d.over_ball.split('.')[0]
            const newBowler = !prev || prev.bowler !== d.bowler
            const ci = cellInfo(d)
            return (
              <div
                key={i}
                className="flex items-center"
                style={{
                  height: CELL,
                  borderTop: newOver ? '1px solid #e5e7eb' : '1px solid #f9fafb',
                }}
              >
                {/* over.ball */}
                <div
                  style={{ width: OVER_W }}
                  className={`text-[9px] tabular-nums pr-1 text-right ${
                    newOver ? 'text-gray-600 font-medium' : 'text-gray-300'
                  }`}
                >
                  {d.over_ball}
                </div>
                {/* bowler */}
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
                  if (b !== d.batter_index) {
                    return (
                      <div
                        key={b}
                        style={{ width: CELL, height: CELL }}
                        className="border-r border-gray-100"
                      />
                    )
                  }
                  return (
                    <div
                      key={b}
                      style={{
                        width: CELL,
                        height: CELL,
                        backgroundColor: ci.bg,
                        color: d.runs_batter >= 4 || ci.bg === '#dc2626' ? '#fff' : '#1f2937',
                      }}
                      className="border-r border-gray-100 flex items-center justify-center text-[9px] font-semibold"
                      title={`${d.over_ball}  ${d.bowler} to ${d.batter}: ${
                        d.wicket_kind ? `OUT (${d.wicket_kind})` :
                        d.runs_total === 0 ? 'dot' :
                        `${d.runs_total} run${d.runs_total === 1 ? '' : 's'}` +
                          (d.extras_wides ? ' (wide)' : '') +
                          (d.extras_noballs ? ' (no-ball)' : '') +
                          (d.extras_byes ? ' (byes)' : '') +
                          (d.extras_legbyes ? ' (leg-byes)' : '')
                      }`}
                    >
                      {ci.text}
                    </div>
                  )
                })}
                {/* score on the right */}
                <div
                  style={{ width: SCORE_W }}
                  className="text-[10px] tabular-nums pl-2 text-gray-600"
                >
                  {d.cumulative_runs}/{d.cumulative_wickets}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-3 text-xs text-gray-500">
        Each row is one delivery. The colored cell sits in the on-strike batter's
        column. Hover any cell for details. Vertical extent of a column = how
        long that batter was at the crease.
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
