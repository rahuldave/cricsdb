/** `useFetch`: run an async request when its dependencies change, and keep its state. */

import { useEffect, useState, useCallback, useRef } from 'react'

/** What `useFetch` returns: the data, whether it is loading, the error, and a way to fetch again. */
export interface FetchState<T> {
  data: T | null // the last result; it stays while a new request loads, and is null before the first result and after an error
  loading: boolean // true while a request is in flight
  error: string | null // the error message of the last request, or null
  refetch: () => void // run the request again with the same dependencies
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
  fn: () => Promise<T>, // the request to run
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  deps: any[], // values that start a new request when they change
): FetchState<T> { // the data, loading flag, error and refetch
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
        // Clear stale data — otherwise the previous successful
        // response stays mounted and the UI silently shows numbers
        // from the prior fetch while the URL has moved on.
        // Was reachable via the Splits Mosaic landing marginals,
        // which 400'd on toss_outcome/result without ?team= until
        // the gate was lifted on 2026-05-11 (spec-splits-mosaic.md
        // §1.1 note). Latent in every useFetch caller until a
        // backend error occurs.
        setData(null)
        setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const refetch = useCallback(() => setTick(t => t + 1), [])
  return { data, loading, error, refetch }
}
