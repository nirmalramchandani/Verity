/**
 * Verity — Utility Formatters
 * Currency, percentage, date, and number formatting for INR context
 */

/**
 * Format a number as Indian Rupees with proper locale formatting
 */
export function formatINR(value, opts = {}) {
  if (value == null || isNaN(value)) return '₹0';
  const abs = Math.abs(value);
  const { compact = true, decimals = 2 } = opts;

  if (compact) {
    if (abs >= 1e7) return `${value < 0 ? '-' : ''}₹${(abs / 1e7).toFixed(2)} Cr`;
    if (abs >= 1e5) return `${value < 0 ? '-' : ''}₹${(abs / 1e5).toFixed(2)} L`;
    if (abs >= 1e3) return `${value < 0 ? '-' : ''}₹${(abs / 1e3).toFixed(1)}K`;
  }

  return `${value < 0 ? '-' : ''}₹${abs.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

/**
 * Format percentage with sign and color hint
 */
export function formatPct(value, decimals = 2) {
  if (value == null || isNaN(value)) return '0.00%';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format a number compactly
 */
export function formatNumber(value) {
  if (value == null || isNaN(value)) return '0';
  const abs = Math.abs(value);
  if (abs >= 1e7) return `${(value / 1e7).toFixed(2)}Cr`;
  if (abs >= 1e5) return `${(value / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toLocaleString('en-IN');
}

/**
 * Format date string to readable format
 */
export function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Format date to short form
 */
export function formatDateShort(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: '2-digit',
  });
}

/**
 * Get color class based on value sign
 */
export function pnlColor(value) {
  if (value > 0) return 'text-glow-success';
  if (value < 0) return 'text-glow-danger';
  return 'text-muted';
}

/**
 * Get CSS variable color for charts based on value
 */
export function pnlCSSColor(value) {
  if (value > 0) return 'var(--accent-emerald)';
  if (value < 0) return 'var(--accent-rose)';
  return 'var(--text-muted)';
}

/**
 * Truncate investor name to readable form
 */
export function truncateName(name, maxLen = 30) {
  if (!name) return 'Unknown';
  if (name.length <= maxLen) return name;
  return name.slice(0, maxLen) + '…';
}

/**
 * Get archetype info from behavioral DNA
 */
export function getArchetype(investorData) {
  if (!investorData) return { label: 'Unknown', color: 'dim', icon: '?' };
  
  const dna = investorData.behavioral_dna || {};
  const identity = investorData.identity || {};
  const type = identity.investor_type;
  const avgHold = investorData.activity_metrics?.avg_hold_days || 0;
  const dipScore = dna.dip_buying_score || 0;
  const trendScore = dna.trend_following_score || 0;
  
  if (type === 'OPERATOR') return { label: 'Operator', color: 'rose', icon: '⚡' };
  if (type === 'LARGE_INVESTOR' && avgHold > 365) return { label: 'Accumulator', color: 'emerald', icon: '🏛' };
  if (type === 'LARGE_INVESTOR') return { label: 'Institution', color: 'blue', icon: '🐋' };
  if (trendScore > 0.6) return { label: 'Momentum', color: 'amber', icon: '🚀' };
  if (dipScore > 0.6) return { label: 'Value Hunter', color: 'violet', icon: '🎯' };
  if (type === 'MID_INVESTOR') return { label: 'Mid-Tier', color: 'blue', icon: '📊' };
  if (type === 'SMALL_INVESTOR') return { label: 'Retail', color: 'dim', icon: '👤' };
  return { label: 'Mixed', color: 'dim', icon: '📋' };
}

/**
 * Calculate holding period in human readable form
 */
export function formatHoldPeriod(days) {
  if (!days || days <= 0) return '< 1 day';
  if (days < 30) return `${days}d`;
  if (days < 365) return `${Math.round(days / 30)}mo`;
  const years = Math.floor(days / 365);
  const months = Math.round((days % 365) / 30);
  return months > 0 ? `${years}y ${months}mo` : `${years}y`;
}
