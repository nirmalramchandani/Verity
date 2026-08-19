import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import MetricCard from '../components/MetricCard';
import InvestorTable from '../components/InvestorTable';
import SellsTable from '../components/SellsTable';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('investors');
  const [investors, setInvestors] = useState([]);
  const [sells, setSells] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [invResp, sellResp] = await Promise.all([
        fetch(`${API_BASE}/data/investors?limit=100`),
        fetch(`${API_BASE}/data/sells?limit=100`),
      ]);

      if (invResp.ok) {
        const invData = await invResp.json();
        setInvestors(invData.data || []);
      }
      if (sellResp.ok) {
        const sellData = await sellResp.json();
        setSells(sellData.data || []);
      }
    } catch (err) {
      setError('Could not connect to API. Is the server running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ─── Computed metrics ──────────────────────────────────────────
  const metrics = useMemo(() => {
    if (!investors.length) return null;

    const scores = investors.map((inv) => inv.ranking_scores || {});
    const smartScores = scores.map((s) => s.smart_money_score || 0);
    const consistencyScores = scores.map((s) => s.consistency_score || 0);
    const convictionScores = scores.map((s) => s.conviction_score || 0);

    return {
      totalInvestors: investors.length,
      avgSmart: (smartScores.reduce((a, b) => a + b, 0) / smartScores.length).toFixed(2),
      maxConsistency: Math.max(...consistencyScores).toFixed(2),
      avgConviction: (convictionScores.reduce((a, b) => a + b, 0) / convictionScores.length).toFixed(2),
    };
  }, [investors]);

  // ─── Chart data ────────────────────────────────────────────────
  const pnlBySymbol = useMemo(() => {
    if (!sells.length) return [];
    const grouped = {};
    for (const s of sells) {
      if (!grouped[s.symbol]) grouped[s.symbol] = 0;
      grouped[s.symbol] += s.pnl_amount || 0;
    }
    return Object.entries(grouped)
      .map(([symbol, pnl]) => ({ symbol, pnl: parseFloat(pnl.toFixed(2)) }))
      .sort((a, b) => b.pnl - a.pnl);
  }, [sells]);

  const scatterData = useMemo(() => {
    return sells.map((s) => ({
      symbol: s.symbol,
      pnl_percentage: s.pnl_percentage || 0,
      exit_type: s.exit_type || 'unknown',
    }));
  }, [sells]);

  const volumeByDate = useMemo(() => {
    if (!sells.length) return [];
    const grouped = {};
    for (const s of sells) {
      const date = s.sell_date?.slice(0, 10) || 'unknown';
      if (!grouped[date]) grouped[date] = 0;
      grouped[date] += s.sell_quantity || 0;
    }
    return Object.entries(grouped)
      .map(([date, volume]) => ({ date, volume }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [sells]);

  const tabs = [
    { id: 'investors', label: '👤 Investor Intelligence' },
    { id: 'sells', label: '💸 Recent Sells' },
    { id: 'analytics', label: '📉 Performance Analytics' },
  ];

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h2>📊 Analytics Dashboard</h2>
            <p className="description">Real-time insights from the Verity intelligence engine.</p>
          </div>
          <button className="btn btn-secondary" onClick={fetchData} disabled={loading}>
            {loading ? <span className="spinner" /> : '🔄'} Refresh
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="status-message status-error mb-lg">
          <span>❌</span> {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center" style={{ padding: 'var(--space-2xl)' }}>
          <div className="spinner" style={{ width: 32, height: 32, margin: '0 auto var(--space-md)' }} />
          <div className="text-muted">Loading data...</div>
        </div>
      )}

      {!loading && !investors.length && !sells.length && !error && (
        <div className="status-message status-warning">
          <span>📭</span> No data found. Please run the ingestion pipeline first.
        </div>
      )}

      {!loading && (investors.length > 0 || sells.length > 0) && (
        <>
          {/* Metrics */}
          {metrics && (
            <div className="metrics-grid">
              <MetricCard label="Total Investors" value={metrics.totalInvestors} accent="blue" />
              <MetricCard label="Avg Smart Score" value={metrics.avgSmart} accent="green" />
              <MetricCard label="Max Consistency" value={metrics.maxConsistency} accent="purple" />
              <MetricCard label="Avg Conviction" value={metrics.avgConviction} accent="cyan" />
            </div>
          )}

          {/* Tabs */}
          <div className="tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                className={`tab${activeTab === tab.id ? ' active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === 'investors' && (
            <div className="card">
              <div className="card-header">
                <span className="card-title">Top Investors by Smart Money Score</span>
                <span className="badge badge-info">{investors.length} total</span>
              </div>
              <InvestorTable investors={investors} />
            </div>
          )}

          {activeTab === 'sells' && (
            <div className="card">
              <div className="card-header">
                <span className="card-title">Recent Sell Transactions</span>
                <span className="badge badge-info">{sells.length} total</span>
              </div>
              <SellsTable sells={sells} />
            </div>
          )}

          {activeTab === 'analytics' && (
            <>
              {sells.length > 0 ? (
                <>
                  {/* PnL Bar Chart */}
                  <div className="card mb-lg">
                    <div className="card-header">
                      <span className="card-title">PnL by Symbol</span>
                    </div>
                    <div className="chart-container">
                      <ResponsiveContainer width="100%" height="100%" minWidth={1}>
                        <BarChart data={pnlBySymbol}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="symbol" />
                          <YAxis />
                          <Tooltip
                            contentStyle={{
                              background: '#0a0f1e',
                              border: '1px solid rgba(255,255,255,0.1)',
                              borderRadius: 10,
                            }}
                          />
                          <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                            {pnlBySymbol.map((entry, index) => (
                              <Cell
                                key={index}
                                fill={entry.pnl >= 0 ? '#00ff88' : '#ef4444'}
                                fillOpacity={0.7}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="charts-grid">
                    {/* Scatter Chart */}
                    <div className="card">
                      <div className="card-header">
                        <span className="card-title">PnL % by Symbol</span>
                      </div>
                      <div className="chart-container">
                        <ResponsiveContainer width="100%" height="100%" minWidth={1}>
                          <ScatterChart>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="symbol" name="Symbol" />
                            <YAxis dataKey="pnl_percentage" name="PnL %" />
                            <Tooltip
                              contentStyle={{
                                background: '#0a0f1e',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: 10,
                              }}
                            />
                            <Scatter data={scatterData} fill="#3b82f6" fillOpacity={0.7} />
                          </ScatterChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Volume Line Chart */}
                    <div className="card">
                      <div className="card-header">
                        <span className="card-title">Activity Volume Over Time</span>
                      </div>
                      <div className="chart-container">
                        <ResponsiveContainer width="100%" height="100%" minWidth={1}>
                          <LineChart data={volumeByDate}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="date" />
                            <YAxis />
                            <Tooltip
                              contentStyle={{
                                background: '#0a0f1e',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: 10,
                              }}
                            />
                            <Line
                              type="monotone"
                              dataKey="volume"
                              stroke="#06b6d4"
                              strokeWidth={2}
                              dot={{ fill: '#06b6d4', r: 3 }}
                              activeDot={{ r: 6, fill: '#06b6d4' }}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="status-message status-info">
                  <span>📊</span> Ingest data to see performance analytics.
                </div>
              )}
            </>
          )}
        </>
      )}
    </>
  );
}
