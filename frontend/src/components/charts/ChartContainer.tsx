/**
 * ChartContainer — the canonical wrapper for any chart that needs a
 * header (title / subtitle) above its drawing area AND absolutely-
 * positioned overlays (rotated x-axis labels, top-of-bar annotations,
 * crosshairs, tooltips) positioned relative to the drawing area.
 *
 * STRUCTURAL CONTRACT:
 *     <div class="w-full" ref={outer}>                 ← layout block; ResizeObserver lives here
 *       <ChartHeader />                                ← normal flow
 *       <div style="position: relative">  ← `chart-area`
 *         <svg /> + absolute overlays                  ← overlays measure top from svg top
 *       </div>
 *     </div>
 *
 * WHY THIS COMPONENT EXISTS
 *
 * Before this wrapper existed, every chart wrote the boilerplate
 * inline:
 *
 *     <div ref={ref} class="w-full" style={{position: 'relative'}}>
 *       <ChartHeader title={…} subtitle={…} />
 *       <SemioticBarChart />
 *       <div style="position:absolute; top:NN">…overlays…</div>
 *     </div>
 *
 * The overlay's `top: NN` was originally computed as "distance from the
 * top of the SVG". That math was correct as long as the SVG was the
 * FIRST flow-positioned child of the wrapper — i.e. wrapper-top ==
 * SVG-top.
 *
 * Commit eb8e69f (May 2026) inserted `<ChartHeader>` as the first child
 * of the same wrapper. The wrapper kept `position: relative`, so the
 * overlay's containing block stayed the wrapper, but the SVG now lived
 * `headerHeight` pixels below the wrapper's top. The overlay's
 * `top: NN` formula no longer matched SVG-relative coordinates and
 * labels drifted UP into the plot area (visible as year labels
 * appearing inside the bars rather than below them).
 *
 * The fix is structural, not arithmetic: the absolute overlay must live
 * inside an element whose top IS the SVG's top. ChartContainer enforces
 * that contract by wrapping the drawing area in its own
 * `position: relative` block, with the header rendered OUTSIDE that
 * block. Charts opt in by composing ChartContainer instead of writing
 * the boilerplate; the class of bug becomes structurally impossible.
 *
 * SPEC: this contract is described once here. Per CLAUDE.md "Extend
 * existing abstractions — do NOT fork parallel helpers" — any new chart
 * wrapper that wants a header should use ChartContainer rather than
 * re-rolling the wrapper structure.
 */

import type { ReactNode } from 'react'

interface ChartContainerProps {
  /** Header element (typically <ChartHeader/>). Rendered above the
   *  chart area in normal document flow. Pass null for chart-less
   *  contexts (the chart-area positioning context still applies).
   */
  header?: ReactNode
  /** Layout className on the outer block. Defaults to "w-full". */
  className?: string
  /** Inline style on the outer block. Lets the caller set CSS custom
   *  properties (e.g. `--wisden-bar-opacity`) consumed by global
   *  scoped rules in index.css without forking the component. */
  style?: React.CSSProperties
  /** Forwarded as a ref to the outer block (for ResizeObserver-based
   *  width measurement). NB: the chart area itself is a child, so its
   *  width matches the outer block's width.
   */
  outerRef?: React.RefObject<HTMLDivElement | null>
  /** Chart content — typically an <svg> followed by zero or more
   *  absolutely-positioned overlay divs. The overlays' `top` /
   *  `bottom` / `left` / `right` measure from THIS block's edges.
   */
  children: ReactNode
}

export default function ChartContainer({
  header,
  className = 'w-full',
  style,
  outerRef,
  children,
}: ChartContainerProps) {
  return (
    <div ref={outerRef} className={className} style={style}>
      {header}
      <div style={{ position: 'relative' }}>
        {children}
      </div>
    </div>
  )
}
