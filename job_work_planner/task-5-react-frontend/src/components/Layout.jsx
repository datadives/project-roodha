import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { getAuthContext, logout } from '../lib/auth'

const navItems = [
  { to: '/', label: 'Dashboard (Kanban)' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/master-data', label: 'Master Data' },
  { to: '/analytics', label: 'Analytics' },
]

export default function Layout() {
  const [auth, setAuth] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    getAuthContext().then(setAuth).catch(() => setAuth(null))
  }, [])

  return (
    <div className="min-h-screen bg-[linear-gradient(160deg,rgba(255,251,235,0.9),rgba(241,245,249,0.96)_35%,rgba(239,246,255,0.9))] text-slate-900 lg:grid lg:grid-cols-[280px_1fr]">
      <aside className="relative overflow-hidden border-b border-white/60 bg-slate-950 px-5 py-6 text-slate-100 shadow-[0_24px_80px_rgba(15,23,42,0.28)] lg:min-h-screen lg:border-b-0 lg:border-r lg:px-6">
        <div className="absolute inset-x-0 top-0 h-40 bg-[radial-gradient(circle_at_top,_rgba(251,191,36,0.35),transparent_55%)]" />
        <div className="relative">
          <div className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-amber-200/80">Project Roodha</p>
            <h1 className="mt-3 text-3xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
              Command center
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              Production planning, master data, and analytics in one tenant-aware workspace.
            </p>
          </div>

          <div className="mb-6 rounded-[28px] border border-white/10 bg-white/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Session</p>
            <div className="mt-3 space-y-2 text-sm text-slate-200">
              <div>Tenant: {auth?.tenant_id || 'Loading'}</div>
              <div>Role: {auth?.user_role || 'Unknown'}</div>
            </div>
          </div>

          <nav className="space-y-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `block rounded-2xl px-4 py-3 text-sm font-medium transition ${isActive ? 'bg-white text-slate-950 shadow-[0_12px_28px_rgba(255,255,255,0.18)]' : 'text-slate-300 hover:bg-white/8 hover:text-white'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <button
            type="button"
            onClick={() =>
              logout()
                .catch(() => null)
                .finally(() => navigate('/login'))
            }
            className="mt-8 w-full rounded-2xl border border-white/12 bg-white/5 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:bg-white/10 hover:text-white"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="p-4 sm:p-6 lg:p-8">
        <Outlet />
      </main>
    </div>
  )
}
