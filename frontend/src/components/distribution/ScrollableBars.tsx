/**
 * Horizontal-scroll wrapper for the distribution sparkline + season-
 * tick axis pair. Forces a minimum width of MIN_BAR_PX × count so
 * the bars stay individually distinguishable even when the panel
 * column is narrow (mobile + iPad portrait). When count × MIN_BAR_PX
 * is smaller than the container width, the inner div sits at the
 * container width and no scrollbar appears — i.e. low-count players
 * fit naturally on every viewport.
 *
 * Decision 2026-05-15: minBarPx = 2 universal (across mobile, iPad,
 * desktop). Heavier readability vs the prior "stretch to fit" was
 * a clear win on touch — 2 × N px on a 390 viewport means a 200-
 * innings player fits without scroll; a 400-innings player needs
 * one swipe.
 *
 * Both children (DistributionSparkline SVG + SeasonTickAxis) must
 * render with `width: 100%` (they already do) so they fill the
 * inner div's clamped width and stay aligned across scroll.
 *
 * Touch behavior — `overscroll-behavior-x: contain` stops the swipe
 * from bleeding to the page body when the user reaches either end
 * of the scroll. Same pattern used for the Splits Mosaic.
 */

import type { ReactNode } from 'react'

export const MIN_BAR_PX = 2

interface Props {
  /** Number of bars rendered inside (e.g. observations.length). The
   *  inner div is sized to at least `count * MIN_BAR_PX` so each
   *  bar receives that much horizontal real estate. */
  count: number
  /** Override the floor — typically left at the default. */
  minBarPx?: number
  children: ReactNode
}

export default function ScrollableBars({ count, minBarPx = MIN_BAR_PX, children }: Props) {
  return (
    <div style={{ overflowX: 'auto', overscrollBehaviorX: 'contain' }}>
      <div style={{ minWidth: `${count * minBarPx}px` }}>
        {children}
      </div>
    </div>
  )
}
