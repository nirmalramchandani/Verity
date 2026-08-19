/**
 * Alpha Table — Stock-level analysis across all whale activity
 * Shows every stock ever touched by whales with aggregate metrics
 */
import { useMemo, useState } from 'react';
import { useWhaleData } from '../hooks/useWhaleData';
import { formatINR, formatPct, pnlColor, truncateName } from '../utils/formatters';
import { getStockName } from '../utils/stockMap';
import { BarChart3, Search, TrendingUp, ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react';

const PAGE_SIZE = 30;

export default function AlphaTable() {
  const { investors, sells, loading } = useWhaleData();
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState('totalPnl');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(0);

  // Aggregate by symbol from sells
  const stockData = useMemo(() => {
    if (!sells.length) return [];
    const map = {};

    for (const s of sells) {
      const sym = s.symbol;
      if (!sym) continue;
      if (!map[sym]) {
        map[sym] = {
          symbol: sym,
          name: getStockName(sym),
          totalPnl: 0,
          totalDeals: 0,
          wins: 0,
          totalValue: 0,
          investors: new Set(),
          avgReturn: [],
          firstDate: s.sell_date,
          lastDate: s.sell_date,
        };
      }
      map[sym].totalPnl += s.pnl_amount || 0;
      map[sym].totalDeals += 1;
      if (s.pnl_amount > 0) map[sym].wins += 1;
      map[sym].totalValue += Math.abs((s.sell_quantity || 0) * (s.sell_price || 0));
      map[sym].investors.add(s.client_id);
      map[sym].avgReturn.push(s.pnl_percentage || 0);
      if (s.sell_date < map[sym].firstDate) map[sym].firstDate = s.sell_date;
      if (s.sell_date > map[sym].lastDate) map[sym].lastDate = s.sell_date;
    }

    return Object.values(map).map((s) => ({
      ...s,
      investorCount: s.investors.size,
      winRate: s.totalDeals > 0 ? (s.wins / s.totalDeals) * 100 : 0,
      avgReturnPct: s.avgReturn.length > 0
        ? s.avgReturn.reduce((a, b) => a + b, 0) / s.avgReturn.length
        : 0,
      investors: undefined,
      avgReturn: undefined,
    }));
  }, [sells]);

  // Filter + Sort
  const filtered = useMemo(() => {
    let list = [...stockData];
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (s) => s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => {
      const av = a[sortKey] || 0;
      const bv = b[sortKey] || 0;
      return sortDir === 'desc' ? bv - av : av - bv;
    });
    return list;
  }, [stockData, search, sortKey, sortDir]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    else { setSortKey(key); setSortDir('desc'); }
    setPage(0);
  };

  if (loading) {
    return (
      <div className="loader-container">
        <div className="spinner" />
        <p className="loader-text">Building alpha matrix...</p>
      </div>
    );
  }

  const SortHeader = ({ label, field }) => (
    <th className="cursor-pointer" onClick={() => handleSort(field)}>
      <div className="flex items-center gap-1">
        {label}
        {sortKey === field && (
          <ArrowUpDown size={12} style={{ opacity: 0.7 }} />
        )}
      </div>
    </th>
  );

  return (
    <div>
      <div className="flex justify-between items-center mb-6 animate-in">
        <div>
          <h1 className="page-title">Alpha Table</h1>
          <p className="page-subtitle">
            {filtered.length.toLocaleString()} stocks — Aggregate performance across all whale activity
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="glass-card mb-6 animate-in animate-in-delay-1">
        <div className="flex items-center gap-2">
          <Search size={16} color="var(--text-muted)" />
          <input
            className="input-field"
            placeholder="Search by symbol or stock name..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="glass-card animate-in animate-in-delay-2">
        <div className="table-container" style={{ maxHeight: 650, overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Symbol</th>
                <th>Stock Name</th>
                <SortHeader label="Total PnL" field="totalPnl" />
                <SortHeader label="Deals" field="totalDeals" />
                <SortHeader label="Win Rate" field="winRate" />
                <SortHeader label="Avg Return" field="avgReturnPct" />
                <SortHeader label="Deal Value" field="totalValue" />
                <SortHeader label="Whale Count" field="investorCount" />
                <th>Period</th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((s, idx) => (
                <tr key={s.symbol}>
                  <td className="text-muted font-mono">{page * PAGE_SIZE + idx + 1}</td>
                  <td className="font-mono font-bold">{s.symbol}</td>
                  <td className="text-secondary">{truncateName(s.name, 25)}</td>
                  <td className={`font-mono ${pnlColor(s.totalPnl)}`}>{formatINR(s.totalPnl)}</td>
                  <td className="font-mono">{s.totalDeals}</td>
                  <td className="font-mono" style={{ color: s.winRate >= 50 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                    {s.winRate.toFixed(1)}%
                  </td>
                  <td className={`font-mono ${pnlColor(s.avgReturnPct)}`}>
                    {formatPct(s.avgReturnPct)}
                  </td>
                  <td className="font-mono">{formatINR(s.totalValue)}</td>
                  <td>
                    <span className="badge badge-blue">{s.investorCount}</span>
                  </td>
                  <td className="font-mono text-xs text-muted">
                    {s.firstDate?.slice(0, 10)} → {s.lastDate?.slice(0, 10)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex justify-between items-center mt-4">
            <span className="text-xs text-muted">
              Page {page + 1} of {totalPages}
            </span>
            <div className="flex gap-2">
              <button className="btn btn-ghost btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
                <ChevronLeft size={14} /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
