import { LineChart as SemioticLineChart } from 'semiotic'
import ChartHeader from '../ChartHeader'
import { abbreviateScope } from '../scopeLinks'
import { useContainerWidth } from '../../hooks/useContainerWidth'
import { useFilters } from '../../hooks/useFilters'
import { WISDEN_PALETTE } from './palette'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface LineChartProps<T extends Record<string, any>> {
  data: T[]
  xAccessor?: string | ((d: T) => number)
  yAccessor?: string | ((d: T) => number)
  lineBy?: string
  colorBy?: string
  colorScheme?: string[]
  title?: string
  /** Faint italic line under the title, typically the filter-state
   *  abbreviation. Empty string is treated as no subtitle. */
  subtitle?: string
  /** When omitted, the chart fills its container via ResizeObserver. */
  width?: number
  height?: number
  xLabel?: string
  yLabel?: string
  showPoints?: boolean
  curve?: 'linear' | 'monotoneX' | 'step'
  /** Pass-through to Semiotic — used for annotations like wicket markers. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  annotations?: any[]
  /** Pass-through to Semiotic — title accessor + fields config. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tooltip?: any
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function LineChart<T extends Record<string, any>>({
  data, xAccessor = 'x', yAccessor = 'y', lineBy, colorBy,
  colorScheme = WISDEN_PALETTE, title, subtitle,
  width, height = 400, xLabel, yLabel, showPoints, curve,
  annotations, tooltip,
}: LineChartProps<T>) {
  const [ref, measuredWidth] = useContainerWidth()
  const effectiveWidth = width ?? measuredWidth
  // Auto-subtitle from filter state — see BarChart for rationale.
  const filters = useFilters()
  const effectiveSubtitle = subtitle ?? (title ? abbreviateScope(filters) : '')

  return (
    <div ref={ref} className="w-full">
      <ChartHeader title={title} subtitle={effectiveSubtitle} />
      {effectiveWidth > 0 && (
        <SemioticLineChart
          data={data}
          xAccessor={xAccessor}
          yAccessor={yAccessor}
          lineBy={lineBy}
          colorBy={colorBy}
          colorScheme={colorScheme}
          width={effectiveWidth}
          height={height}
          xLabel={xLabel}
          yLabel={yLabel}
          showPoints={showPoints}
          curve={curve}
          annotations={annotations}
          tooltip={tooltip}
          // Default the legend below the chart so long category labels
          // (e.g. team names like "Sunrisers Hyderabad") don't get
          // clipped by the chart card on narrow screens.
          legendPosition="bottom"
          enableHover
          showGrid
        />
      )}
    </div>
  )
}
