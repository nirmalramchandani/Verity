/**
 * LiveActivity — Recent transactions feed
 * Shows the latest day's buy/sell activity across all tracked whales
 */
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWhaleData } from '../hooks/useWhaleData';
import { formatINR, truncateName } from '../utils/formatters';
import { Activity, ArrowUpRight, ArrowDownRight, Filter } from 'lucide-react';

export default function LiveActivity() {
  const { transactions, loading } = useWhaleData();
  const navigate = useNavigate();
  const [typeFilter, setTypeFilter] = useState('ALL');

  const filtered = useMemo(() => {
    if (!transactions.length) return [];
    let list = [...transactions];
    if (typeFilter !== 'ALL') {
      list = list.filter((t) => t.type === typeFilter);
    }
    return list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  }, [transactions, typeFilter]);

  const stats = useMemo(() => {
    const buys = transactions.filter((t) => t.type === 'BUY');
    const sells = transactions.filter((t) => t.type === 'SELL');
    const buyVol = buys.reduce((s, t) => s + (t.quantity || 0) * (t.price || 0), 0);
    const sellVol = sells.reduce((s, t) => s + (t.quantity || 0) * (t.price || 0), 0);
    return { buyCount: buys.length, sellCount: sells.length, buyVol, sellVol };
  }, [transactions]);

  if (loading) {
    return (
      <div className="loader-container">
        <div className="spinner" />
        <p className="loader-text">Streaming live activity...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6 animate-in">
        <div>
          <h1 className="page-title">Live Activity</h1>
          <p className="page-subtitle">Latest trading day — {filtered[0]?.date || 'No data'}</p>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={14} color="var(--text-muted)" />
          {['ALL', 'BUY', 'SELL'].map((t) => (
            <button
              key={t}
              className={`filter-chip ${typeFilter === t ? 'active' : ''}`}
              onClick={() => setTypeFilter(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Summary */}
      <div className="grid-4 mb-6">
        <div className="stat-card animate-in animate-in-delay-1">
          <div className="stat-label"><ArrowUpRight size={14} color="var(--accent-emerald)" /> Buys</div>
          <div className="stat-value text-success">{stats.buyCount}</div>
        </div>
        <div className="stat-card animate-in animate-in-delay-2">
          <div className="stat-label"><ArrowDownRight size={14} color="var(--accent-rose)" /> Sells</div>
          <div className="stat-value text-danger">{stats.sellCount}</div>
        </div>
        <div className="stat-card animate-in animate-in-delay-3">
          <div className="stat-label">Buy Volume</div>
          <div className="stat-value text-success font-mono">{formatINR(stats.buyVol)}</div>
        </div>
        <div className="stat-card animate-in animate-in-delay-4">
          <div className="stat-label">Sell Volume</div>
          <div className="stat-value text-danger font-mono">{formatINR(stats.sellVol)}</div>
        </div>
      </div>

      {/* Feed */}
      <div className="glass-card animate-in">
        <div className="section-title"><Activity size={14} /> Transaction Feed</div>
        <div className="table-container" style={{ maxHeight: 600, overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Investor</th>
                <th>Symbol</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Value</th>
                <th className="text-right">Profile</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.id}>
                  <td>
                    <span className={`badge ${t.type === 'BUY' ? 'badge-emerald' : 'badge-rose'}`}>
                      {t.type === 'BUY' ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
                      {t.type}
                    </span>
                  </td>
                  <td className="font-mono text-sm">{truncateName(t.client_id, 30)}</td>
                  <td className="font-mono font-bold">{t.symbol}</td>
                  <td className="font-mono">{(t.quantity || 0).toLocaleString()}</td>
                  <td className="font-mono">{formatINR(t.price, { compact: false })}</td>
                  <td className="font-mono">{formatINR((t.quantity || 0) * (t.price || 0))}</td>
                  <td className="text-right">
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => navigate(`/whale/${t.client_id}`)}
                    >
                      <ArrowUpRight size={12} />
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan="7" className="text-center text-muted" style={{ padding: '3rem' }}>
                    No activity data available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
