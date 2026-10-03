import StatRow from '../../components/StatRow.jsx'
import TokenBreakdown from '../../components/TokenBreakdown.jsx'
import { GitChips, LastCommit } from '../../components/GitInfo.jsx'

/**
 * Repository state and headline metrics for one project.
 *
 * This is everything that used to sit above the tabs; moving it here keeps the
 * Sessions and Harness tabs full-height. `showProjects` is off because the
 * count is always 1 inside a project.
 */
export default function OverviewTab({ project }) {
  return (
    <>
      <div className="card project-head">
        <div className="project-head__main">
          <div className="project-head__name">{project.name}</div>
          <div className="project__path">{project.path}</div>
          <GitChips git={project.git} />
          <LastCommit commit={project.git.lastCommit} />
        </div>
        {project.git.remote && (
          <a
            className="btn"
            href={project.git.remote.replace(/\.git$/, '')}
            target="_blank"
            rel="noreferrer"
          >
            Remote ↗
          </a>
        )}
      </div>

      <StatRow stats={project.stats} showProjects={false} />

      <TokenBreakdown tokens={project.stats.tokens} />
    </>
  )
}
