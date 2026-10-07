import StatCard from './StatCard.jsx'
import { IconFolder, IconGauge, IconPulse, IconTokens } from './Icons.jsx'
import { formatTokens } from '../utils/format.js'

/**
 * The dashboard's headline metrics. Shared by the Dashboard, each project and
 * each agent provider so all three report the same numbers the same way.
 *
 * `showProjects` is off inside a single project, where the count is always 1.
 */
export default function StatRow({ stats, showProjects = true, muted = false }) {
  const quota = stats?.quota
  const quotaValue = quota?.five_hour_pct != null ? `${quota.five_hour_pct.toFixed(1)}%` : '—'

  // A disabled provider renders the same layout with its accents dropped.
  const accent = (color) => (muted ? undefined : color)

  return (
    <div className="stats">
      <StatCard
        label="Active sessions"
        value={stats?.sessions.active ?? 0}
        foot={`${stats?.sessions.total ?? 0} tracked · ${stats?.sessions.idle ?? 0} idle`}
        icon={IconPulse}
        accent={accent('var(--green)')}
      />
      <StatCard
        label="Total tokens"
        value={formatTokens(stats?.tokens.total)}
        foot={`${formatTokens(stats?.tokens.input)} in · ${formatTokens(stats?.tokens.output)} out`}
        icon={IconTokens}
        accent={accent('var(--cyan)')}
      />
      {showProjects && (
        <StatCard
          label="Projects"
          value={stats?.projects ?? 0}
          foot="with agent activity"
          icon={IconFolder}
          accent={accent('var(--magenta)')}
        />
      )}
    </div>
  )
}
