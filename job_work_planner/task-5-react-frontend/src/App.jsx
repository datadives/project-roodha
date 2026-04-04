import { useEffect, useState } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import JobsPage from './pages/JobsPage'
import MasterDataPage from './pages/MasterDataPage'
import AnalyticsPage from './pages/AnalyticsPage'
import LoginPage from './pages/LoginPage'
import { getAuthContext } from './lib/auth'

function ProtectedRoute() {
  const [loading, setLoading] = useState(true)
  const [auth, setAuth] = useState(null)

  useEffect(() => {
    getAuthContext().then(setAuth).catch(() => setAuth(null)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6">Loading...</div>
  if (!auth?.token) return <Navigate to="/login" replace />

  return <Outlet />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/master-data" element={<MasterDataPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
