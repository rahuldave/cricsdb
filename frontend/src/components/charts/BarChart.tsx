import { BarChart as SemioticBarChart } from 'semiotic'
import ChartContainer from './ChartContainer'
import ChartHeader from '../ChartHeader'
import { abbreviateScope } from '../scopeLinks'
import { useContainerWidth } from '../../hooks/useContainerWidth'
import { useDiscipline } from '../../hooks/useDiscipline'
import { useFilters } from '../../hooks/useFilters'
import { WISDEN_PALETTE } from './palette'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface BarChartProps<T extends Record<string, any>> {
  data: T[]
  categoryAccessor: string | ((d: T) => string)
  valueAccessor: string | ((d: T) => number)
  title?: string
  /** Faint italic line under the title, typically the filter-state
   *  abbreviation. Empty string is treated as no subtitle. */
  subtitle?: string
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
  /**
   * Annotation rendered ABOVE each bar at the top of the chart's plot
   * area. Useful for "win % above the wins-by-season bars" where the
   * chart shows raw counts but the reader needs context. Return null
   * to skip a label for a given row.
   */
  topLabelFormat?: (d: T, i: number) => string | null
  /**
   * Tier 5 of spec-apples-to-apples-baselines.md. Per-category cohort
   * reference values rendered as short dashed forest-green segments
   * over each bar at the reference value's y-position. Categories
   * absent from `referenceData` are skipped — useful when the cohort
   * baseline is only defined for some seasons (e.g. seasons with
   * enough sample to clear the cliff threshold). Use this for
   * per-category cohort overlays (closes spec §2.0 A8 for the
   * /bowling Econ-by-Over chart).
   */
  referenceData?: { category: string; value: number | null }[]
  /** Legend label for the dashed reference line series ("League avg"
   *  / "Cohort econ" etc). When omitted, no legend hint renders. */
  referenceLabel?: string
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function BarChart<T extends Record<string, any>>({
  data, categoryAccessor, valueAccessor, title, subtitle, width, height = 400,
  colorScheme = WISDEN_PALETTE, colorBy, categoryLabel, valueLabel, orientation,
  rotateCategoryLabels = 'auto',
  topLabelFormat,
  referenceData,
  referenceLabel,
}: BarChartProps<T>) {
  const [ref, measuredWidth] = useContainerWidth()
  const effectiveWidth = width ?? measuredWidth
  // Auto-subtitle: filter-state abbreviation as a faint reminder line
  // under the title. Only auto-compute when the chart has a title —
  // a titleless chart should stay titleless, not grow an orphan
  // subtitle floating above the SVG. Caller can override the
  // auto-computed value by passing `subtitle` explicitly (including ""
  // to suppress). Empty filter state collapses the line
  // (abbreviateScope returns "").
  const filters = useFilters()
  const discipline = useDiscipline()
  const effectiveSubtitle = subtitle ?? (title ? abbreviateScope(filters, { discipline }) : '')

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
  // Auto-rotate when each bar gets less than ~45px of horizontal space.
  // Earlier 28px threshold was too tight for season-year labels (e.g.
  // "2009/10") on charts that had ~50px per bar.
  const shouldRotate = (rotateCategoryLabels === true)
    || (rotateCategoryLabels === 'auto' && pxPerBar > 0 && pxPerBar < 45)

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
  // When we need precise per-bar overlays (top labels), pin Semiotic's
  // margins explicitly — Semiotic's defaults vary with axis label width,
  // so without pinning our pixel math for the label overlay drifts.
  // Note: frameProps must wrap the margin in `{ margin: ... }` (passing
  // the bare object did NOT take effect; Semiotic kept its defaults of
  // ~{ top: 50, left: 70, bottom: 60 } which threw the labels off by
  // ~20px vertically and ~10px horizontally).
  const PINNED_NORMAL_MARGIN = { top: 30, right: 20, bottom: 50, left: 60 }
  const finalHeight = shouldRotate ? height + 60 : height
  const activeMargin = shouldRotate ? ROT_MARGIN : PINNED_NORMAL_MARGIN
  const innerHeight = finalHeight - activeMargin.top - activeMargin.bottom
  // Always pass the margin via frameProps so the overlay math matches
  // what Semiotic actually renders.
  const FRAME_PROPS = topLabelFormat || shouldRotate
    ? { margin: activeMargin }
    : undefined

  const getLabel = (d: T): string => {
    const v = typeof categoryAccessor === 'function'
      ? categoryAccessor(d)
      : (d as Record<string, unknown>)[categoryAccessor as string]
    return String(v ?? '')
  }

  const getValue = (d: T): number => {
    const v = typeof valueAccessor === 'function'
      ? valueAccessor(d)
      : (d as Record<string, unknown>)[valueAccessor as string]
    if (typeof v === 'number') return v
    // Auto-unwrap MetricEnvelope so string accessors like
    // valueAccessor="run_rate" keep working after fields get wrapped
    // by the league-delta envelope migration (commit 2d9e335). Without
    // this, the chart silently degenerates to maxValue=0 because
    // TypeScript's `Record<string, unknown>` lookup erases the field
    // shape — see CLAUDE.md "API ↔ frontend type contract".
    if (v && typeof v === 'object' && typeof (v as { value?: unknown }).value === 'number') {
      return (v as { value: number }).value
    }
    return 0
  }
  // Reference data lookup keyed by category label; absent entries skip
  // the per-bar overlay segment.
  const referenceByCategory = new Map<string, number>()
  if (referenceData) {
    for (const r of referenceData) {
      if (r.value != null) referenceByCategory.set(String(r.category), r.value)
    }
  }
  // Top-label math uses the bar-only max (matches Semiotic's auto-
  // scaled y-axis); the reference overlay uses the combined max so a
  // reference value higher than any bar stays on-chart.
  const maxValue = data.reduce((m, d) => Math.max(m, getValue(d) || 0), 0)
  const refMax = referenceData
    ? Math.max(0, ...referenceData.map(r => r.value ?? 0))
    : 0
  const refScaleMax = Math.max(maxValue, refMax)

  return (
    <ChartContainer
      outerRef={ref}
      header={<ChartHeader title={title} subtitle={effectiveSubtitle} />}
    >
      {effectiveWidth > 0 && (
        <SemioticBarChart
          data={data}
          categoryAccessor={categoryAccessor}
          // Pass the envelope-unwrapping `getValue` rather than the raw
          // `valueAccessor` so Semiotic reads the unwrapped number for
          // MetricEnvelope-typed fields too (otherwise its internal
          // d[key] lookup sees the envelope object and renders 0).
          valueAccessor={getValue}
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
          frameProps={FRAME_PROPS as any}
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
                  fontFamily: 'var(--serif)',
                  fontStyle: 'italic',
                  color: 'var(--ink-faint)',
                  paddingRight: 4,
                  lineHeight: 1,
                  userSelect: 'none',
                }}>{label}</div>
              </div>
            )
          })}
        </div>
      )}
      {/* Tier 5 of spec-apples-to-apples-baselines.md — per-category
          reference overlay. Short dashed forest-green segment over
          each bar at the reference value's y-position. Same pinned-
          margin math as the topLabelFormat overlay so segment x lines
          up with the bar beneath. */}
      {referenceData && effectiveWidth > 0 && data.length > 0 && refScaleMax > 0 && (
        <div style={{
          position: 'absolute',
          left: activeMargin.left,
          top: 0,
          width: effectiveWidth - activeMargin.left - activeMargin.right,
          height: finalHeight,
          pointerEvents: 'none',
        }}>
          {data.map((d, i) => {
            const label = getLabel(d)
            const refVal = referenceByCategory.get(label)
            if (refVal == null) return null
            // Semiotic auto-scales its y-axis based on the bars (not
            // the reference). If reference > maxValue we'd draw above
            // the plot area — clamp to maxValue so the line sits on
            // the chart's top edge instead of floating off-chart.
            const scaleMax = Math.max(maxValue, refMax)
            const y = activeMargin.top + (innerHeight - (refVal / scaleMax) * innerHeight)
            const segWidth = `${(1 / data.length) * 100}%`
            const xPctCenter = ((i + 0.5) / data.length) * 100
            return (
              <div key={`ref-${i}`} style={{
                position: 'absolute',
                left: `${xPctCenter}%`,
                top: y,
                width: segWidth,
                transform: 'translate(-50%, -1px)',
                height: 2,
                background:
                  // Dashed effect via linear-gradient — semiotic
                  // doesn't expose a way to draw arbitrary SVG
                  // segments over its frame.
                  'repeating-linear-gradient(to right, #3F7A4D 0, #3F7A4D 4px, transparent 4px, transparent 7px)',
              }} />
            )
          })}
        </div>
      )}
      {/* Reference legend hint — small inline caption under the chart
          when referenceLabel is provided. Sits just under the
          finalHeight so it doesn't interfere with rotated x-axis
          labels (which live in the same band). */}
      {referenceData && referenceLabel && data.length > 0 && refScaleMax > 0 && (
        <div style={{
          position: 'absolute',
          left: activeMargin.left,
          bottom: 4,
          fontFamily: 'var(--serif)',
          fontStyle: 'italic',
          fontSize: '0.7rem',
          color: 'var(--ink-faint)',
          pointerEvents: 'none',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.3rem',
        }}>
          <span aria-hidden="true" style={{
            display: 'inline-block', width: 14, height: 2,
            background: 'repeating-linear-gradient(to right, #3F7A4D 0, #3F7A4D 4px, transparent 4px, transparent 7px)',
          }} />
          {referenceLabel}
        </div>
      )}
      {/* Top-label annotation: small labels positioned just above each
          bar's actual top. Bar height = (value/max) × innerHeight, so
          the label's y = topMargin + (innerHeight - barHeight) − offset.
          Pinning Semiotic's margins (PINNED_NORMAL_MARGIN above) keeps
          this math accurate. */}
      {topLabelFormat && effectiveWidth > 0 && data.length > 0 && (
        <div style={{
          position: 'absolute',
          left: activeMargin.left,
          top: 0,
          width: effectiveWidth - activeMargin.left - activeMargin.right,
          height: finalHeight,
          pointerEvents: 'none',
        }}>
          {data.map((d, i) => {
            const label = topLabelFormat(d, i)
            if (label == null) return null
            const v = getValue(d)
            const barH = maxValue > 0 ? (v / maxValue) * innerHeight : 0
            const labelTop = activeMargin.top + (innerHeight - barH) - 14
            const xPct = ((i + 0.5) / data.length) * 100
            return (
              <div key={i} style={{
                position: 'absolute',
                left: `${xPct}%`,
                top: labelTop,
                transform: 'translateX(-50%)',
                fontSize: 11,
                fontFamily: 'var(--sans)',
                color: 'var(--oxblood, #7A1F1F)',
                whiteSpace: 'nowrap',
                lineHeight: 1,
              }}>{label}</div>
            )
          })}
        </div>
      )}
    </ChartContainer>
  )
}
