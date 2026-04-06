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
  /**
   * Rotate the category (x-axis) tick labels to vertical. Useful when
   * categories are wide enough to overlap (e.g. year labels on a
   * by-season chart). Auto-enabled if `auto`, the chart's effective
   * width divided by the number of categories drops below ~28px.
   */
  rotateCategoryLabels?: boolean | 'auto'
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function BarChart<T extends Record<string, any>>({
  data, categoryAccessor, valueAccessor, title, width, height = 400,
  colorScheme, colorBy, categoryLabel, valueLabel, orientation,
  rotateCategoryLabels = 'auto',
}: BarChartProps<T>) {
  const [ref, measuredWidth] = useContainerWidth()
  const effectiveWidth = width ?? measuredWidth

  // Decide whether to rotate. Auto: when each category gets less than
  // ~28px, the labels are likely to overlap.
  const shouldRotate = rotateCategoryLabels === true
    || (rotateCategoryLabels === 'auto'
        && effectiveWidth > 0
        && data.length > 0
        && (effectiveWidth / data.length) < 28)

  // Returning a <text> element with a rotation transform replaces the
  // default tick label. Anchor at "end" so text grows up-and-left from
  // the rotation origin.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const categoryFormat = shouldRotate
    ? (label: string) => (
        <text
          transform="rotate(-60)"
          textAnchor="end"
          fontSize={11}
          fill="var(--semiotic-text, #555)"
          style={{ userSelect: 'none' }}
        >{label}</text>
      )
    : undefined

  return (
    <div ref={ref} className="w-full">
      {effectiveWidth > 0 && (
        <SemioticBarChart
          data={data}
          categoryAccessor={categoryAccessor}
          valueAccessor={valueAccessor}
          title={title}
          width={effectiveWidth}
          // Add bottom padding when labels are rotated so they don't
          // get clipped or collide with the axis label.
          height={shouldRotate ? height + 30 : height}
          colorScheme={colorScheme}
          colorBy={colorBy}
          categoryLabel={categoryLabel}
          valueLabel={valueLabel}
          orientation={orientation}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          categoryFormat={categoryFormat as any}
          enableHover
        />
      )}
    </div>
  )
}
