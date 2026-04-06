import LineChart from './LineChart'
import type { ScorecardInnings } from '../../types'

interface Props {
  innings: ScorecardInnings[]
  /** When omitted, the inner LineChart fills its container. */
  width?: number
  height?: number
}

interface WormPoint {
  over: number
  cumulative: number
  team: string
  is_wicket: boolean
  // Wicket-only fields, undefined for line points
  wicket_batter?: string
  wicket_num?: number
  over_ball?: string
}

/**
 * Worm chart — cumulative runs by over, one line per innings, with
 * wicket points marked on the line.
 *
 * Strategy: combine the over-end data points with the wicket data
 * points into a single sorted-by-over data array, tag each point with
 * `is_wicket: boolean`, and use Semiotic v3's `highlight` annotation
 * type (which filters chart data by field/value and draws circles on
 * matches) to mark the wickets. The Semiotic line draws THROUGH the
 * wicket points naturally because cumulative runs are monotonic, so
 * the wickets sit ON the line at their exact (over, score) coordinate.
 *
 * Hover on any point shows the default Semiotic tooltip with the
 * point's fields, configured to surface `wicket_batter` so you see
 * which batter got out.
 */
export default function WormChart({ innings, width, height = 280 }: Props) {
  // Filter out super-over innings — they don't fit on the same axes.
  const main = innings.filter(i => !i.is_super_over)
  if (main.length === 0) return null

  const data: WormPoint[] = []
  for (const inn of main) {
    const teamPoints: WormPoint[] = [
      // Anchor at over 0 so each line starts at the origin
      { over: 0, cumulative: 0, team: inn.team, is_wicket: false },
    ]
    // Over-end points (one per over)
    for (const o of inn.by_over) {
      teamPoints.push({
        over: o.over,
        cumulative: o.cumulative,
        team: inn.team,
        is_wicket: false,
      })
    }
    // Wicket points — convert "6.5" → fractional over (5 + 5/6 ≈ 5.833)
    // The cumulative runs at the moment of the wicket are already in
    // fall_of_wickets.score.
    for (const w of inn.fall_of_wickets) {
      const [overStr, ballStr] = w.over_ball.split('.')
      const overNum = parseInt(overStr, 10)
      const ball = parseInt(ballStr || '0', 10) || 0
      const fractionalOver = (overNum - 1) + ball / 6
      teamPoints.push({
        over: fractionalOver,
        cumulative: w.score,
        team: inn.team,
        is_wicket: true,
        wicket_batter: w.batter,
        wicket_num: w.wicket,
        over_ball: w.over_ball,
      })
    }
    // Sort by over so the line draws through the points in order
    teamPoints.sort((a, b) => a.over - b.over)
    data.push(...teamPoints)
  }

  // `highlight` filters the chart's data array by field=value and
  // draws a circle at each match using the chart accessors. Perfect
  // for marking wicket points on the line.
  const annotations = [
    {
      type: 'highlight',
      field: 'is_wicket',
      value: true,
      color: '#dc2626',
      r: 5,
    },
  ]

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        Worm — cumulative runs <span className="text-xs font-normal text-gray-500">(red dots = wickets)</span>
      </h3>
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
        annotations={annotations}
        tooltip={{
          // The hover tooltip surfaces wicket_batter for wicket points.
          // For non-wicket points it stays blank, which is fine — those
          // are just over-end markers.
          fields: ['team', 'over', 'cumulative', 'wicket_batter', 'over_ball'],
        }}
      />
      {/* Wickets-fell footer per innings — kept as a sortable list
          for users who want to scan the wickets without hovering. */}
      <div className="mt-2 text-xs text-gray-600 space-y-0.5">
        {main.map(inn => (
          inn.fall_of_wickets.length > 0 && (
            <div key={inn.team}>
              <span className="font-medium text-gray-700">{inn.team} wickets:</span>{' '}
              {inn.fall_of_wickets.map((w, i) => (
                <span key={w.wicket}>
                  {i > 0 ? ', ' : ''}
                  {w.score}/{w.wicket} ({w.over_ball}, {w.batter})
                </span>
              ))}
            </div>
          )
        ))}
      </div>
    </div>
  )
}
