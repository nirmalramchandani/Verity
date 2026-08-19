import { NavLink, useLocation } from 'react-router-dom';

export default function Sidebar() {
  const location = useLocation();

  const adminLinks = [
    { to: '/pipeline', icon: '⚙️', label: 'Pipeline Control' },
    { to: '/dashboard', icon: '📊', label: 'Analytics Dashboard' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>VERITY</h1>
        <div className="subtitle">Institutional Data Intelligence</div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title">Admin Panel</div>
        <nav className="sidebar-nav">
          {adminLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `sidebar-link${isActive ? ' active' : ''}`
              }
            >
              <span className="icon">{link.icon}</span>
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>



      <div className="sidebar-footer">
        <div className="caption">Verity v1.0 — Internal</div>
      </div>
    </aside>
  );
}
