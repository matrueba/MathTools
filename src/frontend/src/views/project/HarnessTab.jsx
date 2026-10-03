import { useState } from 'react'

import QueryState from '../../components/QueryState.jsx'
import InstallMenu from '../../components/InstallMenu.jsx'
import { api } from '../../api/client.js'
import { useApi } from '../../hooks/useApi.js'
import { formatRelative } from '../../utils/format.js'

const TYPE_LABEL = {
  agents: 'Agents',
  commands: 'Commands',
  skills: 'Skills',
  rules: 'Rules',
  workflows: 'Workflows',
}

function ComponentGroup({ type, items }) {
  return (
    <div className="harness-group">
      <div className="harness-group__head">
        <span className="harness-group__title">{TYPE_LABEL[type] ?? type}</span>
        <span className="harness-group__count">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="harness-group__empty">None installed</div>
      ) : (
        <ul className="harness-items">
          {items.map((item) => (
            <li key={item.name} title={item.description}>
              <span className="harness-item__name">{item.name}</span>
              {item.description && (
                <span className="harness-item__desc">{item.description}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function HarnessTab({ project }) {
  const { data, loading, error, refresh } = useApi(
    () => api.harness(project.id),
    { intervalMs: 0, key: project.id },
  )

  const [menuFor, setMenuFor] = useState(null)

  const providers = data?.providers ?? []

  return (
    <QueryState loading={loading} error={error}>
      {providers.map((p) => (
        <section
          className={p.installed ? 'harness' : 'harness harness--absent'}
          key={p.id}
        >
          <div className="harness__head">
            <span
              className="provider__tag"
              style={p.installed ? { color: p.accent, borderColor: p.accent } : undefined}
            >
              {p.tag}
            </span>
            <span className="harness__name">{p.label}</span>

            {p.installed ? (
              <>
                <span className="chip chip--branch">{p.targetDir}</span>
                <span className="chip">{p.scope}</span>
                <span className="chip">{p.componentCount} components</span>
                {p.updateAvailable && (
                  <span className="chip chip--dirty">update available</span>
                )}
                <span className="harness__at">
                  installed {formatRelative(p.installedAt)}
                </span>
              </>
            ) : (
              <span className="chip">
                {p.installable ? 'not installed' : 'no installer support'}
              </span>
            )}

            <button
              className="btn"
              disabled={!p.installable}
              onClick={() => setMenuFor(p)}
              title={
                p.installable
                  ? undefined
                  : `${p.label} has no environment the installer can deploy`
              }
            >
              {p.installed ? 'Update…' : 'Install…'}
            </button>
          </div>

          {p.installed && (
            <div className="harness__groups">
              {Object.entries(p.components).map(([type, items]) => (
                <ComponentGroup key={type} type={type} items={items} />
              ))}
            </div>
          )}
        </section>
      ))}

      {menuFor && (
        <InstallMenu
          provider={menuFor}
          projectId={project.id}
          projectPath={project.path}
          onClose={() => setMenuFor(null)}
          onApplied={refresh}
        />
      )}
    </QueryState>
  )
}
