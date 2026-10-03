import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Fetch once on mount and then poll, mirroring the CLI dashboard's 3s refresh.
 *
 * The fetcher is held in a ref, so passing an inline arrow is safe: its
 * identity never drives the effect. Refetching on a changed argument is opted
 * into with `key` (e.g. the project id), which is the only thing besides
 * `intervalMs` that restarts the cycle.
 *
 * Polling ticks do not flip `loading` back on, so the view never flashes an
 * empty state while it refreshes in the background.
 */
export function useApi(fetcher, { intervalMs = 3000, key } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState(null)

  const cancelled = useRef(false)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const load = useCallback(async (isInitial = false) => {
    try {
      const result = await fetcherRef.current()
      if (cancelled.current) return
      setData(result)
      setError(null)
      setUpdatedAt(new Date())
    } catch (err) {
      if (cancelled.current) return
      // Keep the last good payload on a failed refresh; only a failed first
      // load should replace the view with an error state.
      if (isInitial) setData(null)
      setError(err)
    } finally {
      if (!cancelled.current && isInitial) setLoading(false)
    }
  }, [])

  useEffect(() => {
    cancelled.current = false
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

  return { data, error, loading, updatedAt, refresh: () => load(false) }
}
