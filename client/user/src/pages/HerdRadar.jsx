/**
 * Herd Radar — Co-investment pattern detection
 * Detects when 3+ whales enter the same symbol within a 15-day window
 */
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWhaleData } from '../hooks/useWhaleData';
import { formatINR, formatDate, truncateName } from '../utils/formatters';
import { Radar, Users, ArrowUpRight, AlertCircle, TrendingUp, Zap } from 'lucide-react';

export default function HerdRadar() {
  const { investors, sells, loading, error } = useWhaleData();
  const navigate = useNavigate();
  const [windowDays, setWindowDays] = useState(15);

  // Detect co-investment herds from sell data (buy-side would need open lots)
  const herds = useMemo(() => {
    if (!sells.length) return [];

    // Build a map: symbol → [{ client_id, date, value }]
    const symbolMap = {};
    for (const s of sells) {
      const sym = s.symbol;
      if (!sym) continue;
      if (!symbolMap[sym]) symbolMap[sym] = [];
      symbolMap[sym].push({
        client: s.client_id,
        date: s.sell_date?.slice(0, 10),
        value: Math.abs((s.sell_quantity || 0) * (s.sell_price || 0)),
        pnl: s.pnl_amount || 0,
      });
    }

    const herdSignals = [];

    for (const [symbol, entries] of Object.entries(symbolMap)) {
      // Sort by date
      const sorted = entries.sort((a, b) => a.date?.localeCompare(b.date));

      // Sliding window: find clusters of 3+ unique investors within windowDays
      for (let i = 0; i < sorted.length; i++) {
        const startDate = new Date(sorted[i].date);
        const endDate = new Date(startDate);
        endDate.setDate(endDate.getDate() + windowDays);

        const window = sorted.filter((e) => {
          const d = new Date(e.date);
          return d >= startDate && d <= endDate;
        });

        const uniqueInvestors = [...new Set(window.map((w) => w.client))];

        if (uniqueInvestors.length >= 3) {
          const totalValue = window.reduce((s, w) => s + w.value, 0);
          const totalPnl = window.reduce((s, w) => s + w.pnl, 0);

          // Avoid duplicate signals for same symbol/window
          const key = `${symbol}-${sorted[i].date}`;
          if (!herdSignals.find((h) => h.key === key)) {
            herdSignals.push({
              key,
              symbol,
              startDate: sorted[i].date,
              investors: uniqueInvestors,
              investorCount: uniqueInvestors.length,
              totalValue,
              totalPnl,
              signalStrength: Math.min(uniqueInvestors.length / 5, 1), // 5+ = max
            });
          }
        }
      }
    }

    // Sort by investor count then by total value
    return herdSignals
      .sort((a, b) => b.investorCount - a.investorCount || b.totalValue - a.totalValue)
      .slice(0, 50);
  }, [sells, windowDays]);

  if (loading) {
    return (
      <div className="loader-container">
        <div className="spinner" />
        <p className="loader-text">Scanning for herd patterns...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6 animate-in">
        <div>
          <h1 className="page-title">Herd Radar</h1>
          <p className="page-subtitle">
            Co-investment detection — Find symbols where 3+ whales converge within a time window
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">Window:</span>
          {[7, 15, 30, 60].map((d) => (
            <button
              key={d}
              className={`filter-chip ${windowDays === d ? 'active' : ''}`}
              onClick={() => setWindowDays(d)}
            >
              {d}D
            </button>
          ))}
        </div>
      </div>

      {/* Summary */}
      <div className="grid-3 mb-6">
        <div className="stat-card animate-in animate-in-delay-1">
          <div className="stat-label"><Radar size={14} /> Signals Detected</div>
          <div className="stat-value text-info">{herds.length}</div>
        </div>
        <div className="stat-card animate-in animate-in-delay-2">
          <div className="stat-label"><Users size={14} /> Max Herd Size</div>
          <div className="stat-value">
            {herds.length > 0 ? herds[0].investorCount : 0}
          </div>
        </div>
        <div className="stat-card animate-in animate-in-delay-3">
          <div className="stat-label"><Zap size={14} /> Strongest Signal</div>
          <div className="stat-value text-warning">
            {herds.length > 0 ? (herds[0].signalStrength * 100).toFixed(0) + '%' : '—'}
          </div>
        </div>
      </div>

      {/* Herd Table */}
      <div className="glass-card animate-in animate-in-delay-4">
        <div className="section-title"><TrendingUp size={14} /> Detected Herds</div>
        <div className="table-container" style={{ maxHeight: 600, overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Window Start</th>
                <th>Whales</th>
                <th>Signal</th>
                <th>Total Value</th>
                <th>Combined PnL</th>
                <th>Investors</th>
              </tr>
            </thead>
            <tbody>
              {herds.length > 0 ? (
                herds.map((h) => (
                  <tr key={h.key}>
                    <td className="font-mono font-bold">{h.symbol}</td>
                    <td className="font-mono text-muted">{h.startDate}</td>
                    <td>
                      <span className="badge badge-blue">{h.investorCount} whales</span>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="progress-bar" style={{ width: 60 }}>
                          <div
                            className="progress-bar-fill"
                            style={{
                              width: `${h.signalStrength * 100}%`,
                              background: h.signalStrength > 0.6
                                ? 'var(--accent-emerald)'
                                : 'var(--gradient-blue)',
                            }}
                          />
                        </div>
                        <span className="font-mono text-xs">{(h.signalStrength * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="font-mono">{formatINR(h.totalValue)}</td>
                    <td className={`font-mono ${h.totalPnl >= 0 ? 'text-success' : 'text-danger'}`}>
                      {formatINR(h.totalPnl)}
                    </td>
                    <td>
                      <div className="flex gap-1" style={{ flexWrap: 'wrap', maxWidth: 300 }}>
                        {h.investors.slice(0, 3).map((inv) => (
                          <span
                            key={inv}
                            className="badge badge-dim cursor-pointer"
                            onClick={(e) => { e.stopPropagation(); navigate(`/whale/${inv}`); }}
                            title={inv}
                          >
                            {truncateName(inv, 15)}
                          </span>
                        ))}
                        {h.investors.length > 3 && (
                          <span className="badge badge-dim">+{h.investors.length - 3}</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="text-center text-muted" style={{ padding: '3rem' }}>
                    <Radar size={32} style={{ opacity: 0.3, margin: '0 auto 12px', display: 'block' }} />
                    No herd signals detected in the current window.
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
