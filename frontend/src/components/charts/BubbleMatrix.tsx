import { useMemo, useState } from 'react'
import { useContainerWidth } from '../../hooks/useContainerWidth'

export interface BubbleCell {
  x: string | number
  y: string | number
  /** Magnitude — bubble area is proportional to this. */
  size: number
  /** Outcome metric used to bucket the bubble's colour. Optional —
   *  if omitted, all bubbles get the neutral colour. */
  value?: number | null
  /** Optional secondary count for the tooltip (e.g. wins+losses). */
  meta?: Record<string, number | string | null | undefined>
}

interface BubbleMatrixProps {
  cells: BubbleCell[]
  xCategories: (string | number)[]
  yCategories: (string | number)[]
  /** Format the y-axis tick labels. */
  formatYTick?: (y: string | number) => string
  /** Buckets for `value`. Default: <40 indigo, 40–60 ochre, >60 oxblood
   *  (good for win-percent metrics; LOW = lost more, HIGH = won more). */
  colorBuckets?: { upTo: number; color: string; label: string }[]
  /** Fired when a cell is clicked. */
  onCellClick?: (cell: BubbleCell) => void
  /** Render-time tooltip body — receives the hovered cell. */
  tooltipBody?: (cell: BubbleCell) => React.ReactNode
  /** Cell row height. Default 28. */
  rowHeight?: number
}

const DEFAULT_BUCKETS: { upTo: number; color: string; label: string }[] = [
  { upTo: 40,  color: '#2E6FB5', label: 'lost more (< 40%)' },
  { upTo: 60,  color: '#C9871F', label: 'even (40–60%)' },
  { upTo: 101, color: '#7A1F1F', label: 'won more (> 60%)' },
]

const NEUTRAL = '#8A7D70'

function bucketFor(value: number | null | undefined, buckets: typeof DEFAULT_BUCKETS) {
  if (value == null) return { color: NEUTRAL, label: 'no data' }
  for (const b of buckets) {
    if (value <= b.upTo) return b
  }
  return buckets[buckets.length - 1]
}

export default function BubbleMatrix({
  cells,
  xCategories,
  yCategories,
  formatYTick = (y) => String(y),
  colorBuckets = DEFAULT_BUCKETS,
  onCellClick,
  tooltipBody,
  rowHeight = 28,
}: BubbleMatrixProps) {
  const [ref, measuredWidth] = useContainerWidth()
  const [hover, setHover] = useState<{ xi: number; yi: number; cell: BubbleCell } | null>(null)

  const cellMap = useMemo(() => {
    const m = new Map<string, BubbleCell>()
    for (const c of cells) m.set(`${c.x}|${c.y}`, c)
    return m
  }, [cells])

  const maxSize = useMemo(
    () => cells.reduce((m, c) => Math.max(m, c.size), 0),
    [cells],
  )

  // Sizing: leave a gutter for the y-axis labels and a header row for x.
  const Y_LABEL_W = 180
  const X_LABEL_H = 32
  const innerW = Math.max(measuredWidth - Y_LABEL_W, 200)
  const colW = xCategories.length > 0 ? innerW / xCategories.length : 0
  // Bubble diameter scales with sqrt(size) (so AREA ≈ size, not radius).
  // Cap at the smaller of column width and row height minus a margin.
  const maxR = Math.max(2, Math.min(colW, rowHeight) / 2 - 2)
  const radiusFor = (size: number) =>
    maxSize > 0 ? Math.max(2, Math.sqrt(size / maxSize) * maxR) : 0

  return (
    <div ref={ref} className="w-full" style={{ position: 'relative', userSelect: 'none' }}>
      {measuredWidth > 0 && (
        <div style={{ position: 'relative', paddingLeft: Y_LABEL_W, paddingTop: X_LABEL_H }}>
          {/* X axis labels — rotated so seasons fit. */}
          <div style={{
            position: 'absolute', left: Y_LABEL_W, top: 0,
            width: innerW, height: X_LABEL_H,
          }}>
            {xCategories.map((x, i) => (
              <div
                key={String(x)}
                style={{
                  position: 'absolute',
                  left: i * colW + colW / 2,
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

          {/* Body rows — one per yCategory. */}
          <div style={{ position: 'relative' }}>
            {yCategories.map((y, yi) => (
              <div key={String(y)} style={{ position: 'relative', display: 'flex', height: rowHeight }}>
                {/* y-axis label */}
                <div style={{
                  position: 'absolute',
                  left: -Y_LABEL_W,
                  top: 0,
                  width: Y_LABEL_W - 8,
                  height: rowHeight,
                  display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
                  fontSize: 12,
                  fontFamily: 'var(--serif)',
                  color: 'var(--ink-soft)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}>
                  {formatYTick(y)}
                </div>

                {/* Faint baseline so the row is readable even when empty. */}
                <div style={{
                  position: 'absolute',
                  left: 0, right: 0, top: rowHeight / 2 - 0.5,
                  height: 1, background: 'var(--bg-soft)',
                }} />

                {xCategories.map((x, xi) => {
                  const cell = cellMap.get(`${x}|${y}`)
                  if (!cell || cell.size <= 0) return null
                  const r = radiusFor(cell.size)
                  const { color } = bucketFor(cell.value, colorBuckets)
                  return (
                    <div
                      key={String(x)}
                      onMouseEnter={() => setHover({ xi, yi, cell })}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => onCellClick && onCellClick(cell)}
                      style={{
                        position: 'absolute',
                        left: xi * colW + colW / 2 - r,
                        top: rowHeight / 2 - r,
                        width: r * 2,
                        height: r * 2,
                        borderRadius: '50%',
                        background: color,
                        opacity: 0.88,
                        cursor: onCellClick ? 'pointer' : 'default',
                        transition: 'transform 0.08s',
                        ...(hover && hover.xi === xi && hover.yi === yi
                          ? { transform: 'scale(1.18)' } : {}),
                      }}
                    />
                  )
                })}
              </div>
            ))}
          </div>

          {/* Tooltip */}
          {hover && (
            <div
              style={{
                position: 'absolute',
                left: Math.min(hover.xi * colW + colW / 2 + 14, innerW - 180),
                top: X_LABEL_H + hover.yi * rowHeight - 6,
                background: '#2E2823',
                color: '#FAF7F0',
                padding: '6px 10px',
                fontSize: 12,
                pointerEvents: 'none',
                whiteSpace: 'nowrap',
                zIndex: 10,
                borderRadius: 2,
                boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
              }}
            >
              <div style={{ fontWeight: 600 }}>
                {formatYTick(hover.cell.y)} · {String(hover.cell.x)}
              </div>
              <div style={{ color: 'rgba(250,247,240,0.82)', marginTop: 2 }}>
                {tooltipBody
                  ? tooltipBody(hover.cell)
                  : `${hover.cell.size} matches${
                      hover.cell.value != null ? ` · ${hover.cell.value}` : ''
                    }`}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Legend — one chip per colour bucket. */}
      <div className="wisden-tab-help" style={{ marginTop: 8 }}>
        {colorBuckets.map(b => (
          <span key={b.label} style={{ marginRight: 14 }}>
            <span style={{
              display: 'inline-block', width: 10, height: 10,
              borderRadius: '50%', background: b.color, marginRight: 4,
              verticalAlign: 'middle',
            }} />
            {b.label}
          </span>
        ))}
        <span style={{ fontStyle: 'italic' }}>
          · bubble area is proportional to matches played that season.
        </span>
      </div>
    </div>
  )
}
