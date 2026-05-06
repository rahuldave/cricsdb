/**
 * Season-tick axis rendered below the distribution sparkline. Spec
 * internal_docs/spec-distribution-stats.md §12.2.6 (originally
 * shipped on the bowler panel; lifted here so the batter panel
 * shares the same primitive).
 *
 * For each unique calendar year in the date-asc list, places a
 * tick + 2-digit-year label ('14, '24) at the percentage offset
 * of the year's first observation. Adds calendar-anchor context
 * to a sparkline that would otherwise be just "values over a
 * sequence" — readers can locate a slump or hot streak in real
 * cricket time.
 *
 * Implementation: plain HTML container with absolutely-positioned
 * labels at percentage offsets. The previous SVG-foreignObject
 * approach stretched labels horizontally on wide viewports under
 * `preserveAspectRatio="none"` — labels overlapped into
 * illegibility.
 */

import { useMemo } from 'react'

interface Props {
  /** ISO date strings (YYYY-MM-DD) in chronological order, one per
   *  bar in the sparkline above. Nulls allowed and skipped. */
  dates: (string | null)[]
  height?: number
}

function yearOf(date: string | null): string {
  if (!date) return ''
  return date.slice(0, 4)
}

function shortYear(yyyy: string): string {
  return `'${yyyy.slice(2, 4)}`
}

interface TickMark {
  pct: number
  label: string
}

export default function SeasonTickAxis({ dates, height = 18 }: Props) {
  const ticks: TickMark[] = useMemo(() => {
    if (dates.length === 0) return []
    const out: TickMark[] = []
    let prevYear = ''
    dates.forEach((d, i) => {
      const y = yearOf(d)
      if (y && y !== prevYear) {
        const pct = ((i + 0.5) / dates.length) * 100
        out.push({ pct, label: shortYear(y) })
        prevYear = y
      }
    })
    return out
  }, [dates])

  if (ticks.length === 0) return null

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height,
        marginTop: '0.05rem',
      }}
      aria-label="Season tick axis"
    >
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0,
        height: 1, background: 'var(--ink)', opacity: 0.25,
      }} />
      {ticks.map((t, idx) => (
        <div key={idx}>
          <div style={{
            position: 'absolute',
            top: 0,
            left: `${t.pct}%`,
            width: 1,
            height: 4,
            background: 'var(--ink)',
            opacity: 0.55,
            transform: 'translateX(-0.5px)',
          }} />
          <div style={{
            position: 'absolute',
            top: 5,
            left: `${t.pct}%`,
            transform: 'translateX(-50%)',
            fontFamily: 'var(--serif)',
            fontStyle: 'italic',
            fontSize: '0.62rem',
            color: 'var(--ink-faint)',
            lineHeight: 1,
            whiteSpace: 'nowrap',
          }}>
            {t.label}
          </div>
        </div>
      ))}
    </div>
  )
}
