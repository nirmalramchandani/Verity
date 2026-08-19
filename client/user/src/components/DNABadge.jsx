/**
 * DNA Badge — Visual archetype indicator for investor profiles
 */
import { getArchetype } from '../utils/formatters';

const COLOR_MAP = {
  blue: { bg: 'var(--accent-blue-dim)', border: 'rgba(59,130,246,0.3)', text: 'var(--accent-blue)' },
  emerald: { bg: 'var(--accent-emerald-dim)', border: 'rgba(16,185,129,0.3)', text: 'var(--accent-emerald)' },
  rose: { bg: 'var(--accent-rose-dim)', border: 'rgba(244,63,94,0.3)', text: 'var(--accent-rose)' },
  amber: { bg: 'var(--accent-amber-dim)', border: 'rgba(245,158,11,0.3)', text: 'var(--accent-amber)' },
  violet: { bg: 'var(--accent-violet-dim)', border: 'rgba(139,92,246,0.3)', text: 'var(--accent-violet)' },
  dim: { bg: 'rgba(100,116,139,0.12)', border: 'rgba(100,116,139,0.2)', text: 'var(--text-muted)' },
};

export default function DNABadge({ investor, size = 'normal' }) {
  const arch = getArchetype(investor);
  const colors = COLOR_MAP[arch.color] || COLOR_MAP.dim;

  const style = {
    background: colors.bg,
    borderColor: colors.border,
    color: colors.text,
    fontSize: size === 'small' ? '0.65rem' : '0.72rem',
    padding: size === 'small' ? '2px 8px' : '4px 12px',
  };

  return (
    <span className="dna-badge" style={style}>
      <span>{arch.icon}</span>
      {arch.label}
    </span>
  );
}
