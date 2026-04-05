import { useSearchParams } from 'react-router-dom'
import { useCallback } from 'react'

/**
 * Read/write individual URL search params without clobbering others.
 * Returns [value, setValue] like useState but backed by the URL.
 */
export function useUrlParam(key: string, defaultValue = ''): [string, (v: string) => void] {
  const [params, setParams] = useSearchParams()
  const value = params.get(key) || defaultValue

  const setValue = useCallback((v: string) => {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      if (v) next.set(key, v)
      else next.delete(key)
      return next
    }, { replace: true })
  }, [key, setParams])

  return [value, setValue]
}

/**
 * Set multiple URL params atomically (avoids race conditions).
 */
export function useSetUrlParams(): (updates: Record<string, string>) => void {
  const [, setParams] = useSearchParams()
  return useCallback((updates: Record<string, string>) => {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      for (const [k, v] of Object.entries(updates)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      return next
    }, { replace: true })
  }, [setParams])
}
