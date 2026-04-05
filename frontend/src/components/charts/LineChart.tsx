import { LineChart as SemioticLineChart } from 'semiotic'

interface LineChartProps<T extends Record<string, any>> {
  data: T[]
  xAccessor?: string | ((d: T) => number)
  yAccessor?: string | ((d: T) => number)
  lineBy?: string
  colorBy?: string
  title?: string
  width?: number
  height?: number
  xLabel?: string
  yLabel?: string
  showPoints?: boolean
  curve?: 'linear' | 'monotoneX' | 'step'
}

export default function LineChart<T extends Record<string, any>>({
  data, xAccessor = 'x', yAccessor = 'y', lineBy, colorBy, title,
  width = 500, height = 400, xLabel, yLabel, showPoints, curve,
}: LineChartProps<T>) {
  return (
    <SemioticLineChart
      data={data}
      xAccessor={xAccessor}
      yAccessor={yAccessor}
      lineBy={lineBy}
      colorBy={colorBy}
      title={title}
      width={width}
      height={height}
      xLabel={xLabel}
      yLabel={yLabel}
      showPoints={showPoints}
      curve={curve}
      enableHover
      showGrid
    />
  )
}
