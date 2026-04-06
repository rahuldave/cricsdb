import { Scatterplot } from 'semiotic'
import { useContainerWidth } from '../../hooks/useContainerWidth'
import { WISDEN_PALETTE, WISDEN } from './palette'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface ScatterChartProps<T extends Record<string, any>> {
  data: T[]
  xAccessor?: string | ((d: T) => number)
  yAccessor?: string | ((d: T) => number)
  sizeBy?: string | ((d: T) => number)
  colorBy?: string
  colorScheme?: string[]
  pointColor?: string
  title?: string
  /** When omitted, the chart fills its container via ResizeObserver. */
  width?: number
  height?: number
  xLabel?: string
  yLabel?: string
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function ScatterChart<T extends Record<string, any>>({
  data, xAccessor = 'x', yAccessor = 'y', sizeBy, colorBy,
  colorScheme = WISDEN_PALETTE, pointColor = WISDEN.ink, title,
  width, height = 400, xLabel, yLabel,
  tooltip, annotations, pointIdAccessor, frameProps,
}: ScatterChartProps<T>) {
  const [ref, measuredWidth] = useContainerWidth()
  const effectiveWidth = width ?? measuredWidth

  return (
    <div ref={ref} className="w-full">
      {effectiveWidth > 0 && (
        <Scatterplot
          data={data}
          xAccessor={xAccessor}
          yAccessor={yAccessor}
          sizeBy={sizeBy}
          colorBy={colorBy}
          colorScheme={colorScheme}
          style={colorBy ? undefined : { fill: pointColor, fillOpacity: 0.55, stroke: pointColor, strokeWidth: 0.5 }}
          title={title}
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
    </div>
  )
}
