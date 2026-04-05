import { Scatterplot } from 'semiotic'

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
}

export default function ScatterChart<T extends Record<string, any>>({
  data, xAccessor = 'x', yAccessor = 'y', sizeBy, colorBy, title,
  width = 500, height = 400, xLabel, yLabel,
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
      enableHover
      showGrid
    />
  )
}
