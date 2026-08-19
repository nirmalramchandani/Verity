import { NavLink, useLocation } from 'react-router-dom';
import {
  Home,
  LayoutDashboard,
  Users,
  Activity,
  BarChart3,
  Radar,
  Zap,
} from 'lucide-react';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: Home },
  { path: '/dashboard', label: 'Market Dashboard', icon: LayoutDashboard },
  { path: '/whales', label: 'Institutional Directory', icon: Users },
  { path: '/alpha', label: 'Deal Analytics Ledger', icon: BarChart3 },
  { path: '/herd', label: 'Co-Investment Radar', icon: Radar },
  { path: '/activity', label: 'Market Feed', icon: Activity },
  { path: '/signals', label: 'Quantitative Signals', icon: Zap },
];

export default function Sidebar({ isOpen, onClose }) {
  const location = useLocation();

  return (
    <>
      <div className={`mobile-overlay ${isOpen ? 'open' : ''}`} onClick={onClose} />
      <aside className={`sidebar ${isOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-brand">
          <h1>VERITY</h1>
          <div className="brand-sub">Institutional Research Terminal</div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path);

            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={() => {
                  if (window.innerWidth <= 900) onClose();
                }}
              >
                <Icon className="nav-icon" size={18} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>


      <div className="sidebar-footer">
        <div className="flex items-center gap-2">
          <span className="status-dot" />
          <span className="text-xs text-muted">Data Pipeline Active</span>
        </div>
        <div className="text-xs text-muted mt-2 font-mono" style={{ opacity: 0.5 }}>
          v2.0 — NSE Bulk & Block
        </div>
      </div>
      </aside>
    </>
  );
}
