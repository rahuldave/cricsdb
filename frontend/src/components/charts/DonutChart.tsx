/**
 * A donut chart on Semiotic's `DonutChart`, with a filter-state subtitle and the legend below.
 */
import { DonutChart as SemioticDonutChart } from 'semiotic'
import ChartContainer from './ChartContainer'
import ChartHeader from '../ChartHeader'
import { abbreviateScope } from '../scopeLinks'
import { useDiscipline } from '../../hooks/useDiscipline'
import { useFilters } from '../../hooks/useFilters'
import { WISDEN_PALETTE } from './palette'

/** Props of `DonutChart`. */
interface DonutChartProps<T extends Record<string, any>> {
  data: T[] // the rows, one slice each
  categoryAccessor?: string | ((d: T) => string) // the field or function that gives a slice's category, `'label'` by default
  valueAccessor?: string | ((d: T) => number) // the field or function that gives a slice's size, `'value'` by default
  title?: string // the chart title; with none, no auto subtitle either
  /** Faint italic line under the title, typically the filter-state
   *  abbreviation. Empty string is treated as no subtitle. */
  subtitle?: string
  width?: number // the chart width in pixels, 300 by default
  height?: number // the chart height in pixels, 300 by default
  colorScheme?: string[] // the slice colours, `WISDEN_PALETTE` by default
  centerContent?: React.ReactNode // what to show in the hole of the donut
}

/** Show a donut chart with hover and a legend below it. */
export default function DonutChart<T extends Record<string, any>>({
  data, categoryAccessor = 'label', valueAccessor = 'value', title, subtitle,
  width = 300, height = 300, colorScheme = WISDEN_PALETTE, centerContent,
}: DonutChartProps<T>) {
  // Auto-subtitle from filter state — see BarChart for rationale.
  const filters = useFilters()
  const discipline = useDiscipline()
  const effectiveSubtitle = subtitle ?? (title ? abbreviateScope(filters, { discipline }) : '')
  return (
    <ChartContainer
      header={<ChartHeader title={title} subtitle={effectiveSubtitle} />}
    >
      <SemioticDonutChart
        data={data}
        categoryAccessor={categoryAccessor}
        valueAccessor={valueAccessor}
        width={width}
        height={height}
        colorScheme={colorScheme}
        centerContent={centerContent}
        enableHover
        showLegend
        // Default legend below the donut so the long category strings
        // (e.g. "caught and bowled") don't get clipped by the chart card
        // on narrow screens.
        legendPosition="bottom"
      />
    </ChartContainer>
  )
}
