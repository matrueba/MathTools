// Thin wrapper over the FastAPI backend. In development Vite proxies /api to
// uvicorn on :8765; in production FastAPI serves this bundle from the same
// origin, so a relative base works in both cases.

const BASE = '/api'

async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      Accept: 'application/json',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!res.ok) {
    // FastAPI puts the reason in `detail`; surface it so a 400/409 explains
    // itself instead of showing a bare status line.
    const detail = await res
      .json()
      .then((b) => (typeof b.detail === 'string' ? b.detail : null))
      .catch(() => null)
    const err = new Error(detail ?? `${res.status} ${res.statusText} — ${BASE}${path}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

// POST that answers with NDJSON: calls `onEvent` once per line as it arrives
// and resolves when the stream ends. Abort it through `signal`; the backend
// kills the agent process when the connection drops.
async function stream(path, { body, signal, onEvent }) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { Accept: 'application/x-ndjson', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (typeof b.detail === 'string' ? b.detail : null))
      .catch(() => null)
    const err = new Error(detail ?? `${res.status} ${res.statusText} — ${BASE}${path}`)
    err.status = res.status
    throw err
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const flush = (line) => {
    if (line.trim()) onEvent(JSON.parse(line))
  }
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()
    lines.forEach(flush)
  }
  flush(buffer + decoder.decode())
}

export const api = {
  health: () => request('/health'),
  agents: () => request('/agents'),
  projects: () => request('/projects'),
  project: (id) => request(`/projects/${id}`),
  // Sessions only exist inside a project, under the agent that ran them.
  projectAgents: (projectId) => request(`/projects/${projectId}/agents`),
  agentSessions: (projectId, agentId) =>
    request(`/projects/${projectId}/agents/${agentId}/sessions`),
  session: (projectId, agentId, sessionId) =>
    request(`/projects/${projectId}/agents/${agentId}/sessions/${sessionId}`),
  sessionMessages: (projectId, agentId, sessionId) =>
    request(`/projects/${projectId}/agents/${agentId}/sessions/${sessionId}/messages`),
  // Runs one agent turn; see `stream` for the callback contract.
  promptSession: (projectId, agentId, sessionId, body, { signal, onEvent }) =>
    stream(`/projects/${projectId}/agents/${agentId}/sessions/${sessionId}/prompt`, {
      body,
      signal,
      onEvent,
    }),
  createProject: (payload) => request('/projects', { method: 'POST', body: payload }),
  browse: (path) =>
    request(`/fs/browse${path ? `?path=${encodeURIComponent(path)}` : ''}`),
  harness: (id) => request(`/projects/${id}/harness`),
  installHarness: (projectId, providerId, payload) =>
    request(`/projects/${projectId}/harness/${providerId}`, {
      method: 'POST',
      body: payload,
    }),
}
