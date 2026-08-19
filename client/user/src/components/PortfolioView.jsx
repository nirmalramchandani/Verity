/**
 * PortfolioView — Groww/INDMoney-style holdings view
 * Shows current portfolio holdings with lot-level drill-down
 */
import { useState } from 'react';
import { formatINR, formatHoldPeriod } from '../utils/formatters';
import { getStockName } from '../utils/stockMap';
import {
  ChevronDown, ChevronUp, Briefcase, Clock, Layers,
  TrendingUp, Package, CalendarDays, IndianRupee,
} from 'lucide-react';

function HoldingCard({ holding }) {
  const [expanded, setExpanded] = useState(false);

  const weightColor =
    holding.position_weight > 20
      ? 'var(--accent-amber)'
      : holding.position_weight > 10
      ? 'var(--accent-blue)'
      : 'var(--text-secondary)';

  return (
    <div className="holding-card">
      {/* Main Row */}
      <div
        className="holding-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="holding-left">
          <div className="holding-symbol-wrap">
            <div className="holding-symbol-icon">
              {holding.symbol?.slice(0, 2)}
            </div>
            <div>
              <div className="holding-symbol">{holding.symbol}</div>
              <div className="holding-name">{getStockName(holding.symbol)}</div>
            </div>
          </div>
        </div>

        <div className="holding-metrics">
          <div className="holding-metric">
            <span className="holding-metric-label">Qty</span>
            <span className="holding-metric-value mono">
              {holding.total_qty?.toLocaleString()}
            </span>
          </div>
          <div className="holding-metric">
            <span className="holding-metric-label">Avg Cost</span>
            <span className="holding-metric-value mono">
              ₹{holding.avg_price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="holding-metric">
            <span className="holding-metric-label">Invested</span>
            <span className="holding-metric-value mono">
              {formatINR(holding.invested_value)}
            </span>
          </div>
          <div className="holding-metric">
            <span className="holding-metric-label">Weight</span>
            <span className="holding-metric-value mono" style={{ color: weightColor }}>
              {holding.position_weight?.toFixed(1)}%
            </span>
          </div>
          <div className="holding-metric">
            <span className="holding-metric-label">Holding</span>
            <span className="holding-metric-value mono">
              {formatHoldPeriod(holding.holding_days)}
            </span>
          </div>
          <div className="holding-metric">
            <span className="holding-metric-label">Lots</span>
            <span className="holding-metric-value">
              <span className="badge badge-dim">{holding.num_lots}</span>
            </span>
          </div>
        </div>

        <div className="holding-expand">
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {/* Expanded Lot Breakdown */}
      {expanded && holding.lots?.length > 0 && (
        <div className="holding-lots">
          <div className="lots-header">
            <span>Buy Date</span>
            <span>Qty</span>
            <span>Buy Price</span>
            <span>Invested</span>
            <span>Held For</span>
          </div>
          {holding.lots.map((lot, i) => (
            <div key={i} className="lot-row">
              <span className="mono text-muted">
                <CalendarDays size={12} style={{ marginRight: 4, opacity: 0.5 }} />
                {lot.buy_date || '—'}
              </span>
              <span className="mono">{lot.qty?.toLocaleString()}</span>
              <span className="mono">
                ₹{lot.price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
              <span className="mono">{formatINR(lot.invested)}</span>
              <span className="mono" style={{ color: lot.holding_days > 365 ? 'var(--accent-emerald)' : 'var(--text-secondary)' }}>
                {formatHoldPeriod(lot.holding_days)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PortfolioView({ portfolio, loading }) {
  if (loading) {
    return (
      <div className="glass-card">
        <div className="section-title"><Briefcase size={14} /> Current Portfolio</div>
        <div className="loader-container" style={{ minHeight: 200 }}>
          <div className="spinner" />
          <p className="loader-text">Loading portfolio holdings...</p>
        </div>
      </div>
    );
  }

  if (!portfolio || !portfolio.holdings?.length) {
    return (
      <div className="glass-card">
        <div className="section-title"><Briefcase size={14} /> Current Portfolio</div>
        <div className="empty-state">
          <Package size={36} />
          <p>No active holdings found for this investor.</p>
        </div>
      </div>
    );
  }

  const { holdings, total_invested, num_holdings } = portfolio;

  return (
    <div className="glass-card portfolio-container">
      <div className="section-title"><Briefcase size={14} /> Current Portfolio</div>

      {/* Portfolio Summary Bar */}
      <div className="portfolio-summary">
        <div className="portfolio-summary-item">
          <IndianRupee size={14} color="var(--accent-blue)" />
          <div>
            <div className="portfolio-summary-label">Total Invested</div>
            <div className="portfolio-summary-value mono">{formatINR(total_invested)}</div>
          </div>
        </div>
        <div className="portfolio-summary-item">
          <Layers size={14} color="var(--accent-violet)" />
          <div>
            <div className="portfolio-summary-label">Holdings</div>
            <div className="portfolio-summary-value mono">{num_holdings} stocks</div>
          </div>
        </div>
        <div className="portfolio-summary-item">
          <TrendingUp size={14} color="var(--accent-emerald)" />
          <div>
            <div className="portfolio-summary-label">Top Holding</div>
            <div className="portfolio-summary-value mono">
              {holdings[0]?.symbol} ({holdings[0]?.position_weight?.toFixed(1)}%)
            </div>
          </div>
        </div>
        <div className="portfolio-summary-item">
          <Clock size={14} color="var(--accent-amber)" />
          <div>
            <div className="portfolio-summary-label">Longest Held</div>
            <div className="portfolio-summary-value mono">
              {formatHoldPeriod(Math.max(...holdings.map(h => h.holding_days || 0)))}
            </div>
          </div>
        </div>
      </div>

      {/* Holdings List */}
      <div className="holdings-list">
        {holdings.map((h) => (
          <HoldingCard key={h.symbol} holding={h} />
        ))}
      </div>
    </div>
  );
}
