import { useMemo, useState } from 'react'
import { useIsMobile } from '../../hooks/useMediaQuery'

export interface HeatmapCell {
  x: string | number
  y: string | number
  value: number | null
  n?: number
}

interface HeatmapChartProps {
  cells: HeatmapCell[]
  xCategories: (string | number)[]
  yCategories: (string | number)[]
  /** Higher values lean oxblood (default). Set invert=true for
   *  economy-style metrics where LOW is good. */
  invert?: boolean
  xLabel?: string
  yLabel?: string
  /** Format the y-axis tick labels (e.g. "wkt 1", "powerplay" → "PP"). */
  formatYTick?: (y: string | number) => string
  /** Shown in tooltip after "avg: ". Defaults to "runs". */
  valueSuffix?: string
  /** How to format the value cell text and tooltip. */
  formatValue?: (v: number) => string
  /** Minimum `n` to consider full-confidence; cells below this are dimmed. */
  lowNThreshold?: number
  /** Label to use in the tooltip for the sample-size count. Defaults
   *  to "n" — pass e.g. "balls" or "partnerships" so the reader knows
   *  what's being counted. */
  nLabel?: string
  /** Fired when a populated cell is clicked. Lets a parent drill in. */
  onCellClick?: (cell: HeatmapCell) => void
}

// Linear interpolation between cream (low) and oxblood (high)
// For invert=true, the ramp is reversed.
const CREAM = [250, 247, 240]      // rgb(250,247,240)
const OXBLOOD = [122, 31, 31]      // rgb(122,31,31)
const FAINT = [180, 170, 160]       // neutral-dim for NULL / low-n

function interp(t: number, a: number[], b: number[]): string {
  const r = Math.round(a[0] + (b[0] - a[0]) * t)
  const g = Math.round(a[1] + (b[1] - a[1]) * t)
  const bl = Math.round(a[2] + (b[2] - a[2]) * t)
  return `rgb(${r},${g},${bl})`
}

/**
 * HeatmapChart — value-matrix viewer.
 *
 * Layout: pure CSS Grid driven by `--cols`/`--rows` custom properties.
 * No fixed-pixel margins, no JS `measuredWidth`, no absolute-positioned
 * cells (only the floating tooltip is absolute — that's idiomatic).
 *
 * Mobile pivot (≤ 720px): the conceptual axes flip — y=phase, x=season
 * becomes y=season, x=phase. Implementation is a data swap: caller
 * still passes xCategories/yCategories the same way; on mobile we
 * iterate them transposed so each season gets its own row and the
 * (small set of) phases become the columns. Spec: cell width on a
 * 390px viewport jumps from ~18px to ~100px so multi-digit values
 * like `10.16` render comfortably.
 */
export default function HeatmapChart({
  cells,
  xCategories,
  yCategories,
  invert = false,
  xLabel,
  yLabel,
  formatYTick = (y) => typeof y === 'number' ? `wkt ${y}` : String(y),
  valueSuffix = 'runs',
  formatValue = (v) => v.toFixed(1),
  lowNThreshold = 2,
  nLabel = 'n',
  onCellClick,
}: HeatmapChartProps) {
  const [hover, setHover] = useState<{ x: number; y: number; cell: HeatmapCell } | null>(null)
  const isMobile = useIsMobile()

  // On mobile, pivot axes: rows ← original xCategories (seasons),
  // cols ← original yCategories (phases). Cells still keyed by the
  // ORIGINAL (x, y) so the data layer is untouched.
  const rowCats = isMobile ? xCategories : yCategories
  const colCats = isMobile ? yCategories : xCategories
  const rowFormatter = isMobile ? (v: string | number) => String(v) : formatYTick
  const colFormatter = isMobile ? formatYTick : (v: string | number) => String(v)

  const cellMap = useMemo(() => {
    const m = new Map<string, HeatmapCell>()
    for (const c of cells) m.set(`${c.x}|${c.y}`, c)
    return m
  }, [cells])

  const [minV, maxV] = useMemo(() => {
    const vals = cells.map(c => c.value).filter((v): v is number => v != null)
    if (!vals.length) return [0, 0]
    return [Math.min(...vals), Math.max(...vals)]
  }, [cells])

  const colorFor = (v: number | null, n: number | undefined): string => {
    if (v == null) return 'rgb(245,242,235)'
    if (n != null && n < lowNThreshold) return interp(0.25, CREAM, FAINT)
    if (maxV === minV) return interp(0.5, CREAM, OXBLOOD)
    let t = (v - minV) / (maxV - minV)
    if (invert) t = 1 - t
    return interp(t, CREAM, OXBLOOD)
  }

  // Look up a cell by ROW index / COL index, accounting for the pivot.
  const getCell = (rowI: number, colI: number): HeatmapCell | undefined => {
    const xVal = isMobile ? rowCats[rowI] : colCats[colI]
    const yVal = isMobile ? colCats[colI] : rowCats[rowI]
    return cellMap.get(`${xVal}|${yVal}`)
  }

  return (
    <div
      className="wisden-heatmap"
      style={{
        // CSS Grid: first column = y-axis labels (auto-sized to the
        // widest label), remaining columns share remaining width equally.
        // First row = x-axis label header (rotated text); remaining rows
        // size to content.
        display: 'grid',
        gridTemplateColumns: `auto repeat(${colCats.length}, minmax(0, 1fr))`,
        gridAutoRows: 'auto',
        userSelect: 'none',
        position: 'relative',  // contains the floating tooltip
        rowGap: 0,
        columnGap: 0,
      }}
    >
      {/* Corner cell (above the y-labels, left of the x-labels) — empty. */}
      <div />

      {/* X-axis label row (rotated). One cell per column. */}
      {colCats.map((c) => (
        <div
          key={`xlabel-${c}`}
          className="wisden-heatmap-xlabel"
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
            minHeight: '1.8rem',
            padding: '0 0.1rem 0.15rem',
          }}
        >
          <span style={{
            transform: isMobile ? 'none' : 'rotate(-55deg)',
            transformOrigin: 'center bottom',
            whiteSpace: 'nowrap',
            fontSize: '0.7rem',
            fontFamily: 'var(--serif)',
            fontStyle: 'italic',
            color: 'var(--ink-faint)',
            lineHeight: 1,
            display: 'inline-block',
          }}>
            {colFormatter(c)}
          </span>
        </div>
      ))}

      {/* One row per row-category: y-label + N data cells. */}
      {rowCats.map((rc, rowI) => (
        <RowFragment key={`row-${rc}`}>
          <div
            className="wisden-heatmap-ylabel"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              fontSize: '0.7rem',
              fontFamily: 'var(--serif)',
              fontStyle: 'italic',
              color: 'var(--ink-faint)',
              whiteSpace: 'nowrap',
              padding: '0 0.4rem 0 0',
              minHeight: '2rem',
            }}
          >
            {rowFormatter(rc)}
          </div>
          {colCats.map((cc, colI) => {
            const cell = getCell(rowI, colI)
            const v = cell?.value ?? null
            const n = cell?.n
            const bg = colorFor(v, n)
            const display = v == null ? '' : formatValue(v)
            const darkText = v == null || (n != null && n < lowNThreshold) ||
              ((v - minV) / (maxV - minV || 1)) < (invert ? 0.7 : 0.5)
            return (
              <div
                key={`cell-${rc}-${cc}`}
                onMouseEnter={() => cell && setHover({ x: colI, y: rowI, cell })}
                onMouseLeave={() => setHover(null)}
                onClick={() => cell && onCellClick && onCellClick(cell)}
                style={{
                  background: bg,
                  borderRight: '1px solid rgba(255,255,255,0.35)',
                  borderBottom: '1px solid rgba(255,255,255,0.35)',
                  minHeight: '2rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.7rem',
                  fontFamily: 'var(--sans)',
                  color: darkText ? 'var(--ink)' : '#FAF7F0',
                  cursor: cell && onCellClick ? 'pointer' : 'default',
                  padding: '0.15rem 0.1rem',
                }}
              >{display}</div>
            )
          })}
        </RowFragment>
      ))}

      {/* Axis titles — span the full data area below / left of the grid. */}
      {xLabel && (
        <div
          style={{
            gridColumn: `2 / span ${colCats.length}`,
            textAlign: 'center',
            fontSize: '0.75rem', color: 'var(--ink-faint)',
            fontStyle: 'italic',
            marginTop: '0.4rem',
          }}
        >{xLabel}</div>
      )}
      {yLabel && (
        <div
          style={{
            gridColumn: 1,
            gridRow: `2 / span ${rowCats.length}`,
            writingMode: 'vertical-rl',
            transform: 'rotate(180deg)',
            fontSize: '0.75rem', color: 'var(--ink-faint)',
            fontStyle: 'italic',
            placeSelf: 'center',
          }}
        >{yLabel}</div>
      )}

      {/* Tooltip — absolute is appropriate for floating content;
          not used for layout. Positioned by the hovered cell's grid
          coords expressed in percent of the data area. */}
      {hover && (
        <div
          style={{
            position: 'absolute',
            // Anchor to viewport corner of the heatmap container.
            // Picking right side of cell + slight offset is enough for
            // a tooltip that's allowed to overlap.
            left: '50%',
            top: 0,
            transform: 'translateX(-50%)',
            background: '#2E2823',
            color: '#FAF7F0',
            padding: '6px 10px',
            fontSize: 12,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            zIndex: 10,
            borderRadius: 2,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
        >
          <div style={{ color: '#FAF7F0', fontWeight: 600 }}>
            {formatYTick(hover.cell.y)} · {String(hover.cell.x)}
          </div>
          <div style={{ color: 'rgba(250,247,240,0.82)', marginTop: 2 }}>
            avg: {hover.cell.value != null ? formatValue(hover.cell.value) : '—'} {valueSuffix}
            {hover.cell.n != null && ` · ${nLabel}=${hover.cell.n}`}
          </div>
        </div>
      )}
    </div>
  )
}

/** Wrap a y-label + its cells without introducing a wrapping <div>
 *  that would break CSS Grid (the cells need to live as direct grid
 *  children of the heatmap container). React.Fragment is the natural
 *  fit. */
function RowFragment({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
