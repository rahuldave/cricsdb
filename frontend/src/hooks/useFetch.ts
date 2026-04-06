import { useEffect, useState, useCallback, useRef } from 'react'

export interface FetchState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Run an async function whenever `deps` change, exposing { data, loading,
 * error, refetch }. Discards results from stale calls if a newer one
 * superseded them.
 *
 * Pass a stable callback (the hook re-runs when its identity changes,
 * just like useEffect with `fn` as a dep). The deps array is what
 * actually drives re-fetching.
 */
export function useFetch<T>(
  fn: () => Promise<T>,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  deps: any[],
): FetchState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  // Track the latest call so older resolutions don't clobber newer ones.
  const callIdRef = useRef(0)

  useEffect(() => {
    const myId = ++callIdRef.current
    setLoading(true)
    setError(null)
    fn()
      .then(result => {
        if (myId !== callIdRef.current) return
        setData(result)
        setLoading(false)
      })
      .catch(err => {
        if (myId !== callIdRef.current) return
        const message = err instanceof Error ? err.message : String(err)
        setError(message || 'Request failed')
        setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const refetch = useCallback(() => setTick(t => t + 1), [])
  return { data, loading, error, refetch }
}
