import { useMemo, useState } from 'react'

import QueryState from './QueryState.jsx'
import { api } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { formatTokens } from '../utils/format.js'

/**
 * Which agents a session ran and who launched whom (the SessionWindow's
 * Interactions tab).
 *
 * Drawn left to right as a tree: the session's main agent on the left, each
 * agent's subagents in the next column, joined by arrows numbered in launch
 * order. Clicking a node shows what it was asked and what it returned.
 *
 * The layout is computed from the graph alone, never measured from the DOM,
 * so it is right even while the tab is hidden: a column per tree depth, a row
 * per leaf, and every parent centred on its children.
 */

const NODE_W = 230
const NODE_H = 92
const COL_GAP = 110
const ROW_GAP = 26
const PAD = 24

const STATUS_LABEL = { work: 'Working', done: 'Done', error: 'Failed' }

/** Grid positions ({col, row}, rows possibly fractional) for every node. */
function layoutTree(nodes, edges) {
  const children = new Map(nodes.map((n) => [n.id, []]))
  const hasParent = new Set()
  for (const e of [...edges].sort((a, b) => a.order - b.order)) {
    if (!children.has(e.from) || !children.has(e.to)) continue
    children.get(e.from).push(e.to)
    hasParent.add(e.to)
  }

  const pos = new Map()
  let nextRow = 0
  const place = (id, col) => {
    if (pos.has(id)) return pos.get(id).row // a cycle or a second parent
    pos.set(id, { col, row: 0 }) // claim it before descending
    const kids = children.get(id).filter((k) => !pos.has(k))
    let row
    if (!kids.length) {
      row = nextRow++
    } else {
      const rows = kids.map((k) => place(k, col + 1))
      row = (rows[0] + rows[rows.length - 1]) / 2
    }
    pos.set(id, { col, row })
    return row
  }

  // Roots are agents nobody launched — normally just the main agent.
  for (const n of nodes) if (!hasParent.has(n.id)) place(n.id, 0)
  for (const n of nodes) if (!pos.has(n.id)) place(n.id, 0)

  const cols = Math.max(0, ...[...pos.values()].map((p) => p.col)) + 1
  return { pos, cols, rows: Math.max(nextRow, 1) }
}

const toPixels = ({ col, row }) => ({
  x: PAD + col * (NODE_W + COL_GAP),
  y: PAD + row * (NODE_H + ROW_GAP),
})

function formatDuration(ms) {
  if (ms == null) return null
  const s = ms / 1000
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

function Edge({ from, to, edge, status }) {
  const x1 = from.x + NODE_W
  const y1 = from.y + NODE_H / 2
  const x2 = to.x
  const y2 = to.y + NODE_H / 2
  const bend = COL_GAP / 2
  // Midpoint of the cubic Bézier, where the launch-order badge sits.
  const mx = (x1 + 3 * (x1 + bend) + 3 * (x2 - bend) + x2) / 8
  const my = (y1 + 3 * y1 + 3 * y2 + y2) / 8

  return (
    <g className={`graph-edge graph-edge--${status}`}>
      <path
        d={`M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2 - 2} ${y2}`}
        markerEnd={`url(#arrow-${status})`}
      />
      <circle cx={mx} cy={my} r={9} className="graph-edge__badge" />
      <text x={mx} y={my} className="graph-edge__order">
        {edge.order}
      </text>
    </g>
  )
}

function Node({ node, at, selected, onSelect }) {
  const meta = [
    `${formatTokens(node.tokens)} tok`,
    node.toolCalls != null && `${node.toolCalls} tools`,
    formatDuration(node.durationMs),
  ].filter(Boolean)

  return (
    <button
      className={[
        'graph-node',
        `graph-node--${node.status}`,
        node.kind === 'agent' ? 'graph-node--main' : '',
        selected ? 'graph-node--selected' : '',
      ].join(' ')}
      style={{ left: at.x, top: at.y, width: NODE_W, height: NODE_H }}
      onClick={() => onSelect(node.id)}
      title={node.label}
    >
      <span className="graph-node__head">
        <span className="graph-node__type">
          {node.kind === 'agent' ? 'Main' : node.agentType}
        </span>
        <span
          className={`dot ${node.status === 'work' ? 'dot--work' : ''}`}
          title={STATUS_LABEL[node.status]}
        />
      </span>
      <span className="graph-node__label">{node.label}</span>
      <span className="graph-node__meta">{meta.join(' · ')}</span>
    </button>
  )
}

function Detail({ node, parent, launched }) {
  return (
    <div className="graph-detail">
      <div className="graph-detail__head">
        <span className="graph-detail__title">{node.label}</span>
        <span className="chip">{node.kind === 'agent' ? 'main agent' : node.agentType}</span>
        <span className={`chip graph-status graph-status--${node.status}`}>
          {STATUS_LABEL[node.status] ?? node.status}
        </span>
      </div>

      <dl className="graph-detail__facts">
        <dt>Model</dt>
        <dd className="cell-mono">{node.model ?? '—'}</dd>
        <dt>Tokens</dt>
        <dd>{formatTokens(node.tokens)}</dd>
        <dt>Tool calls</dt>
        <dd>{node.toolCalls ?? '—'}</dd>
        <dt>Duration</dt>
        <dd>{formatDuration(node.durationMs) ?? (node.status === 'work' ? 'running' : '—')}</dd>
        {parent && (
          <>
            <dt>Launched by</dt>
            <dd>{parent.label}</dd>
          </>
        )}
        {launched.length > 0 && (
          <>
            <dt>Launched</dt>
            <dd>{launched.map((n) => n.label).join(', ')}</dd>
          </>
        )}
      </dl>

      {node.prompt && (
        <div className="graph-detail__block">
          <div className="field__label">Task</div>
          <p>{node.prompt}</p>
        </div>
      )}
      {node.result && (
        <div className="graph-detail__block">
          <div className="field__label">{node.status === 'error' ? 'Error' : 'Result'}</div>
          <p>{node.result}</p>
        </div>
      )}
    </div>
  )
}

export default function InteractionGraph({ projectId, agentId, session }) {
  const { data, loading, error } = useApi(
    () => api.sessionInteractions(projectId, agentId, session.id),
    { intervalMs: 0, key: session.id },
  )
  const [selectedId, setSelectedId] = useState(null)

  const nodes = data?.nodes ?? []
  const edges = data?.edges ?? []
  const { pos, cols, rows } = useMemo(() => layoutTree(nodes, edges), [nodes, edges])
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  const width = PAD * 2 + cols * NODE_W + (cols - 1) * COL_GAP
  const height = PAD * 2 + rows * NODE_H + (rows - 1) * ROW_GAP

  const selected = byId.get(selectedId) ?? nodes.find((n) => n.kind === 'agent') ?? nodes[0]
  const parentEdge = selected && edges.find((e) => e.to === selected.id)
  const launched = selected
    ? edges
        .filter((e) => e.from === selected.id)
        .sort((a, b) => a.order - b.order)
        .map((e) => byId.get(e.to))
        .filter(Boolean)
    : []

  return (
    <QueryState loading={loading} error={error}>
      {data && nodes.length <= 1 ? (
        <div className="state">
          <div className="state__title">No subagents</div>
          <div className="state__hint">This session has not launched any subagents.</div>
        </div>
      ) : (
        <div className="graph">
          {data?.mock && (
            <div className="notice graph__notice">
              <strong>Sample data.</strong> This graph is a mock, not read from this
              session yet.
            </div>
          )}

          <div className="graph__canvas-wrap">
            <div className="graph__canvas" style={{ width, height }}>
              <svg className="graph__edges" width={width} height={height}>
                <defs>
                  {['work', 'done', 'error'].map((status) => (
                    <marker
                      key={status}
                      id={`arrow-${status}`}
                      className={`graph-arrow graph-arrow--${status}`}
                      viewBox="0 0 10 10"
                      refX="9"
                      refY="5"
                      markerWidth="8"
                      markerHeight="8"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 0 L 10 5 L 0 10 z" />
                    </marker>
                  ))}
                </defs>
                {edges.map((e) =>
                  pos.has(e.from) && pos.has(e.to) ? (
                    <Edge
                      key={`${e.from}-${e.to}`}
                      edge={e}
                      from={toPixels(pos.get(e.from))}
                      to={toPixels(pos.get(e.to))}
                      status={byId.get(e.to)?.status ?? 'done'}
                    />
                  ) : null,
                )}
              </svg>

              {nodes.map((n) => (
                <Node
                  key={n.id}
                  node={n}
                  at={toPixels(pos.get(n.id))}
                  selected={selected?.id === n.id}
                  onSelect={setSelectedId}
                />
              ))}
            </div>
          </div>

          {selected && (
            <Detail
              node={selected}
              parent={parentEdge ? byId.get(parentEdge.from) : null}
              launched={launched}
            />
          )}
        </div>
      )}
    </QueryState>
  )
}
