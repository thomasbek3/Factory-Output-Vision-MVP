import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/dashboard', label: 'Operations Dashboard' },
  { to: '/wizard', label: 'Setup Wizard' },
  { to: '/troubleshooting', label: 'Troubleshooting' },
]

export function AppFrame() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-bar">
          <div className="brand-copy">
            <div className="eyebrow">Phase 7 React Cutover</div>
            <div className="brand-title">Factory Counter Control UI</div>
            <div className="brand-subtitle">
              React is now the only UI surface. FastAPI still owns runtime, state, and all control APIs.
            </div>
          </div>
        </div>
        <nav aria-label="Primary" className="nav-bar">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              to={item.to}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <Outlet />
    </div>
  )
}
