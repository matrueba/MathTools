/** Shared loading / error shell so every view fails the same way. */
export default function QueryState({ loading, error, children }) {
  if (loading) {
    return (
      <div className="state">
        <div className="spinner" />
        <div className="state__hint">Loading…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="state state--error">
        <div className="state__title">Could not reach the API</div>
        <div className="state__hint">
          {String(error.message)}
          <br />
          Make sure the backend is running — <code>mathtools</code>, or{' '}
          <code>uvicorn web.server:app --port 8765</code>.
        </div>
      </div>
    )
  }

  return children
}
