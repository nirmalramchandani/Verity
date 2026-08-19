import { useState, useMemo } from 'react';

export default function SellsTable({ sells }) {
  const [sortKey, setSortKey] = useState('sell_date');
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
    if (!sells || sells.length === 0) return [];
    return [...sells].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (typeof aVal === 'number') return sortAsc ? aVal - bVal : bVal - aVal;
      return sortAsc
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal));
    });
  }, [sells, sortKey, sortAsc]);

  const columns = [
    { key: 'client_id', label: 'Client' },
    { key: 'symbol', label: 'Symbol' },
    { key: 'sell_date', label: 'Date' },
    { key: 'sell_quantity', label: 'Qty' },
    { key: 'sell_price', label: 'Price' },
    { key: 'pnl_amount', label: 'PnL' },
    { key: 'pnl_percentage', label: 'PnL %' },
    { key: 'exit_type', label: 'Exit' },
  ];

  if (rows.length === 0) {
    return (
      <div className="status-message status-info">
        <span>📭</span> No sell transactions yet.
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
          {rows.map((row, i) => (
            <tr key={i}>
              <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{row.client_id}</td>
              <td><strong>{row.symbol}</strong></td>
              <td>{row.sell_date}</td>
              <td>{row.sell_quantity}</td>
              <td>{typeof row.sell_price === 'number' ? row.sell_price.toFixed(2) : row.sell_price}</td>
              <td>
                <span className={row.pnl_amount >= 0 ? 'badge badge-success' : 'badge badge-error'}>
                  {typeof row.pnl_amount === 'number' ? row.pnl_amount.toFixed(2) : row.pnl_amount}
                </span>
              </td>
              <td>
                <span style={{
                  color: row.pnl_percentage >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'
                }}>
                  {typeof row.pnl_percentage === 'number' ? `${row.pnl_percentage.toFixed(2)}%` : row.pnl_percentage}
                </span>
              </td>
              <td>
                <span className="badge badge-info">{row.exit_type}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
