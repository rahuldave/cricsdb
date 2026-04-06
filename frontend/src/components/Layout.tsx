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
  const showFilters = pathname !== '/'
  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-gray-900 text-white">
        <div className="max-w-7xl mx-auto px-4 flex items-center h-14">
          <NavLink to="/" className="font-bold text-lg mr-8 text-white hover:text-gray-200">T20 CricsDB</NavLink>
          <div className="flex gap-1">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  }`
                }
              >{item.label}</NavLink>
            ))}
          </div>
        </div>
      </nav>
      {showFilters && <FilterBar />}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
