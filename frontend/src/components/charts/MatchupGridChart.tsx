import { Link } from 'react-router-dom'
import type { InningsGridInnings, InningsGridDelivery } from '../../types'

interface Props {
  innings: InningsGridInnings
  /**
   * URL query string fragment to append to head-to-head links so the
   * destination opens pre-filtered to this match's tournament context.
   * Should NOT start with `?` or `&`.
   */
  linkParams?: string
}

// Wicket kinds that don't credit the bowler — must mirror the backend
// NON_BOWLER_WICKETS set so the matchup wicket counts agree with the
// bowling figures shown in the regular scorecard.
const NON_BOWLER_WICKETS = new Set([
  'run out',
  'retired hurt',
  'retired out',
  'obstructing the field',
])

interface Cell {
  balls: number  // legal balls only
  runs: number   // off the bat
  wickets: number
}

function buildMatrix(
  deliveries: InningsGridDelivery[],
  numBatters: number,
  numBowlers: number,
): Cell[][] {
  // matrix[batterIdx][bowlerIdx]
  const matrix: Cell[][] = Array.from({ length: numBatters }, () =>
    Array.from({ length: numBowlers }, () => ({ balls: 0, runs: 0, wickets: 0 }))
  )
  for (const d of deliveries) {
    if (d.bowler_index == null) continue
    const cell = matrix[d.batter_index]?.[d.bowler_index]
    if (!cell) continue
    // Legal balls only — wides and no-balls don't count toward balls faced
    if (d.extras_wides === 0 && d.extras_noballs === 0) {
      cell.balls++
    }
    cell.runs += d.runs_batter
    if (
      d.wicket_kind &&
      !NON_BOWLER_WICKETS.has((d.wicket_kind || '').toLowerCase())
    ) {
      // The wicket is credited to the bowler, but only if the dismissed
      // batter is the one currently facing (handles cases where a non-
      // striker gets out as a bye/leg-bye complication).
      if (d.wicket_player_out_index === d.batter_index) {
        cell.wickets++
      }
    }
  }
  return matrix
}

// Light heatmap: subtle green for high SR, light red for wickets.
function cellBg(cell: Cell): string | undefined {
  if (cell.balls === 0) return '#fafafa'
  if (cell.wickets > 0) return '#fee2e2' // red-100 — bowler dominated
  // SR-based green for cells with at least 4 balls
  if (cell.balls >= 4) {
    const sr = (cell.runs / cell.balls) * 100
    if (sr >= 200) return '#bbf7d0'
    if (sr >= 150) return '#dcfce7'
  }
  return '#ffffff'
}

export default function MatchupGridChart({ innings, linkParams = '' }: Props) {
  const numBatters = innings.batters.length
  const numBowlers = innings.bowlers.length
  const matrix = buildMatrix(innings.deliveries, numBatters, numBowlers)

  const h2hHref = (
    batterId: string | null,
    bowlerId: string | null,
  ): string | null => {
    if (!batterId || !bowlerId) return null
    return `/head-to-head?batter=${encodeURIComponent(batterId)}&bowler=${encodeURIComponent(bowlerId)}${linkParams ? '&' + linkParams : ''}`
  }

  return (
    <div className="bg-white rounded-lg border shadow-sm p-4">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="font-semibold text-gray-900">
          {innings.team} — matchup grid
        </h3>
        <div className="text-xs text-gray-500">
          batters × bowlers · click any cell for the head-to-head
        </div>
      </div>

      <div className="overflow-x-auto">
        <table
          className="text-[10px] tabular-nums"
          style={{ borderCollapse: 'separate', borderSpacing: 0, minWidth: '100%' }}
        >
          <thead>
            <tr>
              <th
                className="text-left font-medium text-gray-500 align-bottom"
                style={{
                  position: 'sticky',
                  left: 0,
                  background: '#fff',
                  minWidth: '7rem',
                  paddingRight: '0.5rem',
                  paddingBottom: '0.25rem',
                  borderBottom: '1px solid #e5e7eb',
                  borderRight: '2px solid #d1d5db',
                  zIndex: 1,
                }}
              >
                batter \ bowler
              </th>
              {innings.bowlers.map((b, j) => (
                <th
                  key={j}
                  className="font-medium text-gray-700"
                  style={{
                    width: '3.5rem',
                    height: '4rem',
                    minWidth: '3.5rem',
                    verticalAlign: 'bottom',
                    paddingBottom: '0.25rem',
                    borderBottom: '1px solid #e5e7eb',
                    position: 'relative',
                  }}
                  title={b}
                >
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '0.25rem',
                      left: '50%',
                      transformOrigin: '0 0',
                      transform: 'rotate(-60deg)',
                      whiteSpace: 'nowrap',
                      maxWidth: '4.5rem',
                    }}
                  >
                    {b}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {innings.batters.map((batter, i) => (
              <tr key={i}>
                <th
                  className="text-left font-medium text-gray-700"
                  style={{
                    position: 'sticky',
                    left: 0,
                    background: '#fff',
                    paddingRight: '0.5rem',
                    paddingTop: '0.25rem',
                    paddingBottom: '0.25rem',
                    borderRight: '2px solid #d1d5db',
                    borderBottom: '1px solid #f3f4f6',
                    minWidth: '7rem',
                    whiteSpace: 'nowrap',
                  }}
                  title={batter}
                >
                  {batter}
                </th>
                {innings.bowlers.map((bowler, j) => {
                  const cell = matrix[i][j]
                  const href = cell.balls > 0
                    ? h2hHref(innings.batter_ids[i], innings.bowler_ids[j])
                    : null
                  const content = cell.balls === 0
                    ? <span className="text-gray-300">·</span>
                    : (
                        <span>
                          <span className="font-semibold text-gray-900">{cell.runs}</span>
                          <span className="text-gray-500">({cell.balls})</span>
                          {cell.wickets > 0 && (
                            <sup className="text-red-600 font-bold ml-0.5">
                              {cell.wickets}w
                            </sup>
                          )}
                        </span>
                      )
                  return (
                    <td
                      key={j}
                      style={{
                        backgroundColor: cellBg(cell),
                        textAlign: 'center',
                        verticalAlign: 'middle',
                        height: '1.5rem',
                        borderRight: '1px solid #f3f4f6',
                        borderBottom: '1px solid #f3f4f6',
                      }}
                      title={
                        cell.balls === 0
                          ? `${batter} vs ${bowler}: did not face`
                          : `${batter} vs ${bowler}: ${cell.runs} run${cell.runs === 1 ? '' : 's'} off ${cell.balls} ball${cell.balls === 1 ? '' : 's'}${cell.wickets > 0 ? `, ${cell.wickets} wicket${cell.wickets === 1 ? '' : 's'}` : ''}`
                      }
                    >
                      {href ? (
                        <Link to={href} className="block w-full h-full px-1 text-gray-700 hover:text-blue-600 hover:underline">
                          {content}
                        </Link>
                      ) : (
                        <span className="block w-full h-full px-1">{content}</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 text-xs text-gray-500">
        Each cell shows <span className="font-semibold text-gray-900">runs</span><span className="text-gray-500">(balls)</span><sup className="text-red-600 font-bold">w</sup> for that batter vs that bowler in this innings. Cells with at least 4 balls and SR ≥ 150 are tinted green; cells with a wicket are tinted red. Click any cell to view the full career head-to-head.
      </div>
    </div>
  )
}
