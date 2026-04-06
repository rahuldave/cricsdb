import { Scatterplot } from 'semiotic'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface ScatterChartProps<T extends Record<string, any>> {
  data: T[]
  xAccessor?: string | ((d: T) => number)
  yAccessor?: string | ((d: T) => number)
  sizeBy?: string | ((d: T) => number)
  colorBy?: string
  title?: string
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
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function ScatterChart<T extends Record<string, any>>({
  data, xAccessor = 'x', yAccessor = 'y', sizeBy, colorBy, title,
  width = 500, height = 400, xLabel, yLabel,
  tooltip, annotations, pointIdAccessor,
}: ScatterChartProps<T>) {
  return (
    <Scatterplot
      data={data}
      xAccessor={xAccessor}
      yAccessor={yAccessor}
      sizeBy={sizeBy}
      colorBy={colorBy}
      title={title}
      width={width}
      height={height}
      xLabel={xLabel}
      yLabel={yLabel}
      tooltip={tooltip}
      annotations={annotations}
      pointIdAccessor={pointIdAccessor}
      enableHover
      showGrid
    />
  )
}
