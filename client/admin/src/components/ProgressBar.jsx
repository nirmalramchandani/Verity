export default function ProgressBar({ percent, label }) {
  const clamped = Math.max(0, Math.min(100, percent));

  return (
    <div className="progress-container">
      <div className="progress-label">
        <span>{label || 'Progress'}</span>
        <span>{clamped}%</span>
      </div>
      <div className="progress-track">
        <div
          className={`progress-fill${clamped >= 100 ? ' complete' : ''}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
