import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client.js'

/**
 * Chat with the agent behind one session (the SessionWindow's Agent tab).
 *
 * Every prompt is one headless turn resumed on the same session, streamed
 * back as NDJSON events (see `web/runners/claude.py` for the vocabulary). The
 * exchange held here is local to this window; the turn itself lands in the
 * session's transcript, so the sessions list and metrics pick it up on their
 * next poll.
 *
 * Closing the window or leaving the page aborts the request, and the backend
 * kills the agent process when the connection drops.
 */

// Mirrors PERMISSION_MODES in runners/claude.py. Nothing can stop to ask for
// approval in a headless turn, so "Ask" means "deny whatever would ask".
const MODES = [
  { id: 'manual', label: 'Ask', hint: 'Tools that need approval are denied' },
  { id: 'acceptEdits', label: 'Accept edits', hint: 'File edits run without asking' },
  { id: 'plan', label: 'Plan', hint: 'Read-only: the agent plans, it does not change files' },
  { id: 'auto', label: 'Auto', hint: 'A classifier approves safe actions' },
]

let nextId = 0

/** Fold one stream event into the turn it belongs to. */
function applyEvent(turn, event) {
  const items = [...turn.items]
  const last = items[items.length - 1]

  switch (event.type) {
    case 'start':
      return { ...turn, model: event.model }
    case 'text':
      if (last?.kind === 'text') {
        items[items.length - 1] = { ...last, text: last.text + event.text }
      } else {
        items.push({ kind: 'text', key: nextId++, text: event.text })
      }
      return { ...turn, items }
    case 'tool':
      items.push({ kind: 'tool', key: nextId++, ...event, result: null })
      return { ...turn, items }
    case 'tool_result':
      return {
        ...turn,
        items: items.map((it) =>
          it.kind === 'tool' && it.id === event.id
            ? { ...it, result: { isError: event.isError, text: event.text } }
            : it,
        ),
      }
    case 'done':
      return { ...turn, status: event.isError ? 'error' : 'done', done: event, error: event.result }
    case 'error':
      return { ...turn, status: 'error', error: event.message }
    default:
      return turn
  }
}

function ToolCall({ item }) {
  const [open, setOpen] = useState(false)
  const state = !item.result ? 'running' : item.result.isError ? 'error' : 'ok'

  return (
    <div className={`chat-tool chat-tool--${state}`}>
      <button
        className="chat-tool__head"
        onClick={() => setOpen((o) => !o)}
        disabled={!item.result?.text}
        title={item.result?.text ? 'Show output' : undefined}
      >
        <span className="chat-tool__name">{item.name}</span>
        <span className="chat-tool__summary">{item.summary}</span>
        <span className="chat-tool__state">
          {state === 'running' ? '…' : state === 'error' ? 'failed' : '✓'}
        </span>
      </button>
      {open && <pre className="chat-tool__output">{item.result.text}</pre>}
    </div>
  )
}

function Turn({ turn }) {
  const done = turn.done
  return (
    <div className="chat-turn">
      <div className="chat-msg chat-msg--user">{turn.prompt}</div>

      <div className="chat-msg chat-msg--agent">
        {turn.items.map((it) =>
          it.kind === 'text' ? (
            <div key={it.key} className="chat-text">
              {it.text}
            </div>
          ) : (
            <ToolCall key={it.key} item={it} />
          ),
        )}

        {turn.status === 'running' && (
          <div className="chat-status">
            <span className="dot dot--work" /> Working…
          </div>
        )}
        {turn.status === 'stopped' && <div className="chat-status">Stopped</div>}
        {turn.error && <div className="notice notice--error">{turn.error}</div>}
        {done?.denied?.length > 0 && (
          <div className="notice">
            Denied without asking: <strong>{[...new Set(done.denied)].join(', ')}</strong>.
            Pick a more permissive mode to let the agent run them.
          </div>
        )}
        {done && (
          <div className="chat-meta">
            {[
              turn.model,
              done.turns != null && `${done.turns} step${done.turns === 1 ? '' : 's'}`,
              done.durationMs != null && `${(done.durationMs / 1000).toFixed(1)}s`,
              done.costUsd != null && `$${done.costUsd.toFixed(4)}`,
            ]
              .filter(Boolean)
              .join(' · ')}
          </div>
        )}
      </div>
    </div>
  )
}

export default function AgentChat({ projectId, agentId, session }) {
  const [turns, setTurns] = useState([])
  const [draft, setDraft] = useState('')
  const [mode, setMode] = useState('manual')
  const abortRef = useRef(null)
  const logRef = useRef(null)

  const running = turns.some((t) => t.status === 'running')

  // Abort an in-flight turn when the window closes.
  useEffect(() => () => abortRef.current?.abort(), [])

  // Follow the stream. Scrolls the log itself, not the page around it.
  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [turns])

  const update = (id, fn) => setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)))

  const send = async () => {
    const prompt = draft.trim()
    if (!prompt || running) return

    const id = nextId++
    const controller = new AbortController()
    abortRef.current = controller
    setDraft('')
    setTurns((ts) => [...ts, { id, prompt, items: [], status: 'running' }])

    try {
      await api.promptSession(
        projectId,
        agentId,
        session.id,
        { prompt, permissionMode: mode },
        { signal: controller.signal, onEvent: (event) => update(id, (t) => applyEvent(t, event)) },
      )
      // A stream that ends without `done` or `error` was cut short.
      update(id, (t) =>
        t.status === 'running' ? { ...t, status: 'error', error: 'The agent stream ended unexpectedly' } : t,
      )
    } catch (err) {
      update(id, (t) =>
        err.name === 'AbortError'
          ? { ...t, status: 'stopped' }
          : { ...t, status: 'error', error: err.message },
      )
    } finally {
      if (abortRef.current === controller) abortRef.current = null
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  if (agentId !== 'claude') {
    return (
      <div className="state">
        <div className="state__title">Not available yet</div>
        <div className="state__hint">Only Claude Code sessions can be driven from here for now.</div>
      </div>
    )
  }

  const live = session.pids?.length > 0

  return (
    <div className="chat">
      <div className="chat__log" ref={logRef}>
        {turns.length === 0 ? (
          <div className="state">
            <div className="state__title">Continue this session</div>
            <div className="state__hint">
              Prompts run as Claude Code turns resumed on this session, in its project directory.
            </div>
          </div>
        ) : (
          turns.map((t) => <Turn key={t.id} turn={t} />)
        )}
      </div>

      <div className="chat__composer">
        {live && (
          <div className="notice">
            This session is open in a terminal. Claude Code will continue it in a copy rather
            than write to the running one.
          </div>
        )}
        <textarea
          className="input chat__input"
          rows={3}
          placeholder="Message Claude Code…  (Enter to send, Shift+Enter for a new line)"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="chat__bar">
          <div className="choices" role="radiogroup" aria-label="Permission mode">
            {MODES.map((m) => (
              <button
                key={m.id}
                role="radio"
                aria-checked={mode === m.id}
                className={mode === m.id ? 'choice choice--on' : 'choice'}
                title={m.hint}
                onClick={() => setMode(m.id)}
                disabled={running}
              >
                {m.label}
              </button>
            ))}
          </div>
          {running ? (
            <button className="btn" onClick={() => abortRef.current?.abort()}>
              Stop
            </button>
          ) : (
            <button className="btn btn--primary" onClick={send} disabled={!draft.trim()}>
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
