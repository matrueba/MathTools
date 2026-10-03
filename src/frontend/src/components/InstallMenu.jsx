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
 * The backend is a mock: it reports what the installer would do and writes
 * nothing, so the result panel says so explicitly rather than claiming success.
 */
export default function InstallMenu({ provider, projectId, projectPath, onClose, onApplied }) {
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

  const target = scope === 'global' ? provider.globalDir : `${projectPath}/${provider.targetDir}`

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
                  {value === 'local' ? 'Local (this repo)' : 'Global (~/)'}
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

          {result && (
            <div className="notice">
              <strong>Nothing was written.</strong> The backend is still mocked:
              it reported the {result.components.length} component group
              {result.components.length === 1 ? '' : 's'} it would deploy to{' '}
              <code>{result.target}</code>.
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
            disabled={busy || selected.size === 0}
          >
            {busy ? 'Working…' : provider.installed ? 'Update' : 'Install'}
          </button>
        </div>
      </div>
    </div>
  )
}
