import { useParams } from 'react-router-dom'

import QueryState from '../components/QueryState.jsx'
import Tabs from '../components/Tabs.jsx'
import OverviewTab from './project/OverviewTab.jsx'
import SessionsTab from './project/SessionsTab.jsx'
import HarnessTab from './project/HarnessTab.jsx'
import { api } from '../api/client.js'
import { useLiveApi } from '../hooks/useLiveApi.js'

const TABS = {
  overview: OverviewTab,
  sessions: SessionsTab,
  harness: HarnessTab,
}

export default function ProjectDetail() {
  const { projectId, tab, sessionId } = useParams()
  const activeTab = sessionId ? 'sessions' : tab ?? 'overview'
  const { data, loading, error } = useLiveApi(() => api.project(projectId), {
    event: 'project',
    key: projectId,
    accept: (p) => p.id === projectId,
  })

  const ActiveTab = TABS[activeTab] ?? OverviewTab

  return (
    <QueryState loading={loading} error={error}>
      {data && (
        <>
          <Tabs
            tabs={[
              { to: `/projects/${projectId}`, label: 'Overview', end: true },
              {
                to: `/projects/${projectId}/sessions`,
                label: 'Sessions',
                count: data.stats.sessions.total,
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
