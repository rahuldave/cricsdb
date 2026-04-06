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

  // Rotate the x-axis tick labels to vertical when bars get too dense
  // for horizontal text.
  //
  // Semiotic v3 puts categoryFormat's result inside a <foreignObject>
  // containing a <div> (overflow:visible). Returning an SVG <text>
  // doesn't work — it becomes unknown HTML inside the div and the SVG
  // `transform` attribute is ignored. The trick: return an HTML <div>
  // with a CSS `transform: rotate(...)`, which works because divs DO
  // honor CSS transforms, and the foreignObject's overflow:visible
  // lets the rotated content extend beyond its 60×24 bounds.
  //
  // Anchor the rotation at the top-right of the inner div (which we
  // position at the horizontal center of the foreignObject = the tick
  // mark, slightly above the foreignObject top) so the END of the
  // label touches the tick and the rest trails down-and-to-the-left.
  const pxPerBar = data.length > 0 ? effectiveWidth / data.length : 0
  const shouldRotate = (rotateCategoryLabels === true)
    || (rotateCategoryLabels === 'auto' && pxPerBar > 0 && pxPerBar < 28)

  const categoryFormat = shouldRotate
    ? (label: string) => (
        // Safari's foreignObject content layout is fragile — both
        // position:absolute and padding-right:50% trick fail in
        // different ways. Most reliable cross-browser: just rotate
        // an inline-block in its natural flow position (Semiotic's
        // wrapper centers it horizontally with text-align:center).
        // Rotation pivot is the bounding-box center, so the rotated
        // text sits centered on each tick.
        <span style={{
          display: 'inline-block',
          transform: 'rotate(-60deg)',
          whiteSpace: 'nowrap',
          fontSize: 11,
          color: '#555',
          lineHeight: 1,
          userSelect: 'none',
        }}>{label}</span>
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
          // Rotated labels extend below the baseline; bump the chart
          // height so the bars get the same vertical room and the
          // labels aren't clipped at the bottom.
          height={shouldRotate ? height + 50 : height}
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
