import { useState } from 'react'

import { api } from '../api/client.js'

const TYPE_LABEL = {
  agents: 'Agents',
  commands: 'Commands',
  skills: 'Skills',
  rules: 'Rules',
  workflows: 'Workflows',
}

/**
 * Choose scope and components, then install or update a provider's harness.
 *
 * The backend downloads the framework repositories from GitHub and writes the
 * selected components to disk (see web/harness.py). Files with the same name
 * are overwritten, so the menu warns when the destination already exists;
 * on an update, files a previous install wrote that upstream has dropped are
 * deleted, and the result lists them.
 */
export default function InstallMenu({ provider, projectId, onClose, onApplied }) {
  const [scope, setScope] = useState(provider.scope ?? 'local')
  const [selected, setSelected] = useState(() => new Set(provider.supportedComponents))
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const toggle = (type) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(type) ? next.delete(type) : next.add(type)
      return next
    })
  }

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const res = await api.installHarness(projectId, provider.id, {
        scope,
        components: [...selected],
      })
      setResult(res)
      onApplied?.()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  // Absolute install folder from the backend: <repo>/.claude or $HOME/.claude.
  const target = provider.roots?.[scope]
  const overwrites = provider.existing?.[scope] ?? []

  return (
    <div className="modal" role="dialog" aria-modal="true">
      {/* Click-outside to dismiss; the panel stops propagation. */}
      <div className="modal__backdrop" onClick={onClose} />

      <div className="modal__panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <span
            className="provider__tag"
            style={{ color: provider.accent, borderColor: provider.accent }}
          >
            {provider.tag}
          </span>
          <span className="modal__title">
            {provider.installed ? 'Update' : 'Install'} {provider.label}
          </span>
          <button className="modal__close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal__body">
          <div className="field">
            <div className="field__label">Scope</div>
            <div className="choices">
              {['local', 'global'].map((value) => (
                <button
                  key={value}
                  className={scope === value ? 'choice choice--on' : 'choice'}
                  onClick={() => setScope(value)}
                >
                  {value === 'local' ? 'Local (this repo)' : 'Global (home)'}
                </button>
              ))}
            </div>
            <div className="field__hint cell-mono">{target}</div>
          </div>

          <div className="field">
            <div className="field__label">Components</div>
            <div className="choices">
              {provider.supportedComponents.map((type) => (
                <button
                  key={type}
                  className={selected.has(type) ? 'choice choice--on' : 'choice'}
                  onClick={() => toggle(type)}
                >
                  {selected.has(type) ? '☑' : '☐'} {TYPE_LABEL[type] ?? type}
                </button>
              ))}
            </div>
            <div className="field__hint">
              Pulled from the framework and skills repositories.
            </div>
          </div>

          {!result && overwrites.length > 0 && (
            <div className="notice">
              <strong>{overwrites.join(', ')}</strong> already exist
              {overwrites.length === 1 ? 's' : ''}. Files with the same name will be
              overwritten; anything else in there is left alone.
            </div>
          )}

          {result && (
            <div className="notice notice--ok">
              <strong>
                {result.written} file{result.written === 1 ? '' : 's'} installed
              </strong>{' '}
              to <code>{result.target}</code>
              {result.removed.length > 0 && (
                <>
                  , and {result.removed.length} removed because upstream no longer
                  ships them:
                  <ul className="notice__list">
                    {result.removed.map((f) => (
                      <li key={f} className="cell-mono">
                        {f}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {result.removed.length === 0 && '.'}
            </div>
          )}

          {error && (
            <div className="notice notice--error">
              Request failed: {String(error.message)}
            </div>
          )}
        </div>

        <div className="modal__foot">
          <button className="btn" onClick={onClose}>
            {result ? 'Close' : 'Cancel'}
          </button>
          <button
            className="btn btn--primary"
            onClick={submit}
            disabled={busy || selected.size === 0 || Boolean(result)}
          >
            {busy ? 'Downloading…' : provider.installed ? 'Update' : 'Install'}
          </button>
        </div>
      </div>
    </div>
  )
}
