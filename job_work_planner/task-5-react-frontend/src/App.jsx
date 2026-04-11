import { useEffect, useState } from 'react'
import { Navigate, Outlet, Route, Routes, useOutletContext } from 'react-router-dom'
import AccessDeniedPage from './components/AccessDeniedPage'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import JobsPage from './pages/JobsPage'
import MasterDataPage from './pages/MasterDataPage'
import AnalyticsPage from './pages/AnalyticsPage'
import NotificationsPage from './pages/NotificationsPage'
import LoginPage from './pages/LoginPage'
import { getAuthContext, getStoredDevAuthContext } from './lib/auth'
import { getDefaultRouteForRole, hasAnyRole, listAllowedRoleLabels } from './lib/roles'

function ProtectedRoute() {
  const [auth, setAuth] = useState(() => getStoredDevAuthContext())
  const [loading, setLoading] = useState(() => !Boolean(getStoredDevAuthContext()?.token))

  useEffect(() => {
    if (auth?.token) {
      setLoading(false)
      return
    }

    getAuthContext().then(setAuth).catch(() => setAuth(null)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6">Loading...</div>
  if (!auth?.token) return <Navigate to="/login" replace />

  return <Outlet context={auth} />
}

function RoleRoute({ allowedRoles, title, message }) {
  const auth = useOutletContext()

  if (!hasAnyRole(auth?.user_role, allowedRoles)) {
    return (
      <AccessDeniedPage
        title={title}
        message={message}
        allowedRoles={listAllowedRoleLabels(allowedRoles)}
        homePath={getDefaultRouteForRole(auth?.user_role)}
      />
    )
  }

  return <Outlet context={auth} />
}

function HomeRoute() {
  const auth = useOutletContext()

  if (!hasAnyRole(auth?.user_role, ['OWNER', 'ADMIN', 'SUPERVISOR', 'PLANNER', 'OPERATOR'])) {
    return <Navigate to={getDefaultRouteForRole(auth?.user_role)} replace />
  }

  return <DashboardPage auth={auth} />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<HomeRoute />} />
          <Route
            element={
              <RoleRoute
                allowedRoles={['OWNER', 'ADMIN', 'SUPERVISOR']}
                title="Supervisor workspace only"
                message="Job intake and master data updates are limited to supervisors, owners, and admins so planning inputs stay controlled."
              />
            }
          >
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/master-data" element={<MasterDataPage />} />
          </Route>
          <Route
            element={
              <RoleRoute
                allowedRoles={['OWNER', 'ADMIN', 'SUPERVISOR', 'PLANNER']}
                title="Planning access required"
                message="This workspace is reserved for roles that are allowed to view WIP metrics, planning load, and analytics."
              />
            }
          >
            <Route path="/analytics" element={<AnalyticsPage />} />
          </Route>
          <Route path="/notifications" element={<NotificationsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
