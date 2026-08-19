export default function MetricCard({ label, value, accent }) {
  const accentColor = {
    blue: 'var(--accent-blue)',
    green: 'var(--accent-green)',
    purple: 'var(--accent-purple)',
    amber: 'var(--accent-amber)',
    cyan: 'var(--accent-cyan)',
  }[accent] || 'var(--accent-blue)';

  return (
    <div className="metric-card" style={{ '--metric-accent': accentColor }}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}
