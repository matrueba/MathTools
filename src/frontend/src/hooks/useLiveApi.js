import { useEffect, useRef } from 'react'

import { subscribe } from '../api/live.js'
import { useApi } from './useApi.js'

/**
 * `useApi` kept current by the server's live stream instead of polling.
 *
 * The view loads over REST once (so a deep link renders without waiting for
 * the stream), then every `event` pushed by /api/events replaces the data —
 * the server only sends an event when its payload changed, and the payload
 * has the same shape the REST route returns.
 *
 * `accept(payload)` filters events that are not for this view, e.g. the
 * `project` event for a different project. Like the fetcher, it may be an
 * inline arrow.
 */
export function useLiveApi(fetcher, { event, key, accept } = {}) {
  const query = useApi(fetcher, { intervalMs: 0, key })
  const { replace } = query

  const acceptRef = useRef(accept)
  acceptRef.current = accept

  useEffect(
    () =>
      subscribe(event, (payload) => {
        if (!acceptRef.current || acceptRef.current(payload)) replace(payload)
      }),
    [event, key, replace],
  )

  return query
}
