/** 1_284_500 → "1.3M" — same abbreviation the CLI dashboard uses. */
export function formatTokens(value) {
  const n = Number(value) || 0
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

/**
 * Epoch seconds → "4s ago" / "31m ago" / "2h ago".
 * `short` drops the suffix ("4s") for the narrow dashboard table.
 */
export function formatRelative(epochSeconds, short = false) {
  if (!epochSeconds) return '—'
  const diff = Math.max(0, Date.now() / 1000 - epochSeconds)
  const suffix = short ? '' : ' ago'

  if (diff < 60) return `${Math.floor(diff)}s${suffix}`
  if (diff < 3600) return `${Math.floor(diff / 60)}m${suffix}`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h${suffix}`
  return `${Math.floor(diff / 86400)}d${suffix}`
}

/** Context saturation colour, matching the CLI's green/yellow/red thresholds. */
export function contextColor(pct) {
  if (pct < 60) return 'var(--green)'
  if (pct < 85) return 'var(--yellow)'
  return 'var(--red)'
}
