import { useEffect, useRef } from 'react'
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
  /** When both are set, the matching cell is outlined and scrolled into view. */
  highlightBatterId?: string | null
  highlightBowlerId?: string | null
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

// Heatmap tints — all from the palette tokens defined in index.css
// (--tint-wicket, --tint-strong, --tint-soft). Empty cells fade to
// the soft cream so they recede behind active cells.
function cellBg(cell: Cell): string | undefined {
  if (cell.balls === 0) return 'var(--bg-soft)'
  if (cell.wickets > 0) return 'var(--tint-wicket)'
  if (cell.balls >= 4) {
    const sr = (cell.runs / cell.balls) * 100
    if (sr >= 200) return 'var(--tint-strong)'
    if (sr >= 150) return 'var(--tint-soft)'
  }
  return 'var(--bg)'
}

export default function MatchupGridChart({ innings, linkParams = '', highlightBatterId, highlightBowlerId }: Props) {
  const numBatters = innings.batters.length
  const numBowlers = innings.bowlers.length
  const matrix = buildMatrix(innings.deliveries, numBatters, numBowlers)

  const hlBatterIdx = highlightBatterId ? innings.batter_ids.indexOf(highlightBatterId) : -1
  const hlBowlerIdx = highlightBowlerId ? innings.bowler_ids.indexOf(highlightBowlerId) : -1
  const hasHighlight = hlBatterIdx >= 0 && hlBowlerIdx >= 0

  const highlightCellRef = useRef<HTMLTableCellElement | null>(null)
  useEffect(() => {
    if (hasHighlight && highlightCellRef.current) {
      highlightCellRef.current.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' })
    }
  }, [hasHighlight, hlBatterIdx, hlBowlerIdx])

  const h2hHref = (
    batterId: string | null,
    bowlerId: string | null,
  ): string | null => {
    if (!batterId || !bowlerId) return null
    return `/head-to-head?batter=${encodeURIComponent(batterId)}&bowler=${encodeURIComponent(bowlerId)}${linkParams ? '&' + linkParams : ''}`
  }

  return (
    <div>
      <div className="section-head">
        <span className="section-label">{innings.team} — matchup grid</span>
        <span className="wisden-chart-sub">batters × bowlers · click any cell for the head-to-head</span>
      </div>
      <div className="rule" />
      <div className="wisden-scroll-hint">← swipe to scroll →</div>

      <div className="overflow-x-auto">
        <table
          className="wisden-matchup-grid"
          style={{ borderCollapse: 'separate', borderSpacing: 0, minWidth: '100%' }}
        >
          <thead>
            <tr>
              <th
                className="corner"
                style={{
                  position: 'sticky',
                  left: 0,
                  background: 'var(--bg)',
                  minWidth: '7rem',
                  paddingRight: '0.5rem',
                  paddingBottom: '0.25rem',
                  borderBottom: '1px solid var(--rule)',
                  borderRight: '1px solid var(--rule)',
                  zIndex: 1,
                }}
              >
                batter \ bowler
              </th>
              {innings.bowlers.map((b, j) => (
                <th
                  key={j}
                  className="bowler-head"
                  style={{
                    width: '3.5rem',
                    height: '4rem',
                    minWidth: '3.5rem',
                    verticalAlign: 'bottom',
                    paddingBottom: '0.25rem',
                    borderBottom: '1px solid var(--rule)',
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
                  className="batter-head"
                  style={{
                    position: 'sticky',
                    left: 0,
                    background: 'var(--bg)',
                    paddingRight: '0.5rem',
                    paddingTop: '0.25rem',
                    paddingBottom: '0.25rem',
                    borderRight: '1px solid var(--rule)',
                    borderBottom: '1px solid var(--rule-soft)',
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
                    ? <span style={{ color: 'var(--ink-faint)', opacity: 0.4 }}>·</span>
                    : (
                        <span>
                          <span style={{ color: 'var(--ink)', fontWeight: 600 }}>{cell.runs}</span>
                          <span style={{ color: 'var(--ink-faint)' }}>({cell.balls})</span>
                          {cell.wickets > 0 && (
                            <sup style={{ color: 'var(--accent)', fontWeight: 700, marginLeft: 1 }}>
                              {cell.wickets}w
                            </sup>
                          )}
                        </span>
                      )
                  const isHL = hasHighlight && i === hlBatterIdx && j === hlBowlerIdx
                  return (
                    <td
                      key={j}
                      ref={isHL ? highlightCellRef : undefined}
                      style={{
                        backgroundColor: isHL ? 'var(--highlight)' : cellBg(cell),
                        textAlign: 'center',
                        verticalAlign: 'middle',
                        height: '1.5rem',
                        borderRight: '1px solid var(--rule-soft)',
                        borderBottom: '1px solid var(--rule-soft)',
                        boxShadow: isHL ? 'inset 0 0 0 2px var(--accent)' : undefined,
                      }}
                      title={
                        cell.balls === 0
                          ? `${batter} vs ${bowler}: did not face`
                          : `${batter} vs ${bowler}: ${cell.runs} run${cell.runs === 1 ? '' : 's'} off ${cell.balls} ball${cell.balls === 1 ? '' : 's'}${cell.wickets > 0 ? `, ${cell.wickets} wicket${cell.wickets === 1 ? '' : 's'}` : ''}`
                      }
                    >
                      {href ? (
                        <Link to={href} className="matchup-cell-link">
                          {content}
                        </Link>
                      ) : (
                        <span className="matchup-cell-link">{content}</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="wisden-chart-help">
        Each cell shows <span style={{ color: 'var(--ink)', fontWeight: 600 }}>runs</span><span style={{ color: 'var(--ink-faint)' }}>(balls)</span><sup style={{ color: 'var(--accent)' }}>w</sup> for that batter vs that bowler. Cells with SR ≥ 150 are tinted ochre; cells with a wicket are tinted oxblood. Click any cell for the full career head-to-head.
      </div>
    </div>
  )
}
