/**
 * Season-tick axis rendered below the distribution sparkline. Spec
 * §12.2.6 (revised 2026-05-06).
 *
 * For each unique season in the date-asc observation list, places
 * a tick mark + label at the x-position of that season's first
 * observation. Adds calendar-anchor context to a sparkline that
 * would otherwise be just "values over a sequence" — readers can
 * locate a slump or hot streak in real cricket time.
 *
 * Implementation: plain HTML container with absolutely-positioned
 * labels at percentage offsets. Avoids the SVG
 * `preserveAspectRatio="none"` foreignObject scaling problem
 * (where labels stretch horizontally and overlap when the panel
 * is wide). Labels render at native font size on every viewport.
 *
 * Compact 2-digit year labels ('14, '24) fit horizontally at any
 * panel density without rotation, even at 14 seasons in a 358px
 * mobile panel.
 */

import { useMemo } from 'react'
import type { BowlerInningsObservation } from '../../types'

interface Props {
  observations: BowlerInningsObservation[]
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
  /** percentage offset across the axis (0..100) */
  pct: number
  label: string
}

export default function SeasonTickAxis({
  observations,
  height = 18,
}: Props) {
  const ticks: TickMark[] = useMemo(() => {
    if (observations.length === 0) return []
    const out: TickMark[] = []
    let prevYear = ''
    observations.forEach((o, i) => {
      const y = yearOf(o.date)
      if (y && y !== prevYear) {
        // Center the tick on the bar at index i. Each bar occupies
        // 1/N of the width, so the centre is at (i + 0.5) / N.
        const pct = ((i + 0.5) / observations.length) * 100
        out.push({ pct, label: shortYear(y) })
        prevYear = y
      }
    })
    return out
  }, [observations])

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
      {/* baseline */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0,
        height: 1, background: 'var(--ink)', opacity: 0.25,
      }} />
      {ticks.map((t, idx) => (
        <div key={idx}>
          {/* tick mark */}
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
          {/* label */}
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
