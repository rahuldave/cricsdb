import LineChart from './LineChart'
import type { ScorecardInnings } from '../../types'

interface Props {
  innings: ScorecardInnings[]
  width?: number
  height?: number
}

/**
 * Worm chart — cumulative runs by over, one line per innings.
 *
 * Wicket markers are not drawn on the line itself (the existing
 * Semiotic high-level wrapper doesn't support per-point styling),
 * so wickets-fell summary lines are rendered beneath the chart
 * instead. See CLAUDE.md "Future Enhancements" item G.
 */
export default function WormChart({ innings, width = 480, height = 280 }: Props) {
  // Filter out super-over innings — they don't fit on the same axes.
  const main = innings.filter(i => !i.is_super_over)
  if (main.length === 0) return null

  // Build a flat dataset with team labels for `lineBy` grouping.
  const data: { over: number; cumulative: number; team: string }[] = []
  for (const inn of main) {
    // Anchor at over 0 so all lines start at the origin
    data.push({ over: 0, cumulative: 0, team: inn.team })
    for (const o of inn.by_over) {
      data.push({ over: o.over, cumulative: o.cumulative, team: inn.team })
    }
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Worm — cumulative runs</h3>
      <LineChart
        data={data}
        xAccessor="over"
        yAccessor="cumulative"
        lineBy="team"
        colorBy="team"
        xLabel="Over"
        yLabel="Runs"
        width={width}
        height={height}
        curve="monotoneX"
      />
      {/* Wickets-fell footer per innings */}
      <div className="mt-2 text-xs text-gray-600 space-y-0.5">
        {main.map(inn => (
          inn.fall_of_wickets.length > 0 && (
            <div key={inn.team}>
              <span className="font-medium text-gray-700">{inn.team} wickets:</span>{' '}
              {inn.fall_of_wickets.map((w, i) => (
                <span key={w.wicket}>
                  {i > 0 ? ', ' : ''}
                  {w.score}/{w.wicket} ({w.over_ball})
                </span>
              ))}
            </div>
          )
        ))}
      </div>
    </div>
  )
}
