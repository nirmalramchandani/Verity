export default function Checklist({ checks, completed }) {
  return (
    <ul className="checklist">
      {checks.map(([id, label], index) => {
        const status = completed[id] || 'pending';
        let icon = '⬜';
        let cls = 'pending';

        if (status === 'done') { icon = '✅'; cls = 'done'; }
        else if (status === 'warn') { icon = '⚠️'; cls = 'warn'; }
        else if (status === 'skipped') { icon = '⏭️'; cls = 'skipped'; }

        return (
          <li
            key={id}
            className={`checklist-item ${cls}`}
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <span className={`check-icon`}>{icon}</span>
            <span>{label}</span>
          </li>
        );
      })}
    </ul>
  );
}
