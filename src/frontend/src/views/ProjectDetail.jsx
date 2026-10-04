import { Link, useParams } from 'react-router-dom'

import QueryState from '../components/QueryState.jsx'
import Tabs from '../components/Tabs.jsx'
import OverviewTab from './project/OverviewTab.jsx'
import SessionsTab from './project/SessionsTab.jsx'
import HarnessTab from './project/HarnessTab.jsx'
import { api } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'

const TABS = {
  overview: OverviewTab,
  sessions: SessionsTab,
  harness: HarnessTab,
}

export default function ProjectDetail() {
  const { projectId, tab, sessionId } = useParams()

  // An open session (/projects/:id/sessions/:sessionId) implies the Sessions
  // tab, so the tab stays highlighted while the session window is open.
  const activeTab = sessionId ? 'sessions' : tab ?? 'overview'

  // `key` is what makes navigating between projects refetch.
  const { data, loading, error } = useApi(() => api.project(projectId), {
    key: projectId,
  })

  const ActiveTab = TABS[activeTab] ?? OverviewTab

  return (
    <QueryState loading={loading} error={error}>
      {data && (
        <>
          <div className="crumbs">
            <Link to="/projects">Projects</Link>
            <span>/</span>
            <span className="crumbs__current">{data.name}</span>
          </div>

          <Tabs
            tabs={[
              { to: `/projects/${projectId}`, label: 'Overview', end: true },
              {
                to: `/projects/${projectId}/sessions`,
                label: 'Sessions',
                count: data.sessions.length,
              },
              { to: `/projects/${projectId}/harness`, label: 'Harness' },
            ]}
          />

          <ActiveTab project={data} sessionId={sessionId} />
        </>
      )}
    </QueryState>
  )
}
