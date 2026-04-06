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

  // When rotating, we suppress Semiotic's default labels (which live
  // inside <foreignObject> and break in Safari with any positioning
  // or transform tricks) and render our own as plain HTML elements
  // overlaid OUTSIDE the SVG, where Safari handles transforms fine.
  //
  // Computing bar positions: Semiotic's chart area sits inside the
  // chart's SVG with internal margins. We override those margins via
  // frameProps so we know the exact left offset and inner width to
  // use for the overlay. Each bar's center is then at
  // (i + 0.5) / data.length of the inner width.
  const ROT_MARGIN = { top: 50, right: 20, bottom: 90, left: 60 }
  const NORMAL_MARGIN = undefined // let Semiotic use its defaults
  const finalHeight = shouldRotate ? height + 60 : height

  const getLabel = (d: T): string => {
    const v = typeof categoryAccessor === 'function'
      ? categoryAccessor(d)
      : (d as Record<string, unknown>)[categoryAccessor as string]
    return String(v ?? '')
  }

  return (
    <div ref={ref} className="w-full" style={{ position: 'relative' }}>
      {effectiveWidth > 0 && (
        <SemioticBarChart
          data={data}
          categoryAccessor={categoryAccessor}
          valueAccessor={valueAccessor}
          title={title}
          width={effectiveWidth}
          height={finalHeight}
          colorScheme={colorScheme}
          colorBy={colorBy}
          // When rotating, drop the axis label — Semiotic positions it
          // inside the bottom margin where our rotated overlay lives,
          // so the two visually collide. The rotated labels themselves
          // tell the user what's on the x-axis.
          categoryLabel={shouldRotate ? undefined : categoryLabel}
          valueLabel={valueLabel}
          orientation={orientation}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          categoryFormat={shouldRotate ? ((() => '') as any) : undefined}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          frameProps={shouldRotate ? ({ margin: ROT_MARGIN } as any) : NORMAL_MARGIN}
          // Default legend below the chart so long phase/category
          // labels (e.g. "Powerplay") don't get clipped by the card
          // on narrow screens.
          legendPosition="bottom"
          enableHover
        />
      )}
      {shouldRotate && effectiveWidth > 0 && data.length > 0 && (
        <div style={{
          position: 'absolute',
          left: ROT_MARGIN.left,
          top: finalHeight - ROT_MARGIN.bottom + 6,
          width: effectiveWidth - ROT_MARGIN.left - ROT_MARGIN.right,
          height: 0,
          pointerEvents: 'none',
        }}>
          {data.map((d, i) => {
            const label = getLabel(d)
            const xPct = ((i + 0.5) / data.length) * 100
            return (
              <div key={i} style={{
                position: 'absolute',
                left: `${xPct}%`,
                top: 0,
                width: 0,
                height: 0,
              }}>
                <div style={{
                  position: 'absolute',
                  right: 0,
                  top: 0,
                  transformOrigin: '100% 0',
                  transform: 'rotate(-60deg)',
                  whiteSpace: 'nowrap',
                  fontSize: 11,
                  color: '#555',
                  paddingRight: 4,
                  lineHeight: 1,
                  userSelect: 'none',
                }}>{label}</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
