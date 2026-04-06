import BarChart from './BarChart'
import { WISDEN_PAIR } from './palette'
import type { ScorecardInnings } from '../../types'

interface Props {
  innings: ScorecardInnings[]
  width?: number
  height?: number
}

const COLORS = WISDEN_PAIR

/**
 * Manhattan chart — runs scored in each over.
 *
 * Renders one bar chart per non-super-over innings, stacked vertically
 * inside the container. Color cycles through a small palette so the
 * two innings are visually distinct from the worm.
 */
export default function ManhattanChart({ innings, width, height = 140 }: Props) {
  const main = innings.filter(i => !i.is_super_over)
  if (main.length === 0) return null

  return (
    <div>
      <h3 className="wisden-chart-title">Manhattan — runs per over</h3>
      <div className="space-y-3">
        {main.map((inn, idx) => (
          <div key={inn.innings_number}>
            <div className="wisden-chart-sub" style={{ marginBottom: '0.25rem' }}>{inn.team}</div>
            <BarChart
              data={inn.by_over.map(o => ({
                over: String(o.over),
                runs: o.runs,
                wickets: o.wickets,
              }))}
              categoryAccessor="over"
              valueAccessor="runs"
              width={width}
              height={height}
              colorScheme={[COLORS[idx % COLORS.length]]}
              categoryLabel="Over"
              valueLabel="Runs"
            />
          </div>
        ))}
      </div>
    </div>
  )
}
