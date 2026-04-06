import BarChart from './BarChart'
import type { ScorecardInnings } from '../../types'

interface Props {
  innings: ScorecardInnings[]
  width?: number
  height?: number
}

const COLORS = ['#3b82f6', '#22c55e', '#f97316', '#a855f7']

/**
 * Manhattan chart — runs scored in each over.
 *
 * Renders one bar chart per non-super-over innings, stacked vertically
 * inside the container. Color cycles through a small palette so the
 * two innings are visually distinct from the worm.
 */
export default function ManhattanChart({ innings, width = 480, height = 140 }: Props) {
  const main = innings.filter(i => !i.is_super_over)
  if (main.length === 0) return null

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Manhattan — runs per over</h3>
      <div className="space-y-3">
        {main.map((inn, idx) => (
          <div key={inn.innings_number}>
            <div className="text-xs text-gray-600 mb-1">{inn.team}</div>
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
