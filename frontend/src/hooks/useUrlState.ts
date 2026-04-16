import { useSearchParams } from 'react-router-dom'
import { useCallback } from 'react'

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
