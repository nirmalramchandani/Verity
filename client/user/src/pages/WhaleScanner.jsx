import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWhaleData } from '../hooks/useWhaleData';
import { formatINR, truncateName, getArchetype } from '../utils/formatters';
import DNABadge from '../components/DNABadge';
import ScoreRing from '../components/ScoreRing';
import { Search, SlidersHorizontal, ArrowUpRight, Users, ChevronLeft, ChevronRight } from 'lucide-react';

const TYPE_FILTERS = ['ALL', 'LARGE_INVESTOR', 'MID_INVESTOR', 'SMALL_INVESTOR', 'OPERATOR'];
const SORT_OPTIONS = [
  { label: 'Smart Score', key: 'smart_money_score' },
  { label: 'Conviction', key: 'conviction_score' },
  { label: 'Consistency', key: 'consistency_score' },
  { label: 'Risk Mgmt', key: 'risk_management_score' },
];

const PAGE_SIZE = 25;

export default function WhaleScanner() {
  const { investors, loading, error } = useWhaleData();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [sortBy, setSortBy] = useState('smart_money_score');
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    let list = [...investors];

    // Search
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((inv) =>
        inv._id?.toLowerCase().includes(q) ||
        inv.behavioral_dna?.favorite_sector?.toLowerCase().includes(q)
      );
    }

    // Type filter
    if (typeFilter !== 'ALL') {
      list = list.filter((inv) => inv.identity?.investor_type === typeFilter);
    }

    // Sort
    list.sort((a, b) => {
      const av = a.ranking_scores?.[sortBy] || 0;
      const bv = b.ranking_scores?.[sortBy] || 0;
      return bv - av;
    });

    return list;
  }, [investors, search, typeFilter, sortBy]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  if (loading) {
    return (
      <div className="loader-container">
        <div className="spinner" />
        <p className="loader-text">Loading institutional database...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6 animate-in">
        <div>
          <h1 className="page-title">Institutional Directory</h1>
          <p className="page-subtitle">
            {filtered.length.toLocaleString()} entities — Filter, rank, and profile market participants
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="glass-card mb-6 animate-in animate-in-delay-1">
        <div className="flex items-center gap-4" style={{ flexWrap: 'wrap' }}>
          <div className="flex items-center gap-2" style={{ flex: '1 1 300px' }}>
            <Search size={16} color="var(--text-muted)" />
            <input
              className="input-field"
              placeholder="Search by investor name or sector..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            />
          </div>

          <div className="flex items-center gap-2">
            <SlidersHorizontal size={14} color="var(--text-muted)" />
            {TYPE_FILTERS.map((t) => (
              <button
                key={t}
                className={`filter-chip ${typeFilter === t ? 'active' : ''}`}
                onClick={() => { setTypeFilter(t); setPage(0); }}
              >
                {t === 'ALL' ? 'All' : t.replace('_', ' ')}
              </button>
            ))}
          </div>

          <select
            className="select-field"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>Sort: {o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Investor Grid */}
      <div className="glass-card animate-in animate-in-delay-2">
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Investor</th>
                <th>Archetype</th>
                <th>Smart Score</th>
                <th>Conviction</th>
                <th>Consistency</th>
                <th>Risk Mgmt</th>
                <th>Sector Focus</th>
                <th>Positions</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((inv, idx) => {
                const scores = inv.ranking_scores || {};
                return (
                  <tr key={inv._id} className="cursor-pointer" onClick={() => navigate(`/whale/${inv._id}`)}>
                    <td className="text-muted font-mono">{page * PAGE_SIZE + idx + 1}</td>
                    <td>
                      <div className="font-mono text-sm" style={{ maxWidth: 250 }}>
                        {truncateName(inv._id, 32)}
                      </div>
                    </td>
                    <td><DNABadge investor={inv} size="small" /></td>
                    <td>
                      <span className="font-mono font-bold text-info">
                        {(scores.smart_money_score || 0).toFixed(1)}
                      </span>
                    </td>
                    <td className="font-mono">{(scores.conviction_score || 0).toFixed(1)}</td>
                    <td className="font-mono">{(scores.consistency_score || 0).toFixed(1)}</td>
                    <td className="font-mono">{(scores.risk_management_score || 0).toFixed(1)}</td>
                    <td>
                      <span className="badge badge-dim">
                        {inv.behavioral_dna?.favorite_sector || '—'}
                      </span>
                    </td>
                    <td className="font-mono">{inv.activity_metrics?.active_positions || 0}</td>
                    <td className="text-right">
                      <ArrowUpRight size={16} color="var(--accent-blue)" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex justify-between items-center mt-4">
            <span className="text-xs text-muted">
              Page {page + 1} of {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                className="btn btn-ghost btn-sm"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                <ChevronLeft size={14} /> Prev
              </button>
              <button
                className="btn btn-ghost btn-sm"
                disabled={page >= totalPages - 1}
                onClick={() => setPage(page + 1)}
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
