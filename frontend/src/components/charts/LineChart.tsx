import { LineChart as SemioticLineChart } from 'semiotic'
import ChartContainer from './ChartContainer'
import ChartHeader from '../ChartHeader'
import { abbreviateScope } from '../scopeLinks'
import { useContainerWidth } from '../../hooks/useContainerWidth'
import { useDiscipline } from '../../hooks/useDiscipline'
import { useFilters } from '../../hooks/useFilters'
import { WISDEN_PALETTE } from './palette'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface LineChartProps<T extends Record<string, any>> {
  data: T[]
  xAccessor?: string | ((d: T) => number)
  yAccessor?: string | ((d: T) => number)
  lineBy?: string
  colorBy?: string
  colorScheme?: string[]
  title?: string
  /** Faint italic line under the title, typically the filter-state
   *  abbreviation. Empty string is treated as no subtitle. */
  subtitle?: string
  /** When omitted, the chart fills its container via ResizeObserver. */
  width?: number
  height?: number
  xLabel?: string
  yLabel?: string
  showPoints?: boolean
  curve?: 'linear' | 'monotoneX' | 'step'
  /** Pass-through to Semiotic — used for annotations like wicket markers. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  annotations?: any[]
  /** Pass-through to Semiotic — title accessor + fields config. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tooltip?: any
  /** Optional second series rendered alongside the primary `data` —
   *  e.g. a pool-weighted league baseline against which a team's line
   *  should be read (spec-series-trend-charts.md step 11). Must share
   *  the same x and y accessors as the primary data. Forest green
   *  stroke (`internal_docs/colors.md`'s league-avg reference color);
   *  the primary keeps WISDEN_PALETTE's first color. Ignored when
   *  `lineBy` is already set (multi-series mode wins). */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  referenceData?: Record<string, any>[]
  /** Legend label for the reference series. When omitted, auto-
   *  derived from `abbreviateScope(filters, { discipline })` + " avg"
   *  so the legend always tells the reader exactly which pool the
   *  baseline aggregates over (e.g. "men's · Indian Premier League
   *  avg" / "men's · club · 2024 avg"). */
  referenceLabel?: string
  /** Legend label for the primary `data` series — default "Team". Only
   *  meaningful when `referenceData` is provided. */
  primaryLabel?: string
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function LineChart<T extends Record<string, any>>({
  data, xAccessor = 'x', yAccessor = 'y', lineBy, colorBy,
  colorScheme = WISDEN_PALETTE, title, subtitle,
  width, height = 400, xLabel, yLabel, showPoints, curve,
  annotations, tooltip,
  referenceData, referenceLabel, primaryLabel = 'Team',
}: LineChartProps<T>) {
  const [ref, measuredWidth] = useContainerWidth()
  const effectiveWidth = width ?? measuredWidth
  // Auto-subtitle from filter state — see BarChart for rationale.
  const filters = useFilters()
  const discipline = useDiscipline()
  const scopePhrase = abbreviateScope(filters, { discipline })
  const effectiveSubtitle = subtitle ?? (title ? scopePhrase : '')

  // Auto-derive the reference-line legend label from the same scope
  // phrase that drives the subtitle — the chip deltas on the tile row
  // above already compare against this exact pool (scope_avg on
  // /summary), so the chart legend names the same baseline explicitly.
  // Fallback "League avg" covers the empty-scope case.
  const effectiveReferenceLabel = referenceLabel
    ?? (scopePhrase ? `${scopePhrase} avg` : 'League avg')

  // Reference-overlay mode: combine data + referenceData into a single
  // tagged array and tell Semiotic to draw two lines, distinguished
  // by `_series`. When `lineBy` is already set the multi-series caller
  // owns the data; skip the overlay merge.
  const hasReference = !lineBy && referenceData != null && referenceData.length > 0
  const effectiveData: Record<string, unknown>[] = hasReference
    ? [
        ...data.map(d => ({ ...d, _series: primaryLabel })),
        ...(referenceData ?? []).map(d => ({ ...d, _series: effectiveReferenceLabel })),
      ]
    : data
  const effectiveLineBy = hasReference ? '_series' : lineBy
  const effectiveColorBy = hasReference ? '_series' : colorBy
  const effectiveColorScheme = hasReference
    ? [colorScheme[0] ?? WISDEN_PALETTE[0], '#3F7A4D']
    : colorScheme

  return (
    <ChartContainer
      outerRef={ref}
      header={<ChartHeader title={title} subtitle={effectiveSubtitle} />}
    >
      {effectiveWidth > 0 && (
        <SemioticLineChart
          data={effectiveData}
          xAccessor={xAccessor}
          yAccessor={yAccessor}
          lineBy={effectiveLineBy}
          colorBy={effectiveColorBy}
          colorScheme={effectiveColorScheme}
          width={effectiveWidth}
          height={height}
          xLabel={xLabel}
          yLabel={yLabel}
          showPoints={showPoints}
          curve={curve}
          annotations={annotations}
          tooltip={tooltip}
          // Default the legend below the chart so long category labels
          // (e.g. team names like "Sunrisers Hyderabad") don't get
          // clipped by the chart card on narrow screens.
          legendPosition="bottom"
          enableHover
          showGrid
        />
      )}
    </ChartContainer>
  )
}
