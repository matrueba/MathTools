import { formatRelative } from '../utils/format.js'

export const IconBranch = (props) => (
  <svg
    width="13"
    height="13"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.9"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <circle cx="6" cy="5" r="2.2" />
    <circle cx="6" cy="19" r="2.2" />
    <circle cx="18" cy="9" r="2.2" />
    <path d="M6 7.2v9.6M18 11.2c0 4-4 3.6-6.4 4.6" />
  </svg>
)

/** Branch, working-tree state and divergence from the remote. */
export function GitChips({ git }) {
  if (!git) return null

  return (
    <div className="chips">
      <span className="chip chip--branch">
        <IconBranch />
        {git.branch}
      </span>

      {git.dirty ? (
        <span className="chip chip--dirty">
          {git.changedFiles} changed
        </span>
      ) : (
        <span className="chip">clean</span>
      )}

      {git.ahead > 0 && <span className="chip">↑{git.ahead}</span>}
      {git.behind > 0 && <span className="chip">↓{git.behind}</span>}
      {!git.remote && <span className="chip">no remote</span>}
    </div>
  )
}

/** Last commit line: `8904f76 · add gemini to monitoring · 2h ago`. */
export function LastCommit({ commit }) {
  if (!commit?.hash) return <div className="commit">No commits yet</div>

  return (
    <div className="commit" title={commit.message}>
      <span className="commit__hash">{commit.hash}</span>
      <span className="commit__msg">{commit.message}</span>
      <span className="commit__at">{formatRelative(commit.at)}</span>
    </div>
  )
}
