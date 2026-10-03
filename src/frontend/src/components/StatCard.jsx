export default function StatCard({ label, value, foot, icon: Icon, accent }) {
  return (
    <div className="stat">
      <div className="stat__label">
        {Icon && <Icon width={13} height={13} style={{ color: accent }} />}
        {label}
      </div>
      <div className="stat__value" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      {foot && <div className="stat__foot">{foot}</div>}
    </div>
  )
}
