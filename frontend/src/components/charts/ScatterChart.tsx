/**
 * A scatter plot on Semiotic's `Scatterplot`, with a filter-state subtitle.
 */
import { Scatterplot } from 'semiotic'
import ChartContainer from './ChartContainer'
import ChartHeader from '../ChartHeader'
import { abbreviateScope } from '../scopeLinks'
import { useContainerWidth } from '../../hooks/useContainerWidth'
import { useDiscipline } from '../../hooks/useDiscipline'
import { useFilters } from '../../hooks/useFilters'
import { WISDEN_PALETTE, WISDEN } from './palette'
const DEFAULT_POINT = WISDEN.indigo

/** Props of `ScatterChart`. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface ScatterChartProps<T extends Record<string, any>> {
  data: T[] // the points
  xAccessor?: string | ((d: T) => number) // the field or function that gives a point's x, `'x'` by default
  yAccessor?: string | ((d: T) => number) // the field or function that gives a point's y, `'y'` by default
  sizeBy?: string | ((d: T) => number) // the field or function that sets a point's size
  colorBy?: string // the field whose value picks a point's colour from `colorScheme`
  colorScheme?: string[] // the point colours with `colorBy`, `WISDEN_PALETTE` by default
  pointColor?: string // the colour of every point when there is no `colorBy`, indigo by default
  title?: string // the chart title; with none, no auto subtitle either
  /** Faint italic line under the title, typically the filter-state
   *  abbreviation. Empty string is treated as no subtitle. */
  subtitle?: string
  /** When omitted, the chart fills its container via ResizeObserver. */
  width?: number
  height?: number // the chart height in pixels, 400 by default
  xLabel?: string // the x-axis title
  yLabel?: string // the y-axis title
  /** Pass-through to Semiotic — title accessor + fields config. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tooltip?: any
  /** Pass-through to Semiotic — array of annotation objects (labels, notes, etc). */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  annotations?: any[]
  /** Field/function returning a stable id for each point — used by point-anchored annotations. */
  pointIdAccessor?: string | ((d: T) => string)
  /** Pass-through to Semiotic — used for things like yExtent (axis flip). */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  frameProps?: any
}

/** Show a scatter plot with hover and a grid, that fills its container's width. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function ScatterChart<T extends Record<string, any>>({
  data, xAccessor = 'x', yAccessor = 'y', sizeBy, colorBy,
  colorScheme = WISDEN_PALETTE, pointColor = DEFAULT_POINT, title, subtitle,
  width, height = 400, xLabel, yLabel,
  tooltip, annotations, pointIdAccessor, frameProps,
}: ScatterChartProps<T>) {
  const [ref, measuredWidth] = useContainerWidth()
  const effectiveWidth = width ?? measuredWidth
  // Auto-subtitle from filter state — see BarChart for rationale.
  const filters = useFilters()
  const discipline = useDiscipline()
  const effectiveSubtitle = subtitle ?? (title ? abbreviateScope(filters, { discipline }) : '')

  return (
    <ChartContainer
      outerRef={ref}
      header={<ChartHeader title={title} subtitle={effectiveSubtitle} />}
    >
      {effectiveWidth > 0 && (
        <Scatterplot
          data={data}
          xAccessor={xAccessor}
          yAccessor={yAccessor}
          sizeBy={sizeBy}
          colorBy={colorBy}
          colorScheme={colorScheme}
          style={colorBy ? undefined : { fill: pointColor, fillOpacity: 0.55, stroke: pointColor, strokeWidth: 0.5 }}
          width={effectiveWidth}
          height={height}
          xLabel={xLabel}
          yLabel={yLabel}
          tooltip={tooltip}
          annotations={annotations}
          pointIdAccessor={pointIdAccessor}
          frameProps={frameProps}
          enableHover
          showGrid
        />
      )}
    </ChartContainer>
  )
}
