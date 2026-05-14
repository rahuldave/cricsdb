import { useMemo, useState } from 'react'
import { useIsMobile } from '../../hooks/useMediaQuery'

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

/**
 * Compact form of a team name for narrow viewports.
 *
 *   "Royal Challengers Bengaluru" → "RCB"
 *   "Mumbai Indians"              → "MI"
 *   "Chennai Super Kings"         → "CSK"
 *   "India"                       → "IND"
 *   "Sri Lanka"                   → "SL"
 *
 * Heuristic: pluck the leading capitalised letter of each whitespace-
 * separated word. For single-word names (international teams whose
 * country name is one word), take the first three letters.
 *
 * Punctuation-only chars are skipped so "Q de Kock"-style names don't
 * land here (this helper is for TEAM labels, not player names).
 *
 * SHORTNAME_OVERRIDES handles known collisions where the generic
 * initials produce the same code for two teams. Defunct teams take
 * the longer code (active teams stay punchier — "DC" is Delhi
 * Capitals, not the long-gone Deccan Chargers).
 */
const SHORTNAME_OVERRIDES: Record<string, string> = {
  'Deccan Chargers': 'DECC',  // defuncts → keeps "DC" for Delhi Capitals
}

function shortTeam(name: string): string {
  if (name in SHORTNAME_OVERRIDES) return SHORTNAME_OVERRIDES[name]
  const words = name.split(/\s+/).filter(w => /^[A-Za-z]/.test(w))
  if (words.length === 0) return name.slice(0, 3).toUpperCase()
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase()
  return words
    .filter(w => /^[A-Z]/.test(w))  // skip "of" / "the" in "Bay of Plenty" etc.
    .map(w => w[0])
    .join('')
}

/**
 * BubbleMatrix — opponent × season grid of bubbles. Bubble area is
 * proportional to `size` (matches); colour is bucketed by `value`
 * (win-percent). Cells are clickable.
 *
 * Layout: pure CSS Grid driven by `--cols` count. No fixed-pixel
 * margins, no JS `measuredWidth`, no absolute-positioned cells.
 *
 * Mobile (≤ 720px): we DON'T pivot the axes because the y-axis
 * dimension (opponents) has many entries too — pivoting would just
 * shift the overlap to a different label. Instead, swap the y-axis
 * label formatter for a compact short-form ("Royal Challengers
 * Bengaluru" → "RCB") so the y-column shrinks from ~150px to ~40px,
 * leaving the data area enough room for 12 column bubbles.
 */
export default function BubbleMatrix({
  cells,
  xCategories,
  yCategories,
  formatYTick = (y) => String(y),
  colorBuckets = DEFAULT_BUCKETS,
  onCellClick,
  tooltipBody,
}: BubbleMatrixProps) {
  const [hover, setHover] = useState<{ xi: number; yi: number; cell: BubbleCell } | null>(null)
  const isMobile = useIsMobile()

  const cellMap = useMemo(() => {
    const m = new Map<string, BubbleCell>()
    for (const c of cells) m.set(`${c.x}|${c.y}`, c)
    return m
  }, [cells])

  const maxSize = useMemo(
    () => cells.reduce((m, c) => Math.max(m, c.size), 0),
    [cells],
  )

  // Bubble diameter scales with sqrt(size) (so AREA ≈ size). Output
  // in rem so the diameter is independent of cell width — every
  // bubble across all rows uses the same px-per-unit-of-size scale,
  // which is what makes the matrix legible as a size-comparison.
  // Max diameter 1.5rem fits in the 1.8rem row height with margin;
  // min clamped to 0.3rem so a single-match cell is still visible.
  const diameterRem = (size: number): number =>
    maxSize > 0 ? Math.max(0.3, Math.sqrt(size / maxSize) * 1.5) : 0

  const effectiveFormatY = isMobile
    ? (y: string | number) => shortTeam(formatYTick(y))
    : formatYTick

  return (
    <div
      className="wisden-bubble-matrix"
      style={{
        display: 'grid',
        gridTemplateColumns: `auto repeat(${xCategories.length}, minmax(0, 1fr))`,
        gridAutoRows: 'auto',
        userSelect: 'none',
        position: 'relative',
        rowGap: 0,
        columnGap: 0,
      }}
    >
      {/* Corner cell — empty. */}
      <div />

      {/* X-axis labels — rotated season columns. Header row height
          (min 3rem) is sized to contain the rotated label envelope —
          a single-line label rotated -55° has a bounding box ~0.82 ×
          its unrotated width; for a "2009/10" label at 0.7rem font
          that's ~3rem of vertical room. Without this the labels
          overflow the header row and visually eat into the chart
          title above. */}
      {xCategories.map((x) => (
        <div
          key={`xlabel-${x}`}
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
            minHeight: '3rem',
            padding: '0 0.1rem 0.15rem',
          }}
        >
          <span style={{
            transform: 'rotate(-55deg)',
            transformOrigin: 'center bottom',
            whiteSpace: 'nowrap',
            fontSize: '0.7rem',
            fontFamily: 'var(--serif)',
            fontStyle: 'italic',
            color: 'var(--ink-faint)',
            lineHeight: 1,
            display: 'inline-block',
          }}>
            {String(x)}
          </span>
        </div>
      ))}

      {/* One row per yCategory: label + N bubble cells. */}
      {yCategories.map((y, yi) => (
        <RowFragment key={`row-${y}`}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              fontSize: '0.8rem',
              fontFamily: 'var(--serif)',
              color: 'var(--ink-soft)',
              whiteSpace: 'nowrap',
              padding: '0 0.5rem 0 0',
              minHeight: '1.8rem',
            }}
            title={isMobile ? formatYTick(y) : undefined}
          >
            {effectiveFormatY(y)}
          </div>
          {xCategories.map((x, xi) => {
            const cell = cellMap.get(`${x}|${y}`)
            const dRem = cell && cell.size > 0 ? diameterRem(cell.size) : 0
            const color = cell ? bucketFor(cell.value, colorBuckets).color : NEUTRAL
            const isHovered = hover && hover.xi === xi && hover.yi === yi
            return (
              <div
                key={`cell-${x}-${y}`}
                onMouseEnter={() => cell && setHover({ xi, yi, cell })}
                onMouseLeave={() => setHover(null)}
                onClick={() => cell && onCellClick && onCellClick(cell)}
                style={{
                  position: 'relative',
                  minHeight: '1.8rem',
                  // Faint baseline so the row remains readable when empty.
                  background: 'linear-gradient(to bottom, transparent calc(50% - 0.5px), var(--bg-soft) calc(50% - 0.5px), var(--bg-soft) calc(50% + 0.5px), transparent calc(50% + 0.5px))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: cell && onCellClick ? 'pointer' : 'default',
                }}
              >
                {dRem > 0 && (
                  <div
                    style={{
                      width: `${dRem}rem`,
                      aspectRatio: '1 / 1',
                      borderRadius: '50%',
                      background: color,
                      opacity: 0.88,
                      transition: 'transform 0.08s',
                      transform: isHovered ? 'scale(1.18)' : 'none',
                    }}
                  />
                )}
              </div>
            )
          })}
        </RowFragment>
      ))}

      {/* Tooltip — absolute positioning is appropriate for floating
          content; not used for layout. */}
      {hover && (
        <div
          style={{
            position: 'absolute',
            top: 0, left: '50%',
            transform: 'translateX(-50%)',
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

      {/* Legend — one chip per colour bucket. Spans the data area
          below the grid via grid-column. */}
      <div
        className="wisden-tab-help"
        style={{
          gridColumn: `1 / span ${xCategories.length + 1}`,
          marginTop: '0.5rem',
        }}
      >
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

function RowFragment({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
