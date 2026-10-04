import { IconRefresh } from './Icons.jsx'

export default function Topbar({ title, subtitle, updatedAt, onRefresh, live }) {
  return (
    <header className="topbar">
      <div>
        <div className="topbar__title">{title}</div>
        {subtitle && <div className="topbar__meta">{subtitle}</div>}
      </div>

      <div className="topbar__right">
        {live != null && (
          <span className="pill">
            <span className={live ? 'dot dot--work' : 'dot'} />
            {live ? `${live} active` : 'Idle'}
          </span>
        )}
        {updatedAt && (
          <span className="topbar__meta">
            Updated {updatedAt.toLocaleTimeString()}
          </span>
        )}
        <button className="btn" onClick={onRefresh} title="Refresh now">
          <IconRefresh width={14} height={14} />
        </button>
      </div>
    </header>
  )
}
