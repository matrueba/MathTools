import { NavLink } from 'react-router-dom'

import { api } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { IconAgents, IconFolder, IconSettings } from './Icons.jsx'

// Projects is the entry point: sessions are reached through a project, so they
// have no top-level entry of their own.
const NAV_ITEMS = [
  { to: '/projects', label: 'Projects', icon: IconFolder, countKey: 'projects' },
  { to: '/agents', label: 'Agents', icon: IconAgents },
  { to: '/settings', label: 'Settings', icon: IconSettings },
]

export default function Sidebar({ projectCount }) {
  const { data } = useApi(api.agents, { intervalMs: 0 })

  const counts = { projects: projectCount }

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo">M</div>
        <div>
          <div className="sidebar__title">MathTools</div>
          <div className="sidebar__version">Agent Control</div>
        </div>
      </div>

      <nav className="sidebar__section">
        <div className="sidebar__label">Control</div>
        {NAV_ITEMS.map(({ to, label, icon: Icon, countKey }) => {
          const count = countKey ? counts[countKey] : undefined
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                isActive ? 'navitem navitem--active' : 'navitem'
              }
            >
              <span className="navitem__icon">
                <Icon />
              </span>
              <span>{label}</span>
              {count > 0 && <span className="navitem__badge">{count}</span>}
            </NavLink>
          )
        })}
      </nav>



      <div className="sidebar__foot">
        Mock data · no agent is being controlled yet
      </div>
    </aside>
  )
}
