// One shared Server-Sent Events connection to /api/events for the whole app.
//
// The backend pushes the same payloads its REST routes return (`projects`,
// `agents`, `project`), and only when they change — see web/events.py. Views
// subscribe by event name; the connection opens with the first subscriber and
// closes with the last.
//
// EventSource reconnects by itself after a network drop, and the server
// resends its whole snapshot to every new connection, so nothing is lost
// across a reconnect. It gives up for good only when the server answers with
// an error status (e.g. a backend without /api/events); then we retry later.

const URL = '/api/events'
const RETRY_MS = 5000

const listeners = new Map() // event name -> Set<handler>
let source = null
let retryTimer = null

function dispatch(e) {
  let payload
  try {
    payload = JSON.parse(e.data)
  } catch {
    return
  }
  listeners.get(e.type)?.forEach((handler) => handler(payload))
}

function open() {
  clearTimeout(retryTimer)
  source = new EventSource(URL)
  for (const event of listeners.keys()) source.addEventListener(event, dispatch)
  source.onerror = () => {
    if (source?.readyState !== EventSource.CLOSED) return // reconnecting itself
    source = null
    retryTimer = setTimeout(() => {
      if (listeners.size && !source) open()
    }, RETRY_MS)
  }
}

function close() {
  clearTimeout(retryTimer)
  source?.close()
  source = null
}

/** Call `handler(payload)` for every `event`; returns the unsubscribe function. */
export function subscribe(event, handler) {
  if (!listeners.has(event)) {
    listeners.set(event, new Set())
    source?.addEventListener(event, dispatch)
  }
  listeners.get(event).add(handler)
  if (!source) open()

  return () => {
    const handlers = listeners.get(event)
    if (!handlers) return
    handlers.delete(handler)
    if (!handlers.size) {
      listeners.delete(event)
      source?.removeEventListener(event, dispatch)
    }
    if (!listeners.size) close()
  }
}
