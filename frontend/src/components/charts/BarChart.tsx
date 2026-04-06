import { BarChart as SemioticBarChart } from 'semiotic'
import { useContainerWidth } from '../../hooks/useContainerWidth'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface BarChartProps<T extends Record<string, any>> {
  data: T[]
  categoryAccessor: string | ((d: T) => string)
  valueAccessor: string | ((d: T) => number)
  title?: string
  /** When omitted, the chart fills its container via ResizeObserver. */
  width?: number
  height?: number
  colorScheme?: string[]
  colorBy?: string
  categoryLabel?: string
  valueLabel?: string
  orientation?: 'vertical' | 'horizontal'
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function BarChart<T extends Record<string, any>>({
  data, categoryAccessor, valueAccessor, title, width, height = 400,
  colorScheme, colorBy, categoryLabel, valueLabel, orientation,
}: BarChartProps<T>) {
  const [ref, measuredWidth] = useContainerWidth()
  const effectiveWidth = width ?? measuredWidth

  return (
    <div ref={ref} className="w-full">
      {effectiveWidth > 0 && (
        <SemioticBarChart
          data={data}
          categoryAccessor={categoryAccessor}
          valueAccessor={valueAccessor}
          title={title}
          width={effectiveWidth}
          height={height}
          colorScheme={colorScheme}
          colorBy={colorBy}
          categoryLabel={categoryLabel}
          valueLabel={valueLabel}
          orientation={orientation}
          enableHover
        />
      )}
    </div>
  )
}
