import { useNavigate } from 'react-router-dom'

import SessionCard from '../../components/SessionCard.jsx'
import SessionWindow from '../../components/SessionWindow.jsx'
import { formatTokens } from '../../utils/format.js'

/**
 * Sessions of one project, grouped by the provider that ran them.
 *
 * Opening a session replaces the list with a full-width SessionWindow; the X
 * brings the list back. The window renders inside this tab, so the sidebar and
 * the project tabs stay visible and usable while it is open. The open session
 * lives in the URL, so it survives a reload and can be linked to.
 */
export default function SessionsTab({ project, sessionId }) {
  const navigate = useNavigate()
  const providers = project.providers ?? []

  const open = (session) =>
    navigate(`/projects/${project.id}/sessions/${session.id}`)

  const close = () => navigate(`/projects/${project.id}/sessions`)

  // Find the open session and the provider that owns it, so the window can
  // show the right tag. An unknown id leaves both null and falls through to
  // the list rather than erroring.
  let openSession = null
  let openProvider = null
  if (sessionId) {
    for (const p of providers) {
      const found = p.sessions.find((s) => s.id === sessionId)
      if (found) {
        openSession = found
        openProvider = p
        break
      }
    }
  }

  if (!providers.length) {
    return (
      <div className="card">
        <div className="state">
          <div className="state__title">No sessions in this project</div>
          <div className="state__hint">
            Start an agent session inside {project.path} and it will appear here.
          </div>
        </div>
      </div>
    )
  }

  // Master/detail: the window takes the whole tab, so the list is not
  // rendered at all while a session is open.
  if (openSession) {
    return (
      <SessionWindow
        session={openSession}
        provider={openProvider}
        onClose={close}
      />
    )
  }

  return providers.map((p) => (
    <section className="provider-group" key={p.id}>
      <div className="provider-group__head">
        <span
          className="provider__tag"
          style={{ color: p.accent, borderColor: p.accent }}
        >
          {p.tag}
        </span>
        <span className="provider-group__name">{p.label}</span>
        <span className="provider-group__meta">
          {p.sessions.length} session{p.sessions.length === 1 ? '' : 's'}
          {' · '}
          {formatTokens(p.stats.tokens.total)} tokens
        </span>
        {p.stats.sessions.active > 0 && (
          <span className="pill">
            <span className="dot dot--work" />
            {p.stats.sessions.active} active
          </span>
        )}
      </div>

      <div className="sessions-list">
        {p.sessions.map((s) => (
          <SessionCard key={s.id} session={s} onOpen={open} />
        ))}
      </div>
    </section>
  ))
}
