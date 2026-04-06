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

  // Semiotic v3's high-level `categoryFormat` puts its result inside a
  // <foreignObject> + <div>, so SVG rotation transforms passed via
  // <text> are ignored. Instead use `frameProps.oLabel` from the
  // lower-level OrdinalFrame, which returns a real SVG element that
  // becomes the tick label.
  //
  // The label sits below the chart baseline; we render an SVG <text>
  // anchored at "end" with rotate(-60) so the end of the text touches
  // the tick mark and the rest trails down-and-to-the-left.
  const oLabel = shouldRotate
    ? (labelValue: string) => (
        <text
          textAnchor="end"
          transform="rotate(-60)"
          fontSize={11}
          fill="#555"
          dy="0.35em"
          style={{ userSelect: 'none' }}
        >{labelValue}</text>
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
          height={shouldRotate ? height + 40 : height}
          colorScheme={colorScheme}
          colorBy={colorBy}
          categoryLabel={categoryLabel}
          valueLabel={valueLabel}
          orientation={orientation}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          frameProps={oLabel ? { oLabel: oLabel as any, margin: { top: 50, right: 10, bottom: 70, left: 70 } } : undefined}
          enableHover
        />
      )}
    </div>
  )
}
