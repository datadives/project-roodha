import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard (Kanban)' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/master-data', label: 'Master Data' },
  { to: '/analytics', label: 'Analytics' },
]

export default function Layout() {
  return (
    <div className="min-h-screen grid grid-cols-[260px_1fr]">
      <aside className="bg-slate-900 text-slate-100 p-4">
        <h1 className="text-xl font-bold mb-6">JobWork Planner</h1>
        <nav className="space-y-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${isActive ? 'bg-indigo-600' : 'hover:bg-slate-800'}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  )
}
