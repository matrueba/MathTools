import { Navigate, Route, Routes } from 'react-router-dom'

import Sidebar from './components/Sidebar.jsx'
import { api } from './api/client.js'
import { useLiveApi } from './hooks/useLiveApi.js'

import Projects from './views/Projects.jsx'
import ProjectDetail from './views/ProjectDetail.jsx'
import Agents from './views/Agents.jsx'
import Settings from './views/Settings.jsx'

export default function App() {
  // Projects is the entry point and carries per-project session counts, so a
  // single live query feeds the sidebar (badge and active count) and the Projects view.
  const projectsQuery = useLiveApi(api.projects, { event: 'projects' })
  const projects = projectsQuery.data?.projects ?? []

  const activeCount = projects.reduce(
    (total, p) => total + p.stats.sessions.active,
    0,
  )

  return (
    <div className="app">
      <Sidebar projectCount={projects.length} activeCount={activeCount} />

      <div className="main">
        <div className="content">
          <Routes>
            <Route path="/projects" element={<Projects projectsQuery={projectsQuery} />} />
            <Route path="/projects/:projectId" element={<ProjectDetail />} />
            <Route path="/projects/:projectId/:tab" element={<ProjectDetail />} />
            <Route
              path="/projects/:projectId/sessions/:sessionId"
              element={<ProjectDetail />}
            />
            <Route path="/agents" element={<Agents />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/sessions" element={<Navigate to="/projects" replace />} />
            <Route path="/projects/sessions" element={<Navigate to="/projects" replace />} />
            <Route path="*" element={<Navigate to="/projects" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
