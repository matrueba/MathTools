import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Fetch once on mount and, with `intervalMs`, poll.
 *
 * The fetcher is held in a ref, so passing an inline arrow is safe: its
 * identity never drives the effect. Refetching on a changed argument is opted
 * into with `key` (e.g. the project id), which is the only thing besides
 * `intervalMs` that restarts the cycle.
 *
 * Polling ticks do not flip `loading` back on, so the view never flashes an
 * empty state while it refreshes in the background.
 *
 * `replace(value)` swaps the data from outside — that is how live (SSE)
 * updates land, see useLiveApi. A fetch that was already in flight when
 * `replace` ran is discarded on arrival, so a slow response can never
 * overwrite the newer pushed state.
 */
export function useApi(fetcher, { intervalMs = 3000, key } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState(null)

  const cancelled = useRef(false)
  const version = useRef(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const load = useCallback(async (isInitial = false) => {
    const started = version.current
    try {
      const result = await fetcherRef.current()
      if (cancelled.current || version.current !== started) return
      setData(result)
      setError(null)
      setUpdatedAt(new Date())
    } catch (err) {
      if (cancelled.current || version.current !== started) return
      // Keep the last good payload on a failed refresh; only a failed first
      // load should replace the view with an error state.
      if (isInitial) setData(null)
      setError(err)
    } finally {
      if (!cancelled.current && isInitial) setLoading(false)
    }
  }, [])

  const replace = useCallback((value) => {
    version.current += 1
    setData(value)
    setError(null)
    setLoading(false)
    setUpdatedAt(new Date())
  }, [])

  useEffect(() => {
    cancelled.current = false
    version.current += 1
    setLoading(true)
    load(true)

    if (!intervalMs) {
      return () => {
        cancelled.current = true
      }
    }

    const timer = setInterval(() => load(false), intervalMs)
    return () => {
      cancelled.current = true
      clearInterval(timer)
    }
  }, [load, intervalMs, key])

  return { data, error, loading, updatedAt, refresh: () => load(false), replace }
}
