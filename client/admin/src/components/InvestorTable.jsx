import { useState, useMemo } from 'react';

export default function InvestorTable({ investors }) {
  const [sortKey, setSortKey] = useState('smart_money_score');
  const [sortAsc, setSortAsc] = useState(false);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const rows = useMemo(() => {
    if (!investors || investors.length === 0) return [];

    return investors
      .map((inv) => {
        const scores = inv.ranking_scores || {};
        return {
          id: inv._id,
          smart_money_score: scores.smart_money_score ?? 0,
          consistency_score: scores.consistency_score ?? 0,
          conviction_score: scores.conviction_score ?? 0,
          risk_management_score: scores.risk_management_score ?? 0,
        };
      })
      .sort((a, b) => {
        const aVal = a[sortKey] ?? 0;
        const bVal = b[sortKey] ?? 0;
        return sortAsc ? aVal - bVal : bVal - aVal;
      });
  }, [investors, sortKey, sortAsc]);

  const columns = [
    { key: 'id', label: 'Investor ID' },
    { key: 'smart_money_score', label: 'Smart Score' },
    { key: 'consistency_score', label: 'Consistency' },
    { key: 'conviction_score', label: 'Conviction' },
    { key: 'risk_management_score', label: 'Risk Mgmt' },
  ];

  if (rows.length === 0) {
    return (
      <div className="status-message status-info">
        <span>📭</span> No investor data available.
      </div>
    );
  }

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className={sortKey === col.key ? 'sorted' : ''}
              >
                {col.label}
                <span className="sort-icon">
                  {sortKey === col.key ? (sortAsc ? '↑' : '↓') : '↕'}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{row.id}</td>
              <td>
                <span className="badge badge-success">{row.smart_money_score.toFixed(2)}</span>
              </td>
              <td>{row.consistency_score.toFixed(2)}</td>
              <td>{row.conviction_score.toFixed(2)}</td>
              <td>{row.risk_management_score.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
