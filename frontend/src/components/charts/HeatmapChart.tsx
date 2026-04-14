import { useMemo, useState } from 'react'
import { useContainerWidth } from '../../hooks/useContainerWidth'

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
  const [ref, measuredWidth] = useContainerWidth()
  const [hover, setHover] = useState<{ x: number; y: number; cell: HeatmapCell } | null>(null)

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

  // Sizing — left margin for y-axis labels, top margin for x-axis labels.
  const Y_LABEL_W = 80
  const X_LABEL_H = 28
  const innerW = Math.max(measuredWidth - Y_LABEL_W, 100)
  const cellW = xCategories.length > 0 ? innerW / xCategories.length : 0
  const cellH = 32

  return (
    <div ref={ref} className="w-full" style={{ position: 'relative', userSelect: 'none' }}>
      {measuredWidth > 0 && (
        <div style={{ position: 'relative', paddingLeft: Y_LABEL_W, paddingTop: X_LABEL_H }}>
          {/* X axis labels (column categories — usually seasons, rotated) */}
          <div style={{
            position: 'absolute', left: Y_LABEL_W, top: 0,
            width: innerW, height: X_LABEL_H,
          }}>
            {xCategories.map((x, i) => (
              <div
                key={String(x)}
                style={{
                  position: 'absolute',
                  left: i * cellW + cellW / 2,
                  top: X_LABEL_H - 4,
                  transformOrigin: '0 0',
                  transform: 'rotate(-55deg)',
                  whiteSpace: 'nowrap',
                  fontSize: 11,
                  fontFamily: 'var(--serif)',
                  fontStyle: 'italic',
                  color: 'var(--ink-faint)',
                  lineHeight: 1,
                }}
              >{String(x)}</div>
            ))}
          </div>

          {/* Grid body */}
          <div style={{ position: 'relative' }}>
            {yCategories.map((y, yi) => (
              <div key={String(y)} style={{ display: 'flex', position: 'relative' }}>
                {/* Y axis label (wicket number) */}
                <div style={{
                  position: 'absolute',
                  left: -Y_LABEL_W,
                  top: 0,
                  width: Y_LABEL_W - 6,
                  height: cellH,
                  display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
                  fontSize: 11,
                  fontFamily: 'var(--serif)',
                  fontStyle: 'italic',
                  color: 'var(--ink-faint)',
                }}>
                  {formatYTick(y)}
                </div>
                {xCategories.map((x, xi) => {
                  const cell = cellMap.get(`${x}|${y}`)
                  const v = cell?.value ?? null
                  const n = cell?.n
                  const bg = colorFor(v, n)
                  const display = v == null ? '' : formatValue(v)
                  // Use dark text on light cells, light text on dark cells.
                  // Heuristic: brightness of bg.
                  const darkText = v == null || (n != null && n < lowNThreshold) ||
                    ((v - minV) / (maxV - minV || 1)) < (invert ? 0.7 : 0.5)
                  return (
                    <div
                      key={String(x)}
                      onMouseEnter={() => cell && setHover({ x: xi, y: yi, cell })}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => cell && onCellClick && onCellClick(cell)}
                      style={{
                        width: cellW, height: cellH,
                        background: bg,
                        borderRight: '1px solid rgba(255,255,255,0.35)',
                        borderBottom: '1px solid rgba(255,255,255,0.35)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: Math.min(11, cellW * 0.28),
                        fontFamily: 'var(--sans)',
                        color: darkText ? 'var(--ink)' : '#FAF7F0',
                        cursor: cell && onCellClick ? 'pointer' : 'default',
                      }}
                    >{display}</div>
                  )
                })}
              </div>
            ))}
          </div>

          {/* Axis titles */}
          {xLabel && (
            <div style={{
              textAlign: 'center',
              fontSize: 12, color: 'var(--ink-faint)',
              fontStyle: 'italic',
              marginTop: 6,
            }}>{xLabel}</div>
          )}
          {yLabel && (
            <div style={{
              position: 'absolute',
              left: -10, top: X_LABEL_H + (yCategories.length * cellH) / 2,
              transform: 'rotate(-90deg)',
              transformOrigin: '0 0',
              fontSize: 12, color: 'var(--ink-faint)',
              fontStyle: 'italic',
            }}>{yLabel}</div>
          )}

          {/* Tooltip — use hardcoded colors, not CSS vars (the project
              doesn't define --cream; falling back to unset text colour
              made the tooltip unreadable). */}
          {hover && (
            <div
              style={{
                position: 'absolute',
                left: Math.min(hover.x * cellW + cellW + 4, innerW - 160),
                top: X_LABEL_H + hover.y * cellH - 2,
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
      )}
    </div>
  )
}
