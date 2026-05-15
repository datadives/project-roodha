/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: Layout.jsx
 * 
 * 1) Purpose: React component for rendering Layout UI elements.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import React, { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, useOutletContext } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { fetchNotifications } from '../lib/notificationsApi'
import { getRoleLabel, hasAnyRole, hasPermission } from '../lib/roles'
import LayoutDashboard from 'lucide-react/dist/esm/icons/layout-dashboard.js'
import Briefcase from 'lucide-react/dist/esm/icons/briefcase.js'
import Database from 'lucide-react/dist/esm/icons/database.js'
import BarChart3 from 'lucide-react/dist/esm/icons/chart-bar-big.js'
import Bell from 'lucide-react/dist/esm/icons/bell.js'
import LogOut from 'lucide-react/dist/esm/icons/log-out.js'
import Users from 'lucide-react/dist/esm/icons/users.js'

const navItems = [
  { to: '/dashboard', label: 'Board', permission: 'dashboard', allowedRoles: ['OWNER', 'SUPERVISOR'], icon: LayoutDashboard },
  { to: '/operator', label: 'Operator Kanban', permission: 'operatorDashboard', allowedRoles: ['OPERATOR'], icon: LayoutDashboard },
  { to: '/jobs', label: 'Jobs', permission: 'jobs', icon: Briefcase },
  { to: '/master-data', label: 'Master', permission: 'masterData', icon: Database },
  { to: '/analytics', label: 'Analytics', permission: 'analytics', icon: BarChart3 },
  { to: '/users', label: 'Users', permission: 'userManagement', icon: Users },
  { to: '/notifications', label: 'Alerts', permission: 'notifications', showUnreadBadge: true, icon: Bell },
]

function getMissingSessionFields(auth) {
  const missing = []
  if (!auth?.isAuthenticated) missing.push('isAuthenticated')
  if (!auth?.token) missing.push('token')
  if (!auth?.tenantId) missing.push('tenantId')
  if (!auth?.userRole) missing.push('userRole')
  return missing
}

export default function Layout() {
  const outletAuth = useOutletContext()
  const { auth: contextAuth, role, logout } = useAuth()
  const auth = contextAuth || outletAuth
  const [unreadCount, setUnreadCount] = useState(0)
  const navigate = useNavigate()
  const missingSessionFields = getMissingSessionFields(auth)
  const resolvedRole = role || auth?.userRole || auth?.role
  const visibleNavItems = navItems.filter((item) => (
    item.allowedRoles
      ? hasAnyRole(resolvedRole, item.allowedRoles)
      : hasPermission(resolvedRole, item.permission)
  ))

  useEffect(() => {
    if (missingSessionFields.length > 0) {
      setUnreadCount(0)
      return undefined
    }

    async function loadUnreadCount() {
      try {
        const response = await fetchNotifications()
        setUnreadCount(response.unread_count || 0)
      } catch {
        setUnreadCount(0)
      }
    }

    loadUnreadCount()

    function handleRefresh() {
      loadUnreadCount()
    }

    window.addEventListener('notifications:refresh', handleRefresh)
    return () => window.removeEventListener('notifications:refresh', handleRefresh)
  }, [missingSessionFields.length])

  if (missingSessionFields.length > 0) {
    return (
      <div className="min-h-screen bg-slate-950 p-6 text-slate-100 font-mono">
        <div className="mx-auto max-w-2xl rounded-[1.5rem] border border-orange-500/30 bg-slate-900 p-8 shadow-2xl">
          <p className="text-xs font-black uppercase tracking-[0.3em] text-orange-400">System State: Error</p>
          <h1 className="mt-4 text-3xl font-black text-white">INCOMPLETE SESSION</h1>
          <p className="mt-4 text-sm leading-relaxed text-slate-400">
            Critical authentication headers are missing from the current context: {missingSessionFields.join(', ')}.
          </p>
          <button
            type="button"
            onClick={() =>
              logout()
                .catch(() => null)
                .finally(() => navigate('/login'))
            }
            className="mt-8 touch-target w-full rounded-xl bg-orange-500 text-sm font-black uppercase tracking-widest text-[#0F172A] transition hover:bg-orange-400 shadow-[0_0_20px_-5px_rgba(249,115,22,0.4)]"
          >
            Re-authenticate
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#0F172A] text-slate-100 lg:grid lg:grid-cols-[260px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)]">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex flex-col border-r border-slate-800 bg-slate-900/50 p-6 min-h-screen sticky top-0">
        <div className="mb-10 min-w-0">
          <div className="flex items-center gap-2">
            <div className="h-6 w-2 bg-orange-500 rounded-full" />
            <p className="text-xs font-black uppercase tracking-[0.4em] text-orange-500/80">Roodha Industrial</p>
          </div>
          <h1 className="mt-4 text-2xl font-black tracking-normal text-white xl:text-3xl">COMMAND</h1>
          <p className="mt-2 text-[11px] font-bold uppercase tracking-widest text-slate-500 leading-tight">
            Production & Resource Monitoring
          </p>
        </div>

        <div className="mb-8 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-600">Active Tenant</p>
          <div className="mt-2 font-mono text-sm font-bold text-orange-200/90 truncate">
            {auth?.tenantId || '--'}
          </div>
          <div className="mt-1 text-[10px] font-bold text-slate-500 uppercase">
            {getRoleLabel(resolvedRole)}
          </div>
        </div>

        <nav className="flex-1 space-y-1.5">
          {visibleNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex min-w-0 items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold uppercase tracking-normal transition-all ${
                  isActive 
                    ? 'bg-orange-500 text-white shadow-[0_0_25px_-5px_rgba(249,115,22,0.4)]' 
                    : 'text-slate-400 hover:bg-slate-800/80 hover:text-slate-200'
                }`
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span className="min-w-0 truncate">{item.label}</span>
              {item.showUnreadBadge && unreadCount > 0 && (
                <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-slate-950/50 text-[10px] font-black text-orange-400">
                  {unreadCount}
                </span>
              )}
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
          className="mt-auto flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/20 px-4 py-3 text-xs font-black uppercase tracking-widest text-slate-400 transition hover:bg-orange-500/10 hover:text-orange-300 hover:border-orange-500/30"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign Out</span>
        </button>
      </aside>

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-col min-h-screen">
        <main className="min-w-0 flex-1 overflow-x-hidden p-4 pb-24 sm:p-6 lg:p-8 lg:pb-10 xl:p-10">
          <Outlet context={auth} />
        </main>

        {/* Mobile Bottom Navigation */}
        <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around border-t border-slate-800 bg-slate-900/95 backdrop-blur-md px-2 safe-bottom">
          {visibleNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex h-16 min-w-0 flex-col items-center justify-center gap-1 transition-colors ${
                  isActive ? 'text-orange-500' : 'text-slate-500'
                }`
              }
            >
              <div className="relative">
                <item.icon className="h-5 w-5" />
                {item.showUnreadBadge && unreadCount > 0 && (
                  <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-orange-500 border-2 border-slate-900" />
                )}
              </div>
              <span className="max-w-full truncate text-[10px] font-black uppercase tracking-normal">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
