import { BarChart as SemioticBarChart } from 'semiotic'

interface BarChartProps<T extends Record<string, any>> {
  data: T[]
  categoryAccessor: string | ((d: T) => string)
  valueAccessor: string | ((d: T) => number)
  title?: string
  width?: number
  height?: number
  colorScheme?: string[]
  colorBy?: string
  categoryLabel?: string
  valueLabel?: string
  orientation?: 'vertical' | 'horizontal'
}

export default function BarChart<T extends Record<string, any>>({
  data, categoryAccessor, valueAccessor, title, width = 500, height = 400,
  colorScheme, colorBy, categoryLabel, valueLabel, orientation,
}: BarChartProps<T>) {
  return (
    <SemioticBarChart
      data={data}
      categoryAccessor={categoryAccessor}
      valueAccessor={valueAccessor}
      title={title}
      width={width}
      height={height}
      colorScheme={colorScheme}
      colorBy={colorBy}
      categoryLabel={categoryLabel}
      valueLabel={valueLabel}
      orientation={orientation}
      enableHover
    />
  )
}
