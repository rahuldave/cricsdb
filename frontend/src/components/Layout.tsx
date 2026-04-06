import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import FilterBar from './FilterBar'

const navItems = [
  { to: '/teams', label: 'Teams' },
  { to: '/batting', label: 'Batting' },
  { to: '/bowling', label: 'Bowling' },
  { to: '/head-to-head', label: 'Head to Head' },
  { to: '/matches', label: 'Matches' },
]

export default function Layout() {
  const { pathname } = useLocation()
  // Hide FilterBar on pages where global filters are meaningless:
  // home (static landing) and the dedicated scorecard for one match.
  const showFilters = pathname !== '/' && !/^\/matches\/[^/]+$/.test(pathname)

  const [mobileOpen, setMobileOpen] = useState(false)
  // Close the mobile menu on navigation
  useEffect(() => { setMobileOpen(false) }, [pathname])

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
    }`

  return (
    <div className="min-h-screen">
      <nav className="bg-gray-900 text-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between h-14">
            <NavLink
              to="/"
              className="font-bold text-lg text-white hover:text-gray-200 whitespace-nowrap"
            >
              {/* Short brand on mobile, full brand on sm and up */}
              <span className="sm:hidden">CricsDB</span>
              <span className="hidden sm:inline">T20 CricsDB</span>
            </NavLink>

            {/* Desktop nav: shown md and up */}
            <div className="hidden md:flex gap-1">
              {navItems.map(item => (
                <NavLink key={item.to} to={item.to} className={linkClass}>{item.label}</NavLink>
              ))}
            </div>

            {/* Mobile hamburger: shown below md */}
            <button
              type="button"
              aria-label="Toggle navigation menu"
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen(o => !o)}
              className="md:hidden inline-flex items-center justify-center p-2 rounded-md text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              {mobileOpen ? (
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              ) : (
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
              )}
            </button>
          </div>

          {/* Mobile drawer: stacked links, only when open and below md */}
          {mobileOpen && (
            <div className="md:hidden pb-3 flex flex-col gap-1 border-t border-gray-800 pt-3">
              {navItems.map(item => (
                <NavLink key={item.to} to={item.to} className={linkClass}>{item.label}</NavLink>
              ))}
            </div>
          )}
        </div>
      </nav>
      {showFilters && <FilterBar />}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
