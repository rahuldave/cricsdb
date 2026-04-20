import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import FilterBar from './FilterBar'
import ScopeStatusStrip from './ScopeStatusStrip'

interface NavChild { to: string; label: string }
interface NavItem {
  to: string
  label: string
  /** When set, this nav item hosts a desktop hover-dropdown of sub-
   *  routes, AND a mobile sub-row that appears when the current route
   *  is the parent OR any of its children. */
  children?: NavChild[]
}

const navItems: NavItem[] = [
  { to: '/series', label: 'Series' },
  { to: '/teams', label: 'Teams' },
  { to: '/players', label: 'Players', children: [
    { to: '/batting',  label: 'Batting'  },
    { to: '/bowling',  label: 'Bowling'  },
    { to: '/fielding', label: 'Fielding' },
  ]},
  { to: '/head-to-head', label: 'Head to Head' },
  { to: '/venues', label: 'Venues' },
  { to: '/matches', label: 'Matches' },
]

function isInGroup(pathname: string, item: NavItem): boolean {
  if (pathname === item.to) return true
  if (!item.children) return false
  return item.children.some(c => pathname === c.to)
}

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

  // The Players group exposes a persistent mobile sub-row of
  // Batting / Bowling / Fielding so those three are always one tap
  // away from each other (and from the Players overview).
  const playersGroup = navItems.find(i => i.to === '/players')
  const showPlayersSubrow = !!playersGroup && isInGroup(pathname, playersGroup)

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
              item.children
                ? <DesktopGroupLink key={item.to} item={item} pathname={pathname} />
                : <NavLink
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
              <div key={item.to}>
                <NavLink
                  to={item.to}
                  end={!item.children}
                  className={({ isActive }) =>
                    // For grouped items (Players), highlight the parent
                    // also when any child route is active.
                    `wisden-nav-link${
                      (isActive || (item.children && isInGroup(pathname, item)))
                        ? ' is-active' : ''
                    }`
                  }
                >
                  {item.label}{item.children ? ' ▾' : ''}
                </NavLink>
                {item.children && (
                  <div className="wisden-nav-mobile-children">
                    {item.children.map(c => (
                      <NavLink
                        key={c.to}
                        to={c.to}
                        className={({ isActive }) =>
                          `wisden-nav-link${isActive ? ' is-active' : ''}`
                        }
                      >
                        {c.label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
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

        {/* Mobile sub-row: persistent secondary nav while the user is
            in the Players group, so all four entries (Players overview
            + Batting / Bowling / Fielding) are one tap from each other.
            Hidden on desktop — the hover dropdown serves the same
            purpose there. */}
        {showPlayersSubrow && playersGroup?.children && (
          <div className="wisden-nav-subrow">
            <NavLink
              to={playersGroup.to}
              end
              className={({ isActive }) =>
                `wisden-nav-sublink${isActive ? ' is-active' : ''}`
              }
            >
              {playersGroup.label}
            </NavLink>
            {playersGroup.children.map(c => (
              <NavLink
                key={c.to}
                to={c.to}
                className={({ isActive }) =>
                  `wisden-nav-sublink${isActive ? ' is-active' : ''}`
                }
              >
                {c.label}
              </NavLink>
            ))}
          </div>
        )}
      </nav>
      {showFilters && <FilterBar />}
      {showFilters && <ScopeStatusStrip />}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

// ─── Desktop dropdown ───────────────────────────────────────────────

interface DesktopGroupLinkProps { item: NavItem; pathname: string }

function DesktopGroupLink({ item, pathname }: DesktopGroupLinkProps) {
  const active = isInGroup(pathname, item)
  return (
    <div className="wisden-nav-group">
      <NavLink
        to={item.to}
        end
        className={() => `wisden-nav-link${active ? ' is-active' : ''}`}
      >
        {item.label} <span aria-hidden="true" className="wisden-nav-caret">▾</span>
      </NavLink>
      {item.children && (
        <ul className="wisden-nav-dropdown">
          {item.children.map(c => (
            <li key={c.to}>
              <NavLink
                to={c.to}
                className={({ isActive }) =>
                  `wisden-nav-dropdown-link${isActive ? ' is-active' : ''}`
                }
              >
                {c.label}
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
