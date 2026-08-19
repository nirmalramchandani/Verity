import { useMemo, useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useWhaleData, useInvestorProfile, useWhalePortfolio } from '../hooks/useWhaleData';
import {
  formatINR, formatPct, formatDate, formatHoldPeriod,
  pnlColor, pnlCSSColor, truncateName, getArchetype,
} from '../utils/formatters';
import DNABadge from '../components/DNABadge';
import ScoreRing from '../components/ScoreRing';
import PortfolioView from '../components/PortfolioView';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, PieChart, Pie, ScatterChart,
  Scatter, ZAxis,
} from 'recharts';
import {
  ArrowLeft, User, Target, Activity, TrendingUp, Shield,
  Clock, Crosshair, BarChart3, PieChart as PieIcon, Layers,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function WhaleProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { investors, sells, loading: globalLoading } = useWhaleData();

  // Try from cache first, then direct fetch
  const cachedProfile = useMemo(() => investors.find((i) => i._id === id), [investors, id]);
  const { profile: fetchedProfile, loading: fetchLoading } = useInvestorProfile(
    cachedProfile ? null : id
  );
  const profile = cachedProfile || fetchedProfile;
  const { portfolio, loading: portfolioLoading } = useWhalePortfolio(id);
  const loading = globalLoading || fetchLoading;

  // Client trades from sells data
  const clientTrades = useMemo(() => {
    if (!sells.length) return [];
    return sells
      .filter((s) => s.client_id === id)
      .sort((a, b) => new Date(a.sell_date) - new Date(b.sell_date));
  }, [sells, id]);

  // Computed statistics
  const stats = useMemo(() => {
    if (!clientTrades.length) return null;
    let realized = 0, wins = 0, cum = 0;
    const timeline = [];
    const returnDist = [];

    for (const t of clientTrades) {
      realized += t.pnl_amount || 0;
      if (t.pnl_amount > 0) wins++;
      cum += t.pnl_amount || 0;
      timeline.push({ date: t.sell_date?.slice(0, 10), pnl: Math.round(cum) });

      // Bucket returns for histogram
      const pct = t.pnl_percentage || 0;
      returnDist.push(pct);
    }

    return {
      firstTrade: clientTrades[0].sell_date?.slice(0, 10),
      lastTrade: clientTrades[clientTrades.length - 1].sell_date?.slice(0, 10),
      realized,
      winRate: (wins / clientTrades.length) * 100,
      totalTrades: clientTrades.length,
      timeline,
      returnDist,
    };
  }, [clientTrades]);

  // Return distribution histogram
  const histogram = useMemo(() => {
    if (!stats?.returnDist?.length) return [];
    const buckets = {};
    for (const pct of stats.returnDist) {
      let bucket;
      if (pct < -50) bucket = '< -50%';
      else if (pct < -20) bucket = '-50 to -20%';
      else if (pct < 0) bucket = '-20 to 0%';
      else if (pct < 20) bucket = '0 to 20%';
      else if (pct < 50) bucket = '20 to 50%';
      else if (pct < 100) bucket = '50 to 100%';
      else bucket = '> 100%';
      buckets[bucket] = (buckets[bucket] || 0) + 1;
    }
    const order = ['< -50%', '-50 to -20%', '-20 to 0%', '0 to 20%', '20 to 50%', '50 to 100%', '> 100%'];
    return order.map((name) => ({ name, count: buckets[name] || 0 }));
  }, [stats]);

  // Portfolio composition (positions)
  const positions = useMemo(() => {
    if (!profile?.portfolio_state?.positions) return [];
    return profile.portfolio_state.positions
      .filter((p) => p.qty > 0)
      .sort((a, b) => b.position_weight - a.position_weight);
  }, [profile]);

  // Portfolio pie data
  const portfolioPie = useMemo(() => {
    return positions.slice(0, 10).map((p) => ({
      name: p.symbol,
      value: Math.round(p.qty * p.avg_price),
    }));
  }, [positions]);

  // Conviction timeline (bubble chart from sells)
  const dealBubbles = useMemo(() => {
    return clientTrades.slice(-100).map((t) => ({
      date: t.sell_date?.slice(0, 10),
      price: t.sell_price || 0,
      value: Math.abs((t.sell_quantity || 0) * (t.sell_price || 0)),
      pnl: t.pnl_amount || 0,
      symbol: t.symbol,
    }));
  }, [clientTrades]);

  const PIE_COLORS = ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#f43f5e', '#ec4899', '#6366f1', '#14b8a6', '#a855f7'];

  if (loading) {
    return (
      <div className="loader-container">
        <div className="spinner" />
        <p className="loader-text">Loading whale profile...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="glass-card text-center" style={{ padding: '3rem' }}>
        <User size={48} color="var(--text-dim)" style={{ margin: '0 auto 16px' }} />
        <h2>Entity Not Found</h2>
        <p className="text-muted mt-2">No data for investor "{id}"</p>
        <button className="btn btn-ghost mt-4" onClick={() => navigate('/whales')}>
          <ArrowLeft size={16} /> Back to Scanner
        </button>
      </div>
    );
  }

  const scores = profile.ranking_scores || {};
  const dna = profile.behavioral_dna || {};
  const identity = profile.identity || {};
  const activity = profile.activity_metrics || {};

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-primary)',
        borderRadius: '8px',
        padding: '10px 14px',
        fontSize: '0.78rem',
      }}>
        <div className="font-mono mb-1">{d.date}</div>
        <div className="font-mono font-bold" style={{ color: d.pnl >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
          {formatINR(payload[0].value)}
        </div>
      </div>
    );
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 animate-in">
        <button className="btn btn-ghost btn-sm mb-4" onClick={() => navigate(-1)}>
          <ArrowLeft size={14} /> Back
        </button>
        <div className="flex items-center gap-4">
          <div style={{
            width: 52, height: 52, borderRadius: 'var(--radius-lg)',
            background: 'var(--gradient-blue)', display: 'flex',
            alignItems: 'center', justifyContent: 'center',
          }}>
            <User size={26} color="white" />
          </div>
          <div>
            <h1 className="page-title flex items-center gap-3">
              {truncateName(id, 40)}
              <DNABadge investor={profile} />
            </h1>
            <p className="page-subtitle">
              {identity.investor_type || 'UNKNOWN'} · {dna.favorite_sector || 'Unclassified'} · Active since {formatDate(identity.first_seen_date)}
            </p>
          </div>
        </div>
      </div>

      {/* Score Cards */}
      <div className="grid-4 mb-6">
        {[
          { label: 'Smart Score', value: scores.smart_money_score, color: 'var(--accent-blue)', icon: Target },
          { label: 'Conviction', value: scores.conviction_score, color: 'var(--accent-violet)', icon: Crosshair },
          { label: 'Consistency', value: scores.consistency_score, color: 'var(--accent-emerald)', icon: Activity },
          { label: 'Risk Mgmt', value: scores.risk_management_score, color: 'var(--accent-cyan)', icon: Shield },
        ].map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={s.label} className={`stat-card animate-in animate-in-delay-${i + 1}`}>
              <div className="stat-label"><Icon size={14} /> {s.label}</div>
              <div className="flex items-center gap-3">
                <ScoreRing value={s.value || 0} color={s.color} size={52} />
                <div className="stat-value font-mono" style={{ color: s.color }}>
                  {(s.value || 0).toFixed(1)}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Trading Stats + Wealth Trajectory */}
      <div className="grid-2 mb-6">
        <div className="glass-card animate-in">
          <div className="section-title"><BarChart3 size={14} /> Trading Dossier</div>
          <div className="grid-2 gap-4">
            <div>
              <div className="text-xs text-muted mb-1">First Active</div>
              <div className="font-mono">{stats?.firstTrade || identity.first_seen_date?.slice(0, 10) || '—'}</div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Last Active</div>
              <div className="font-mono">{stats?.lastTrade || identity.last_activity_date?.slice(0, 10) || '—'}</div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Realized PnL</div>
              <div className={`font-mono font-bold ${pnlColor(stats?.realized || 0)}`}>
                {formatINR(stats?.realized || 0)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Win Rate</div>
              <div className="font-mono">
                {(stats?.winRate || 0).toFixed(1)}%
                <span className="text-muted text-xs ml-2">({stats?.totalTrades || 0} exits)</span>
              </div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Entry Style</div>
              <div><span className="badge badge-blue">{dna.entry_style || 'UNKNOWN'}</span></div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Exit Style</div>
              <div><span className="badge badge-violet">{dna.exit_style || 'UNKNOWN'}</span></div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Total Buys</div>
              <div className="font-mono">{activity.total_buys || 0}</div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Active Positions</div>
              <div className="font-mono">{activity.active_positions || 0}</div>
            </div>
          </div>
        </div>

        <div className="glass-card animate-in">
          <div className="section-title"><TrendingUp size={14} /> Wealth Trajectory</div>
          <div style={{ height: 240 }}>
            {stats?.timeline?.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stats.timeline}>
                  <defs>
                    <linearGradient id="wealthGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" hide />
                  <YAxis width={70} tickFormatter={(v) => formatINR(v)} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="pnl" stroke="var(--accent-blue)" strokeWidth={2} fill="url(#wealthGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">No historical trace available.</div>
            )}
          </div>
        </div>
      </div>

      {/* Return Distribution + Portfolio Composition */}
      <div className="grid-2 mb-6">
        <div className="glass-card animate-in">
          <div className="section-title"><BarChart3 size={14} /> Trade Accuracy Distribution</div>
          <div style={{ height: 220 }}>
            {histogram.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={histogram}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis width={35} />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border-primary)',
                      borderRadius: '8px',
                      fontSize: '0.8rem',
                    }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {histogram.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={entry.name.includes('-') || entry.name.includes('< ')
                          ? 'var(--accent-rose)'
                          : 'var(--accent-emerald)'}
                        fillOpacity={0.7}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">No return data available.</div>
            )}
          </div>
        </div>

        <div className="glass-card animate-in">
          <div className="section-title"><PieIcon size={14} /> Portfolio Composition</div>
          <div style={{ height: 220 }}>
            {portfolioPie.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={portfolioPie}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                  >
                    {portfolioPie.map((_, i) => (
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
                    formatter={(v) => formatINR(v, { compact: false })}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">No active positions.</div>
            )}
          </div>
          <div className="flex flex-col gap-1 mt-2">
            {portfolioPie.slice(0, 5).map((p, i) => (
              <div key={p.name} className="flex justify-between items-center text-xs">
                <div className="flex items-center gap-2">
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: PIE_COLORS[i] }} />
                  <span className="font-mono">{p.name}</span>
                </div>
                <span className="font-mono text-muted">{formatINR(p.value)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Current Portfolio — Groww/INDMoney Style */}
      <div className="mb-6 animate-in">
        <PortfolioView portfolio={portfolio} loading={portfolioLoading} />
      </div>

      {/* Recent Executions */}
      <div className="glass-card mt-6 animate-in">
        <div className="section-title"><Activity size={14} /> Recent Exits</div>
        <div className="table-container" style={{ maxHeight: 400, overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Symbol</th>
                <th>Qty</th>
                <th>Price</th>
                <th>PnL</th>
                <th>Return %</th>
                <th>Exit Type</th>
              </tr>
            </thead>
            <tbody>
              {clientTrades.slice().reverse().slice(0, 30).map((t, i) => (
                <tr key={i}>
                  <td className="font-mono text-muted">{t.sell_date?.slice(0, 10)}</td>
                  <td className="font-mono font-bold">{t.symbol}</td>
                  <td className="font-mono">{(t.sell_quantity || 0).toLocaleString()}</td>
                  <td className="font-mono">{formatINR(t.sell_price, { compact: false })}</td>
                  <td className={`font-mono ${pnlColor(t.pnl_amount)}`}>
                    {formatINR(t.pnl_amount)}
                  </td>
                  <td className={`font-mono ${pnlColor(t.pnl_percentage)}`}>
                    {formatPct(t.pnl_percentage)}
                  </td>
                  <td><span className="badge badge-blue">{t.exit_type || '—'}</span></td>
                </tr>
              ))}
              {clientTrades.length === 0 && (
                <tr>
                  <td colSpan="7" className="text-center text-muted" style={{ padding: '2rem' }}>
                    No sell transactions found.
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
