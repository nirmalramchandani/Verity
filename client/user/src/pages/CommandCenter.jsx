import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWhaleData } from '../hooks/useWhaleData';
import { formatINR, formatPct, pnlColor, truncateName, getArchetype } from '../utils/formatters';
import DNABadge from '../components/DNABadge';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, PieChart, Pie,
} from 'recharts';
import {
  TrendingUp, Users, Zap, Target, Activity, ArrowUpRight,
  AlertCircle, ChevronRight, BarChart3,
} from 'lucide-react';

const TIME_FILTERS = [
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '1Y', days: 365 },
  { label: '5Y', days: 1825 },
  { label: 'ALL', days: 9999 },
];

export default function CommandCenter() {
  const { investors, sells, transactions, loading, error } = useWhaleData();
  const [daysFilter, setDaysFilter] = useState(365);
  const navigate = useNavigate();

  // Filter sells by time
  const filteredSells = useMemo(() => {
    if (!sells.length) return [];
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - daysFilter);
    return sells.filter((s) => new Date(s.sell_date) >= cutoff);
  }, [sells, daysFilter]);

  // Top PnL performers
  const topWhales = useMemo(() => {
    if (!filteredSells.length) return [];
    const pnlMap = {};
    for (const s of filteredSells) {
      pnlMap[s.client_id] = (pnlMap[s.client_id] || 0) + (s.pnl_amount || 0);
    }
    const invMap = {};
    for (const inv of investors) invMap[inv._id] = inv;

    return Object.entries(pnlMap)
      .map(([id, pnl]) => ({
        id,
        pnl,
        score: invMap[id]?.ranking_scores?.smart_money_score || 0,
        investor: invMap[id],
      }))
      .sort((a, b) => b.pnl - a.pnl)
      .slice(0, 8);
  }, [filteredSells, investors]);

  // Cumulative PnL trend
  const pnlTrend = useMemo(() => {
    const map = {};
    for (const s of filteredSells) {
      const d = s.sell_date?.slice(0, 10);
      if (d) map[d] = (map[d] || 0) + (s.pnl_amount || 0);
    }
    let cum = 0;
    return Object.entries(map)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, amt]) => {
        cum += amt;
        return { date, pnl: Math.round(cum) };
      });
  }, [filteredSells]);

  // Sector breakdown from investors
  const sectorData = useMemo(() => {
    const map = {};
    for (const inv of investors) {
      const sector = inv.behavioral_dna?.favorite_sector || 'OTHER';
      map[sector] = (map[sector] || 0) + 1;
    }
    return Object.entries(map)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  }, [investors]);

  // Summary stats
  const stats = useMemo(() => {
    const totalPnl = filteredSells.reduce((sum, s) => sum + (s.pnl_amount || 0), 0);
    const wins = filteredSells.filter((s) => s.pnl_amount > 0).length;
    const total = filteredSells.length;
    return {
      totalPnl,
      totalDeals: total,
      winRate: total > 0 ? (wins / total) * 100 : 0,
      activeWhales: investors.length,
    };
  }, [filteredSells, investors]);

  // Type distribution
  const typeDist = useMemo(() => {
    const map = {};
    for (const inv of investors) {
      const t = inv.identity?.investor_type || 'UNKNOWN';
      map[t] = (map[t] || 0) + 1;
    }
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [investors]);

  const PIE_COLORS = ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#f43f5e', '#64748b', '#6366f1'];

  if (loading) {
    return (
      <div className="loader-container">
        <div className="spinner" />
        <p className="loader-text">Initializing Verity Terminal...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card flex items-center gap-4" style={{ borderColor: 'var(--accent-rose)' }}>
        <AlertCircle size={24} color="var(--accent-rose)" />
        <div>
          <h3>Connection Error</h3>
          <p className="text-muted">{error}</p>
        </div>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-primary)',
        borderRadius: '8px',
        padding: '10px 14px',
        fontSize: '0.8rem',
      }}>
        <div className="text-muted text-xs mb-2">{label}</div>
        <div className="font-mono font-bold" style={{ color: payload[0].value >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
          {formatINR(payload[0].value)}
        </div>
      </div>
    );
  };

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6 animate-in">
        <div>
          <h1 className="page-title">Market Dashboard</h1>
          <p className="page-subtitle">
            Institutional capital flow across {investors.length.toLocaleString()} tracked entities
          </p>
        </div>
        <div className="flex items-center gap-2">
          {TIME_FILTERS.map((f) => (
            <button
              key={f.days}
              className={`filter-chip ${daysFilter === f.days ? 'active' : ''}`}
              onClick={() => setDaysFilter(f.days)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid-4 mb-6">
        <div className="stat-card animate-in animate-in-delay-1">
          <div className="stat-label"><Users size={14} /> Institutional Allocators</div>
          <div className="stat-value text-info">{stats.activeWhales.toLocaleString()}</div>
          <div className="stat-delta text-muted">Unique market participants</div>
        </div>
        <div className="stat-card animate-in animate-in-delay-2">
          <div className="stat-label"><TrendingUp size={14} /> Realized PnL</div>
          <div className={`stat-value ${stats.totalPnl >= 0 ? 'text-success' : 'text-danger'}`}>
            {formatINR(stats.totalPnl)}
          </div>
          <div className="stat-delta text-muted">Selected timeframe</div>
        </div>
        <div className="stat-card animate-in animate-in-delay-3">
          <div className="stat-label"><Target size={14} /> Win Rate</div>
          <div className="stat-value text-accent">{stats.winRate.toFixed(1)}%</div>
          <div className="stat-delta text-muted">Of {stats.totalDeals.toLocaleString()} exit deals</div>
        </div>
        <div className="stat-card animate-in animate-in-delay-4">
          <div className="stat-label"><Activity size={14} /> Total Deals</div>
          <div className="stat-value text-warning">{stats.totalDeals.toLocaleString()}</div>
          <div className="stat-delta text-muted">Closed transaction lots</div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid-3 mb-6">
        {/* PnL Trend */}
        <div className="glass-card animate-in" style={{ gridColumn: 'span 2' }}>
          <div className="section-title"><Zap size={14} /> Cumulative Institutional PnL</div>
          <div style={{ height: 220 }}>
            {pnlTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={pnlTrend}>
                  <defs>
                    <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" hide />
                  <YAxis width={70} tickFormatter={(v) => formatINR(v)} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="pnl"
                    stroke="var(--accent-blue)"
                    strokeWidth={2}
                    fill="url(#pnlGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state"><p>No trend data for period</p></div>
            )}
          </div>
        </div>

        {/* Sector Breakdown */}
        <div className="glass-card animate-in">
          <div className="section-title"><BarChart3 size={14} /> Sector Focus</div>
          <div style={{ height: 220 }}>
            {sectorData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sectorData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={75}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                  >
                    {sectorData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border-primary)',
                      borderRadius: '8px',
                      fontSize: '0.8rem',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state"><p>No sector data</p></div>
            )}
          </div>
          <div className="flex flex-col gap-1 mt-2">
            {sectorData.slice(0, 4).map((s, i) => (
              <div key={s.name} className="flex justify-between items-center text-xs">
                <div className="flex items-center gap-2">
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: PIE_COLORS[i] }} />
                  <span className="text-secondary">{s.name}</span>
                </div>
                <span className="font-mono text-muted">{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top Whales Table */}
      <div className="glass-card animate-in">
        <div className="flex justify-between items-center mb-4">
          <div className="section-title" style={{ marginBottom: 0 }}>
            <TrendingUp size={14} /> Top Performing Whales
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/whales')}>
            View All <ChevronRight size={14} />
          </button>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Investor</th>
                <th>Archetype</th>
                <th>Period PnL</th>
                <th>Smart Score</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {topWhales.length > 0 ? (
                topWhales.map((w, idx) => (
                  <tr key={w.id}>
                    <td>
                      <span className={`badge ${idx < 3 ? 'badge-amber' : 'badge-dim'}`}>
                        #{idx + 1}
                      </span>
                    </td>
                    <td className="font-mono text-sm">{truncateName(w.id, 35)}</td>
                    <td>{w.investor && <DNABadge investor={w.investor} size="small" />}</td>
                    <td className={`font-mono ${pnlColor(w.pnl)}`}>
                      {formatINR(w.pnl)}
                    </td>
                    <td className="font-mono">{w.score.toFixed(1)}</td>
                    <td className="text-right">
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => navigate(`/whale/${w.id}`)}
                      >
                        Profile <ArrowUpRight size={12} />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" className="text-center text-muted" style={{ padding: '2rem' }}>
                    No exits found in selected period.
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
