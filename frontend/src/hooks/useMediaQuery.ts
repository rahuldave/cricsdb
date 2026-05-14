import { useSyncExternalStore } from 'react'

/**
 * Subscribe to a CSS media query. Returns `true` when the query matches.
 *
 * Implementation note: uses `useSyncExternalStore` so React 18+ concurrent
 * rendering picks up the correct value during hydration without an extra
 * render — the snapshot is read from `window.matchMedia(query).matches`
 * synchronously and the listener wires `change` events.
 *
 * SSR safety: when `window` is undefined (server render or test env
 * without jsdom), returns `false`.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (callback) => {
      if (typeof window === 'undefined') return () => {}
      const mql = window.matchMedia(query)
      mql.addEventListener('change', callback)
      return () => mql.removeEventListener('change', callback)
    },
    () => typeof window === 'undefined' ? false : window.matchMedia(query).matches,
    () => false,
  )
}

/**
 * Convenience for the project's mobile breakpoint (`max-width: 720px`),
 * matching the breakpoint used by `wisden-splits-row`, `BarChart`'s
 * rotation threshold, and the `@media (max-width: 720px)` rules in
 * index.css.
 */
export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 720px)')
}
