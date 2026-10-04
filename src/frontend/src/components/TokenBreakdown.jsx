import { formatTokens } from '../utils/format.js'

const ROWS = [
  { key: 'input', label: 'Input', color: 'var(--yellow)' },
  { key: 'output', label: 'Output', color: 'var(--magenta)' },
  { key: 'cacheRead', label: 'Cache R', color: 'var(--cyan)' },
  { key: 'cacheWrite', label: 'Cache W', color: 'var(--blue)' },
]

export default function TokenBreakdown({ tokens }) {
  // Bars are scaled against the largest bucket, not the total — cache reads
  // dwarf everything else, so a total-relative scale would flatten the rest.
  const max = Math.max(...ROWS.map((r) => tokens?.[r.key] ?? 0), 1)

  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Token usage</span>
        <span className="card__hint">{formatTokens(tokens?.total)} total</span>
      </div>
      <div style={{ padding: '6px 0 12px' }}>
        {ROWS.map(({ key, label, color }) => {
          const value = tokens?.[key] ?? 0
          return (
            <div className="tokenrow" key={key}>
              <div className="tokenrow__label">{label}</div>
              <div className="meter">
                <div
                  className="meter__fill"
                  style={{ width: `${(value / max) * 100}%`, background: color }}
                />
              </div>
              <div className="tokenrow__value">{formatTokens(value)}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
