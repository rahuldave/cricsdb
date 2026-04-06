import { useEffect, useRef, useState, type RefObject } from 'react'

/**
 * Tracks the inner content width of a DOM element via ResizeObserver.
 *
 * Usage:
 *   const [ref, width] = useContainerWidth()
 *   return <div ref={ref}>{width > 0 && <Chart width={width} />}</div>
 *
 * Returns 0 until the first measurement lands, so callers should gate
 * the chart on `width > 0` to avoid passing 0 to chart libraries that
 * crash on it.
 */
export function useContainerWidth<T extends HTMLElement = HTMLDivElement>(): [
  RefObject<T | null>,
  number,
] {
  const ref = useRef<T | null>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // Seed with the current size synchronously so the first render after
    // mount can already render the chart at the right width.
    setWidth(Math.floor(el.getBoundingClientRect().width))
    const obs = new ResizeObserver(entries => {
      for (const entry of entries) {
        const w = Math.floor(entry.contentRect.width)
        setWidth(prev => (prev === w ? prev : w))
      }
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return [ref, width]
}
