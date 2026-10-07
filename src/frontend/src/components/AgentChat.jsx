import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'

/**
 * Chat with the agent behind one session (the SessionWindow's Chat tab).
 *
 * It opens on the session's conversation so far, read from its transcript
 * (`/history`), and every prompt sent from here is one headless turn resumed
 * on the same session, streamed back as NDJSON. Both speak the same event
 * vocabulary (see `web/runners/claude.py`), so one reducer renders them.
 *
 * The history is reloaded whenever the session's transcript changes (its
 * `updatedAt`, pushed live over SSE) — except while a turn from here is
 * streaming, which already shows that change as it happens.
 *
 * A session open in another client (a terminal, the VS Code extension) is
 * read-only here: two writers would fork the session or interleave turns, so
 * the composer is disabled and the backend refuses the prompt as well. The
 * history keeps following what happens over there.
 *
 * Closing the window or leaving the page aborts a running turn, and the
 * backend kills the agent process when the connection drops.
 */

// Mirrors PERMISSION_MODES in runners/claude.py. Nothing can stop to ask for
// approval in a headless turn, so "Ask" means "deny whatever would ask".
const MODES = [
  { id: 'manual', label: 'Manual', hint: 'Tools that need approval are denied' },
  { id: 'acceptEdits', label: 'Accept edits', hint: 'File edits run without asking' },
  { id: 'plan', label: 'Plan', hint: 'Read-only: the agent plans, it does not change files' },
  { id: 'auto', label: 'Auto', hint: 'A classifier approves safe actions' },
]

// Claude Code's `entrypoint` values, as a person would name them.
const CLIENTS = {
  cli: 'a terminal',
  'claude-vscode': 'VS Code',
  'claude-desktop': 'Claude Desktop',
}

function describeClients(entrypoints = []) {
  const names = [...new Set(entrypoints.map((e) => CLIENTS[e] ?? 'another Claude Code client'))]
  return names.length ? names.join(' and ') : 'another Claude Code client'
}

let nextId = 0

/** Fold one event into the turn it belongs to. */
function applyEvent(turn, event) {
  const items = [...turn.items]
  const last = items[items.length - 1]

  switch (event.type) {
    case 'start':
      return { ...turn, model: event.model }
    case 'text':
      // Live deltas extend the current text; a history block is whole.
      if (last?.kind === 'text' && !event.block) {
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
    case 'note':
      items.push({ kind: 'note', key: nextId++, text: event.text })
      return { ...turn, items }
    case 'done':
      return { ...turn, status: event.isError ? 'error' : 'done', done: event, error: event.result }
    case 'error':
      return { ...turn, status: 'error', error: event.message }
    default:
      return turn
  }
}

/** A transcript's events as finished turns, one per prompt. */
function historyTurns(events) {
  const turns = []
  for (const event of events) {
    if (event.type === 'prompt') {
      turns.push({ id: nextId++, prompt: event.text, items: [], status: 'done' })
      continue
    }
    // Anything before the first prompt (a note, say) gets a turn of its own.
    if (!turns.length) turns.push({ id: nextId++, prompt: null, items: [], status: 'done' })
    turns[turns.length - 1] = applyEvent(turns[turns.length - 1], event)
  }
  return turns
}

function ToolCall({ item, final }) {
  const [open, setOpen] = useState(false)
  // A finished turn can still hold a call without a result: it was
  // interrupted before the tool returned.
  const state = item.result ? (item.result.isError ? 'error' : 'ok') : final ? 'none' : 'running'
  const mark = { running: '…', error: 'failed', ok: '✓', none: '—' }[state]

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
        <span className="chat-tool__state">{mark}</span>
      </button>
      {open && <pre className="chat-tool__output">{item.result.text}</pre>}
    </div>
  )
}

function Turn({ turn, agentLabel }) {
  const done = turn.done
  const final = turn.status !== 'running'
  // A past turn can be a prompt the agent never answered (interrupted at
  // once); it gets no empty agent card.
  const answered =
    turn.items.length > 0 ||
    turn.status === 'running' ||
    turn.status === 'stopped' ||
    Boolean(turn.error) ||
    Boolean(done)

  return (
    <div className="chat-turn">
      {turn.prompt != null && (
        <div className="chat-row chat-row--user">
          <div className="chat-author">You</div>
          <div className="chat-msg chat-msg--user">{turn.prompt}</div>
        </div>
      )}

      {answered && (
        <div className="chat-row chat-row--agent">
          <div className="chat-author chat-author--agent">{agentLabel}</div>
          <div className="chat-msg chat-msg--agent">
            {turn.items.map((it) => {
              if (it.kind === 'text') {
                return (
                  <div key={it.key} className="chat-text">
                    {it.text}
                  </div>
                )
              }
              if (it.kind === 'note') {
                return (
                  <div key={it.key} className="chat-note">
                    {it.text}
                  </div>
                )
              }
              return <ToolCall key={it.key} item={it} final={final} />
            })}

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
      )}
    </div>
  )
}

export default function AgentChat({ projectId, agentId, agentLabel = 'Agent', accent, session }) {
  const [turns, setTurns] = useState([])
  const [history, setHistory] = useState({ loading: true, error: null })
  const [draft, setDraft] = useState('')
  const [mode, setMode] = useState('manual')
  const abortRef = useRef(null)
  const logRef = useRef(null)
  // The `updatedAt` the shown history was loaded for.
  const loadedFor = useRef(null)

  const running = turns.some((t) => t.status === 'running')
  const runningRef = useRef(running)
  runningRef.current = running

  const supported = agentId === 'claude'
  const live = Boolean(session.live)

  // Abort an in-flight turn when the window closes.
  useEffect(() => () => abortRef.current?.abort(), [])

  // A different session starts from a clean slate.
  useEffect(() => {
    loadedFor.current = null
    setTurns([])
    setHistory({ loading: true, error: null })
  }, [session.id])

  // (Re)load the conversation whenever the transcript has changed since the
  // last load. Skipped mid-turn: the stream is already showing that turn, and
  // the reload that follows it swaps in the transcript's version.
  useEffect(() => {
    if (!supported || running || loadedFor.current === session.updatedAt) return
    const target = session.updatedAt
    let cancelled = false

    api
      .sessionHistory(projectId, agentId, session.id)
      .then((body) => {
        // A turn started while this was in flight owns the view now.
        if (cancelled || runningRef.current) return
        loadedFor.current = target
        setTurns(historyTurns(body.events))
        setHistory({ loading: false, error: null })
      })
      .catch((err) => {
        if (cancelled) return
        setHistory({ loading: false, error: err.message })
      })

    return () => {
      cancelled = true
    }
  }, [supported, running, projectId, agentId, session.id, session.updatedAt])

  // Follow the conversation. Scrolls the log itself, not the page around it.
  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [turns])

  const update = (id, fn) => setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)))

  const send = async () => {
    const prompt = draft.trim()
    if (!prompt || running || live) return

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

  if (!supported) {
    return (
      <div className="state">
        <div className="state__title">Not available yet</div>
        <div className="state__hint">Only Claude Code sessions can be driven from here for now.</div>
      </div>
    )
  }

  let placeholder = null
  if (turns.length === 0) {
    placeholder = history.loading ? (
      <div className="state">
        <div className="state__hint">Loading conversation…</div>
      </div>
    ) : (
      <div className="state">
        <div className="state__title">No messages yet</div>
        <div className="state__hint">
          Prompts run as Claude Code turns resumed on this session, in its project directory.
        </div>
      </div>
    )
  }

  return (
    // The provider's colour marks the agent's side of the conversation.
    <div className="chat" style={accent ? { '--agent-accent': accent } : undefined}>
      <div className="chat__log" ref={logRef}>
        {history.error && (
          <div className="notice notice--error">Could not load the conversation: {history.error}</div>
        )}
        {placeholder ?? turns.map((t) => <Turn key={t.id} turn={t} agentLabel={agentLabel} />)}
      </div>

      <div className="chat__composer">
        {live && (
          <div className="notice">
            This session is open in <strong>{describeClients(session.liveIn)}</strong>. The
            conversation keeps updating here, but you can only write to it once it is closed
            there.
          </div>
        )}
        <textarea
          className="input chat__input"
          rows={3}
          placeholder={
            live
              ? 'Read-only while the session is open elsewhere'
              : 'Message Claude Code…  (Enter to send, Shift+Enter for a new line)'
          }
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={live}
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
                disabled={running || live}
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
            <button
              className="btn btn--primary"
              onClick={send}
              disabled={live || !draft.trim()}
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
