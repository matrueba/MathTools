import { NavLink } from 'react-router-dom'

/** Route-backed tabs, so a tab is deep-linkable and survives a reload. */
export default function Tabs({ tabs }) {
  return (
    <div className="tabs">
      {tabs.map(({ to, label, end, count }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => (isActive ? 'tab tab--active' : 'tab')}
        >
          {label}
          {count != null && <span className="tab__count">{count}</span>}
        </NavLink>
      ))}
    </div>
  )
}
