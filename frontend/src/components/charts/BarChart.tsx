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

  // True rotation isn't viable with Semiotic v3's high-level BarChart:
  // the `categoryFormat` hook puts its result inside a <foreignObject>
  // <div>, so SVG <text transform="rotate(...)"> is ignored, and the
  // wrapper overrides anything passed via frameProps.oLabel. Instead
  // we *thin* the labels — return empty string for indices that would
  // overlap, so only every Nth tick prints a label. The bars
  // themselves stay densely packed.
  const pxPerBar = data.length > 0 ? effectiveWidth / data.length : 0
  const dense = (rotateCategoryLabels === true)
    || (rotateCategoryLabels === 'auto' && pxPerBar > 0 && pxPerBar < 28)
  // Aim for at least ~32px between printed labels.
  const stride = dense ? Math.max(1, Math.ceil(32 / Math.max(pxPerBar, 1))) : 1
  // Always show the first and last label so the user can read the
  // axis range. The first goes via index===0 in the modulo; for the
  // last we add a fallback when (data.length-1) % stride !== 0.
  const lastIndex = data.length - 1
  const categoryFormat = stride > 1
    ? (label: string, index?: number): string => {
        if (index == null) return label
        if (index === 0 || index === lastIndex) return label
        return index % stride === 0 ? label : ''
      }
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
          height={height}
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
