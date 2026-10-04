import { useEffect, useState } from 'react'

import { api } from '../api/client.js'
import { IconBranch } from './GitInfo.jsx'

/**
 * Pick a local git repository and register it as a project.
 *
 * A browser cannot give the page an absolute path for a folder chosen with a
 * native picker, so this walks the server's filesystem through /fs/browse.
 * The list shows only the git repos inside the current folder; other folders
 * are reached by going up or typing a path. The backend checks again on POST,
 * so a folder that stops being a repo in between is still rejected.
 */
export default function AddProjectModal({ onClose, onCreated }) {
  const [listing, setListing] = useState(null)
  const [pathInput, setPathInput] = useState('')
  const [browseError, setBrowseError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const open = async (path) => {
    setBrowseError(null)
    try {
      const res = await api.browse(path)
      setListing(res)
      setPathInput(res.path)
      // Opening a repo selects it; opening anything else clears the choice.
      setSelected(res.isGitRepo ? res.path : null)
    } catch (err) {
      setBrowseError(err)
    }
  }

  useEffect(() => {
    open()
  }, [])

  const select = (entry) => {
    setError(null)
    setSelected(entry.path)
  }

  const repos = listing?.entries.filter((e) => e.isGitRepo) ?? []

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const project = await api.createProject({
        path: selected,
        name: name.trim() || null,
      })
      onCreated?.(project)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const folderName = selected?.split('/').filter(Boolean).pop() ?? ''

  return (
    <div className="modal" role="dialog" aria-modal="true">
      <div className="modal__backdrop" onClick={onClose} />

      <div className="modal__panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <span className="modal__title">Add project</span>
          <button className="modal__close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal__body">
          <div className="field">
            <div className="field__label">Repository</div>

            <div className="browser">
              <div className="browser__bar">
                <button
                  className="btn btn--sm"
                  onClick={() => open(listing?.parent)}
                  disabled={!listing?.parent}
                  title="Parent folder"
                >
                  ↑
                </button>
                <input
                  className="input browser__path cell-mono"
                  value={pathInput}
                  onChange={(e) => setPathInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && open(pathInput.trim())}
                  placeholder="…"
                  spellCheck={false}
                />
              </div>

              <div className="browser__list">
                {listing && repos.length === 0 && (
                  <div className="browser__empty">No git repositories in this folder</div>
                )}
                {repos.map((entry) => (
                  <button
                    key={entry.path}
                    className={
                      selected === entry.path
                        ? 'browser__entry browser__entry--on'
                        : 'browser__entry'
                    }
                    onClick={() => select(entry)}
                    title={entry.path}
                  >
                    <span className="browser__icon">
                      <IconBranch />
                    </span>
                    <span className="browser__name">{entry.name}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="field__hint">
              Only git repositories are listed. Type a path and press Enter, or go
              up with ↑, to look in another folder.
            </div>
            {browseError && (
              <div className="notice notice--error">{String(browseError.message)}</div>
            )}
          </div>

          <div className="field">
            <div className="field__label">Selected</div>
            {selected ? (
              <div className="cell-mono field__value">{selected}</div>
            ) : (
              <div className="field__hint">No git repository selected.</div>
            )}
          </div>

          <div className="field">
            <div className="field__label">Name</div>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={folderName || 'Defaults to the folder name'}
            />
          </div>

          {error && <div className="notice notice--error">{String(error.message)}</div>}
        </div>

        <div className="modal__foot">
          <button className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn--primary"
            onClick={submit}
            disabled={busy || !selected}
          >
            {busy ? 'Adding…' : 'Add project'}
          </button>
        </div>
      </div>
    </div>
  )
}
