import { DonutChart as SemioticDonutChart } from 'semiotic'
import ChartContainer from './ChartContainer'
import ChartHeader from '../ChartHeader'
import { abbreviateScope } from '../scopeLinks'
import { useDiscipline } from '../../hooks/useDiscipline'
import { useFilters } from '../../hooks/useFilters'
import { WISDEN_PALETTE } from './palette'

interface DonutChartProps<T extends Record<string, any>> {
  data: T[]
  categoryAccessor?: string | ((d: T) => string)
  valueAccessor?: string | ((d: T) => number)
  title?: string
  /** Faint italic line under the title, typically the filter-state
   *  abbreviation. Empty string is treated as no subtitle. */
  subtitle?: string
  width?: number
  height?: number
  colorScheme?: string[]
  centerContent?: React.ReactNode
}

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
