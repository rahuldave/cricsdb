import { useSearchParams } from 'react-router-dom'
import { useCallback } from 'react'

// `__any__` is the slot-override sentinel for "explicit empty / do
// not inherit primary." See spec-slot-override-chip-alignment.md §4.1.
// Falsy values (empty string, undefined) still trigger the URL-delete
// branch — the sentinel is the ONLY way to keep an explicitly-empty
// param in the URL.
export const ANY_SENTINEL = '__any__'

/**
 * Read/write individual URL search params without clobbering others.
 * Returns [value, setValue] like useState but backed by the URL.
 *
 * **Pushes history by default** — the back button walks through filter
 * states the user actually created. Pass `{ replace: true }` to the
 * setter for programmatic, auto-correcting updates (see internal_docs/url-state.md
 * for which call-sites need replace).
 */
export function useUrlParam(
  key: string,
  defaultValue = '',
): [string, (v: string, opts?: { replace?: boolean }) => void] {
  const [params, setParams] = useSearchParams()
  const value = params.get(key) || defaultValue

  const setValue = useCallback((v: string, opts?: { replace?: boolean }) => {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      if (v) next.set(key, v)
      else next.delete(key)
      return next
    }, { replace: opts?.replace ?? false })
  }, [key, setParams])

  return [value, setValue]
}

/**
 * Set multiple URL params atomically (avoids race conditions).
 * Pushes history by default. Pass `{ replace: true }` for programmatic
 * auto-corrections that shouldn't pollute the back stack.
 *
 * Truthy values are written; falsy values delete the key. The
 * `__any__` sentinel is truthy and lands in the URL literally — it's
 * the contract callers use to express "explicit empty" on slot
 * overrides (distinct from the absent-default-inherit case).
 */
export function useSetUrlParams(): (
  updates: Record<string, string>,
  opts?: { replace?: boolean },
) => void {
  const [, setParams] = useSearchParams()
  return useCallback((updates: Record<string, string>, opts?: { replace?: boolean }) => {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      for (const [k, v] of Object.entries(updates)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      return next
    }, { replace: opts?.replace ?? false })
  }, [setParams])
}
