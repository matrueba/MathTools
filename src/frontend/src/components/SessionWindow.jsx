import { useState } from 'react'

import AgentChat from './AgentChat.jsx'
import InteractionGraph from './InteractionGraph.jsx'

/**
 * Working surface for one session, opened from the Sessions list.
 *
 * It sits inside the content area rather than over it, so the sidebar stays
 * usable while it is open. Its inner tabs are local state: the session itself
 * is route-backed (deep-linkable), but which tab you were on is not worth a
 * URL segment.
 *
 * The Chat tab stays mounted while hidden, so switching to Interactions
 * neither loses the conversation nor aborts a turn that is still running.
 */

const TABS = [
  { id: 'chat', label: 'Chat' },
  { id: 'interactions', label: 'Interactions' },
]

export default function SessionWindow({ projectId, session, provider, onClose }) {
  const [tab, setTab] = useState('chat')

  return (
    <aside className="session-window" aria-label={`Session ${session.id}`}>
      <header className="session-window__head">
        <span
          className={session.status === 'work' ? 'dot dot--work' : 'dot dot--wait'}
        />
        {provider && (
          <span
            className="provider__tag"
            style={{ color: provider.accent, borderColor: provider.accent }}
          >
            {provider.tag}
          </span>
        )}
        <span className="session-window__title" title={session.summary}>
          {session.summary}
        </span>
        <button
          className="session-window__close"
          onClick={onClose}
          aria-label="Close session"
          title="Close"
        >
          ✕
        </button>
      </header>

      <div className="tabs tabs--inset">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? 'tab tab--active' : 'tab'}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="session-window__body" hidden={tab !== 'chat'}>
        <AgentChat
          projectId={projectId}
          agentId={provider?.id}
          agentLabel={provider?.label}
          accent={provider?.accent}
          session={session}
        />
      </div>
      <div
        className="session-window__body"
        hidden={tab !== 'interactions'}
        style={provider?.accent ? { '--agent-accent': provider.accent } : undefined}
      >
        <InteractionGraph projectId={projectId} agentId={provider?.id} session={session} />
      </div>
    </aside>
  )
}
