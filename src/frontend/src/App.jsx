import { Navigate, Route, Routes, useLocation, useMatch } from 'react-router-dom'

import Sidebar from './components/Sidebar.jsx'
import Topbar from './components/Topbar.jsx'
import { api } from './api/client.js'
import { useApi } from './hooks/useApi.js'

import Projects from './views/Projects.jsx'
import ProjectDetail from './views/ProjectDetail.jsx'
import Agents from './views/Agents.jsx'
import Settings from './views/Settings.jsx'

const PAGES = {
  '/projects': { title: 'Projects', subtitle: 'Git repositories with agent activity' },
  '/agents': { title: 'Agents', subtitle: 'Metrics per provider' },
  '/settings': { title: 'Settings', subtitle: 'Dashboard configuration' },
}

const TAB_SUBTITLE = {
  harness: 'Skills, agents and commands installed in this repository',
  sessions: 'Agent sessions in this repository',
  overview: 'Repository state and usage',
}

export default function App() {
  const { pathname } = useLocation()

  // Project detail is a dynamic route, so it is not in the PAGES table.
  // Matched at both depths so the title survives a tab switch.
  const projectMatch = useMatch('/projects/:projectId')
  const tabMatch = useMatch('/projects/:projectId/:tab')
  const sessionMatch = useMatch('/projects/:projectId/sessions/:sessionId')
  const match = projectMatch ?? tabMatch ?? sessionMatch

  const page = match
    ? {
        title: match.params.projectId,
        // An open session is still the Sessions tab.
        subtitle: TAB_SUBTITLE[
          sessionMatch ? 'sessions' : match.params.tab ?? 'overview'
        ],
      }
    : PAGES[pathname] ?? { title: 'MathTools' }

  // Projects is the entry point and carries per-project session counts, so a
  // single poll feeds the sidebar badge, the topbar and the Projects view.
  const projectsQuery = useApi(api.projects)
  const projects = projectsQuery.data?.projects ?? []

  const activeCount = projects.reduce(
    (total, p) => total + p.stats.sessions.active,
    0,
  )

  return (
    <div className="app">
      <Sidebar projectCount={projects.length} />

      <div className="main">
        <Topbar
          title={page.title}
          subtitle={page.subtitle}
          updatedAt={projectsQuery.updatedAt}
          onRefresh={projectsQuery.refresh}
          live={activeCount}
        />

        <div className="content">
          <Routes>
            <Route path="/projects" element={<Projects projectsQuery={projectsQuery} />} />
            <Route path="/projects/:projectId" element={<ProjectDetail />} />
            {/* Tabs are route-backed so they survive a reload. */}
            <Route path="/projects/:projectId/:tab" element={<ProjectDetail />} />
            {/* An open session window — deep-linkable, and the sidebar stays
                usable because it renders inside the content area. */}
            <Route
              path="/projects/:projectId/sessions/:sessionId"
              element={<ProjectDetail />}
            />
            <Route path="/agents" element={<Agents />} />
            <Route path="/settings" element={<Settings />} />
            {/* Projects replaced the dashboard as the entry point; these keep
                older links from landing on a project named "sessions". */}
            <Route path="/sessions" element={<Navigate to="/projects" replace />} />
            <Route path="/projects/sessions" element={<Navigate to="/projects" replace />} />
            <Route path="*" element={<Navigate to="/projects" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
