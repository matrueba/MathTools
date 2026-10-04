import QueryState from '../components/QueryState.jsx'
import StatRow from '../components/StatRow.jsx'
import TokenBreakdown from '../components/TokenBreakdown.jsx'
import { api } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'

/**
 * One dashboard-style panel per provider: the same metrics the Dashboard
 * shows, scoped to that provider's sessions.
 */
export default function Agents() {
  const { data, loading, error } = useApi(api.agents)
  const agents = data?.agents ?? []

  return (
    <QueryState loading={loading} error={error}>
      {agents.map((a) => (
        <section
          key={a.id}
          className={a.enabled ? 'agent' : 'agent agent--disabled'}
        >
          <div className="agent__head">
            <span
              className="provider__tag"
              style={a.enabled ? { color: a.accent, borderColor: a.accent } : undefined}
            >
              {a.tag}
            </span>
            <span className="agent__name">{a.label}</span>
            {a.enabled ? (
              <span className="pill">
                <span
                  className={a.stats.sessions.active > 0 ? 'dot dot--work' : 'dot'}
                />
                {a.stats.sessions.active > 0
                  ? `${a.stats.sessions.active} active`
                  : 'Idle'}
              </span>
            ) : (
              <span className="pill">Not wired up yet</span>
            )}
          </div>

          <StatRow stats={a.stats} muted={!a.enabled} />

          {a.enabled && a.stats.tokens.total > 0 && (
            <TokenBreakdown tokens={a.stats.tokens} />
          )}
        </section>
      ))}
    </QueryState>
  )
}
