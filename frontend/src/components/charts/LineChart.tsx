import { LineChart as SemioticLineChart } from 'semiotic'
import { useContainerWidth } from '../../hooks/useContainerWidth'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface LineChartProps<T extends Record<string, any>> {
  data: T[]
  xAccessor?: string | ((d: T) => number)
  yAccessor?: string | ((d: T) => number)
  lineBy?: string
  colorBy?: string
  title?: string
  /** When omitted, the chart fills its container via ResizeObserver. */
  width?: number
  height?: number
  xLabel?: string
  yLabel?: string
  showPoints?: boolean
  curve?: 'linear' | 'monotoneX' | 'step'
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function LineChart<T extends Record<string, any>>({
  data, xAccessor = 'x', yAccessor = 'y', lineBy, colorBy, title,
  width, height = 400, xLabel, yLabel, showPoints, curve,
}: LineChartProps<T>) {
  const [ref, measuredWidth] = useContainerWidth()
  const effectiveWidth = width ?? measuredWidth

  return (
    <div ref={ref} className="w-full">
      {effectiveWidth > 0 && (
        <SemioticLineChart
          data={data}
          xAccessor={xAccessor}
          yAccessor={yAccessor}
          lineBy={lineBy}
          colorBy={colorBy}
          title={title}
          width={effectiveWidth}
          height={height}
          xLabel={xLabel}
          yLabel={yLabel}
          showPoints={showPoints}
          curve={curve}
          enableHover
          showGrid
        />
      )}
    </div>
  )
}
