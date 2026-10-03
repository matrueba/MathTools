import { contextColor, formatRelative, formatTokens } from '../utils/format.js'

/** "—" when a provider does not report a metric; 0 stays a real 0. */
const metric = (value, format = (v) => v) =>
  value === null || value === undefined ? '—' : format(value)

function Metric({ label, value, mono = true }) {
  return (
    <div className="metric">
      <div className="metric__label">{label}</div>
      <div className={mono ? 'metric__value cell-mono' : 'metric__value'}>{value}</div>
    </div>
  )
}

/**
 * Summary of one session. Interacting with it — transcript, subagents, the
 * live chat — happens in the SessionWindow that `Open` reveals, not here.
 */
export default function SessionCard({ session, onOpen }) {
  const ctx = session.context

  return (
    <div className="session">
      <div className="session__head">
        <span
          className={session.status === 'work' ? 'dot dot--work' : 'dot dot--wait'}
          title={session.status === 'work' ? 'Working' : 'Waiting'}
        />
        <span className="session__summary" title={session.summary}>
          {session.summary}
        </span>
        <span className="session__id cell-mono">{session.id.slice(0, 8)}</span>
        <button className="btn btn--sm" onClick={() => onOpen?.(session)}>
          Open
        </button>
      </div>

      <div className="session__metrics">
        <div className="metric metric--ctx">
          <div className="metric__label">Context window</div>
          <div className="ctx">
            <div className="ctx__meter">
              <div
                className="meter__fill"
                style={{
                  width: `${Math.min(100, ctx.pct)}%`,
                  background: contextColor(ctx.pct),
                }}
              />
            </div>
            <span className="ctx__pct">{ctx.pct.toFixed(0)}%</span>
          </div>
          <div className="metric__sub cell-mono">
            {formatTokens(ctx.used)} / {formatTokens(ctx.window)}
          </div>
        </div>

        <Metric label="Model" value={session.model} />
        <Metric label="Turns" value={metric(session.turnCount)} />
        <Metric label="Total" value={metric(session.tokens.total, formatTokens)} />
        <Metric label="In" value={metric(session.tokens.input, formatTokens)} />
        <Metric label="Out" value={metric(session.tokens.output, formatTokens)} />
        <Metric label="Cache R" value={metric(session.tokens.cacheRead, formatTokens)} />
        <Metric label="Cache W" value={metric(session.tokens.cacheWrite, formatTokens)} />
        <Metric label="Updated" value={formatRelative(session.updatedAt)} />
      </div>
    </div>
  )
}
