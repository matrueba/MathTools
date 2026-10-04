import { useNavigate } from 'react-router-dom'

import QueryState from '../components/QueryState.jsx'
import { GitChips, LastCommit } from '../components/GitInfo.jsx'
import { formatRelative, formatTokens } from '../utils/format.js'

export default function Projects({ projectsQuery }) {
  const navigate = useNavigate()
  const projects = projectsQuery.data?.projects ?? []

  return (
    <QueryState loading={projectsQuery.loading} error={projectsQuery.error}>
      {projects.length === 0 ? (
        <div className="card">
          <div className="state">
            <div className="state__title">No repositories tracked</div>
            <div className="state__hint">
              Projects appear here once an agent session runs inside a git
              repository.
            </div>
          </div>
        </div>
      ) : (
        <div className="projects">
          {projects.map((p) => (
            <button
              key={p.id}
              className="project"
              onClick={() => navigate(`/projects/${p.id}`)}
            >
              <div className="project__head">
                <span
                  className={
                    p.stats.sessions.active > 0 ? 'dot dot--work' : 'dot dot--wait'
                  }
                />
                <span className="project__name" title={p.name}>
                  {p.name}
                </span>
                {p.stats.sessions.active > 0 && (
                  <span className="project__active">
                    {p.stats.sessions.active} active
                  </span>
                )}
              </div>

              <div className="project__path" title={p.path}>
                {p.path}
              </div>

              <GitChips git={p.git} />
              <LastCommit commit={p.git.lastCommit} />

              <div className="project__foot">
                <span>
                  <strong>{p.stats.sessions.total}</strong> session
                  {p.stats.sessions.total === 1 ? '' : 's'}
                </span>
                <span>
                  <strong>{formatTokens(p.stats.tokens.total)}</strong> tokens
                </span>
                <span>{formatRelative(p.updatedAt)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </QueryState>
  )
}
