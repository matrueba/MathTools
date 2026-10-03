export default function Settings() {
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Settings</span>
      </div>
      <div className="state">
        <div className="state__title">Nothing to configure yet</div>
        <div className="state__hint">
          The dashboard currently serves mock data. Once the backend reads real
          sessions, refresh interval, tracked providers and vault paths will live
          here.
        </div>
      </div>
    </div>
  )
}
