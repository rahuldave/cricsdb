import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import FilterBar from './FilterBar'

const navItems = [
  { to: '/tournaments', label: 'Tournaments' },
  { to: '/teams', label: 'Teams' },
  { to: '/batting', label: 'Batting' },
  { to: '/bowling', label: 'Bowling' },
  { to: '/fielding', label: 'Fielding' },
  { to: '/head-to-head', label: 'Head to Head' },
  { to: '/matches', label: 'Matches' },
]

export default function Layout() {
  const { pathname } = useLocation()
  // Hide FilterBar on pages where global filters are meaningless:
  // home (static landing), the dedicated scorecard for one match,
  // and the /help pages.
  const showFilters = pathname !== '/'
    && !/^\/matches\/[^/]+$/.test(pathname)
    && !pathname.startsWith('/help')

  const [mobileOpen, setMobileOpen] = useState(false)
  useEffect(() => { setMobileOpen(false) }, [pathname])

  return (
    <div className="min-h-screen">
      <nav className="wisden-nav">
        <div className="wisden-nav-inner">
          <NavLink to="/" className="wisden-wordmark">
            T20 <span className="wisden-amp">&amp;</span> CricsDB
          </NavLink>

          {/* Desktop nav: shown md and up */}
          <div className="wisden-nav-links">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `wisden-nav-link${isActive ? ' is-active' : ''}`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <NavLink
              to="/help"
              className={({ isActive }) =>
                `wisden-nav-help${isActive ? ' is-active' : ''}`
              }
              aria-label="About this site & help"
              title="About this site & help"
            >
              ?
            </NavLink>
          </div>

          {/* Mobile hamburger */}
          <button
            type="button"
            aria-label="Toggle navigation menu"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(o => !o)}
            className="wisden-hamburger"
          >
            {mobileOpen ? (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            ) : (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            )}
          </button>
        </div>

        {mobileOpen && (
          <div className="wisden-nav-mobile">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `wisden-nav-link${isActive ? ' is-active' : ''}`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <NavLink
              to="/help"
              className={({ isActive }) =>
                `wisden-nav-link${isActive ? ' is-active' : ''}`
              }
            >
              About &amp; Help
            </NavLink>
          </div>
        )}
      </nav>
      {showFilters && <FilterBar />}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
