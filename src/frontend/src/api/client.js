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
    throw new Error(`${res.status} ${res.statusText} — ${BASE}${path}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  agents: () => request('/agents'),
  stats: () => request('/stats'),
  sessions: () => request('/sessions'),
  session: (id) => request(`/sessions/${id}`),
  sessionMessages: (id) => request(`/sessions/${id}/messages`),
  projects: () => request('/projects'),
  project: (id) => request(`/projects/${id}`),
  harness: (id) => request(`/projects/${id}/harness`),
  installHarness: (projectId, providerId, payload) =>
    request(`/projects/${projectId}/harness/${providerId}`, {
      method: 'POST',
      body: payload,
    }),
}
