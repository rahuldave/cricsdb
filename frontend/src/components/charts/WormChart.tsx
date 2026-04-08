import LineChart from './LineChart'
import { WISDEN, WISDEN_PAIR } from './palette'
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
  // Partnership info — set on non-wicket over-end points so hovering
  // between wickets surfaces the active partnership.
  pship_number?: number
  pship_runs?: number
  pship_from?: string  // batter dismissed at start (or "innings start")
  pship_to?: string    // batter dismissed at end (or "innings ongoing")
}

interface PartnershipSpan {
  number: number
  runs: number
  startOver: number   // fractional over where partnership began
  endOver: number     // fractional over where partnership ended
  fromBatter: string  // who got out (or "innings start")
  toBatter: string    // who gets out at end (or "innings end")
}

/**
 * Compute partnerships from fall_of_wickets + final innings score.
 * Partnership N is the span from wicket N-1 (or innings start) to
 * wicket N (or innings end). Runs come from score deltas; the two
 * batters are inferred as "the dismissed batter at each boundary".
 * Per-ball balls are NOT computed because the worm chart only has
 * over-aggregated data.
 */
function computePartnerships(
  fall: { wicket: number; score: number; batter: string; over_ball: string }[],
  finalScore: number,
  finalOver: number,
): PartnershipSpan[] {
  const spans: PartnershipSpan[] = []
  let prevScore = 0
  let prevOver = 0
  let prevBatter = 'innings start'
  for (let i = 0; i < fall.length; i++) {
    const w = fall[i]
    const [overStr, ballStr] = w.over_ball.split('.')
    const overNum = parseInt(overStr, 10)
    const ball = parseInt(ballStr || '0', 10) || 0
    const fractionalOver = (overNum - 1) + ball / 6
    spans.push({
      number: i + 1,
      runs: w.score - prevScore,
      startOver: prevOver,
      endOver: fractionalOver,
      fromBatter: prevBatter,
      toBatter: w.batter,
    })
    prevScore = w.score
    prevOver = fractionalOver
    prevBatter = w.batter
  }
  if (finalScore > prevScore || fall.length === 0) {
    spans.push({
      number: fall.length + 1,
      runs: finalScore - prevScore,
      startOver: prevOver,
      endOver: finalOver,
      fromBatter: prevBatter,
      toBatter: 'not out',
    })
  }
  return spans
}

function partnershipForOver(spans: PartnershipSpan[], over: number): PartnershipSpan | null {
  for (const p of spans) {
    if (over > p.startOver && over <= p.endOver) return p
  }
  // Edge: the over==0 anchor point belongs to the first partnership
  if (spans.length > 0 && over === 0) return spans[0]
  return null
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
export default function WormChart({ innings, width, height = 480 }: Props) {
  // Filter out super-over innings — they don't fit on the same axes.
  const main = innings.filter(i => !i.is_super_over)
  if (main.length === 0) return null

  const data: WormPoint[] = []
  for (const inn of main) {
    const finalOverEnd = inn.by_over[inn.by_over.length - 1]
    const partnerships = computePartnerships(
      inn.fall_of_wickets,
      finalOverEnd?.cumulative ?? 0,
      finalOverEnd?.over ?? 0,
    )
    const tagPartnership = (over: number): Partial<WormPoint> => {
      const p = partnershipForOver(partnerships, over)
      if (!p) return {}
      return {
        pship_number: p.number,
        pship_runs: p.runs,
        pship_from: p.fromBatter,
        pship_to: p.toBatter,
      }
    }

    const teamPoints: WormPoint[] = [
      // Anchor at over 0 so each line starts at the origin
      { over: 0, cumulative: 0, team: inn.team, is_wicket: false, ...tagPartnership(0) },
    ]
    // Over-end points (one per over)
    for (const o of inn.by_over) {
      teamPoints.push({
        over: o.over,
        cumulative: o.cumulative,
        team: inn.team,
        is_wicket: false,
        ...tagPartnership(o.over),
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
      color: WISDEN.oxblood,
      r: 5,
    },
  ]

  return (
    <div>
      <h3 className="wisden-chart-title">
        Worm — cumulative runs <span className="wisden-chart-sub">(oxblood dots = wickets)</span>
      </h3>
      <LineChart
        data={data}
        xAccessor="over"
        yAccessor="cumulative"
        lineBy="team"
        colorBy="team"
        colorScheme={WISDEN_PAIR}
        xLabel="Over"
        yLabel="Runs"
        width={width}
        height={height}
        curve="monotoneX"
        annotations={annotations}
        // Function-form tooltip — returns null for non-wicket points
        // (no tooltip shows at all) and a small custom card for wicket
        // points with the dismissed batter, the over.ball, and the
        // team score at fall.
        tooltip={(d: Record<string, unknown>) => {
          // Wicket point: red oxblood top accent + dismissed batter
          if (d.is_wicket) {
            return (
              <div style={{
                background: 'var(--bg)',
                border: '1px solid var(--rule)',
                borderTop: '2px solid var(--accent)',
                padding: '6px 10px',
                fontSize: 12,
                fontFamily: 'var(--serif)',
                color: 'var(--ink)',
                whiteSpace: 'nowrap',
              }}>
                <div style={{ fontWeight: 600 }}>{String(d.wicket_batter)}</div>
                <div style={{ color: 'var(--ink-faint)', fontStyle: 'italic', fontSize: 11 }}>
                  {String(d.team)} · {String(d.over_ball)} ov · {String(d.cumulative)} runs
                </div>
              </div>
            )
          }
          // Between-wicket point: surface the active partnership
          if (d.pship_number != null) {
            return (
              <div style={{
                background: 'var(--bg)',
                border: '1px solid var(--rule)',
                borderTop: '2px solid var(--ink)',
                padding: '6px 10px',
                fontSize: 12,
                fontFamily: 'var(--serif)',
                color: 'var(--ink)',
                whiteSpace: 'nowrap',
              }}>
                <div style={{ fontWeight: 600 }}>
                  Partnership {String(d.pship_number)} —{' '}
                  <span style={{ fontFamily: 'inherit' }}>{String(d.pship_runs)}</span> runs
                </div>
                <div style={{ color: 'var(--ink-faint)', fontStyle: 'italic', fontSize: 11 }}>
                  {String(d.team)} · {String(d.pship_from)} → {String(d.pship_to)}
                </div>
              </div>
            )
          }
          return null
        }}
      />
      <div className="wisden-wickets-footer">
        {main.map(inn => (
          inn.fall_of_wickets.length > 0 && (
            <div key={inn.team}>
              <span className="lbl">{inn.team} wickets</span>{' '}
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
