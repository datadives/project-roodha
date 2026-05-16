/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: App.jsx
 * 
 * 1) Purpose: Frontend core logic.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import React, { useEffect, useState, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation, useOutletContext } from 'react-router-dom'
import AccessDeniedPage from './components/AccessDeniedPage'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import JobsPage from './pages/JobsPage'
import MasterDataPage from './pages/MasterDataPage'
import AnalyticsPage from './pages/AnalyticsPage'
import NotificationsPage from './pages/NotificationsPage'
import PlanningPage from './pages/PlanningPage'
import SettingsPage from './pages/SettingsPage'
import UserManagement from './pages/UserManagement'
import WorklistPage from './pages/WorklistPage'
import LoginPage from './pages/LoginPage'
import { CONFIG } from './config'
import { useAuth } from './context/AuthContext'
import { getDefaultRouteForRole, hasAnyRole, listAllowedRoleLabels, normalizeRole } from './lib/roles'
import ErrorBoundary from './components/common/ErrorBoundary'

function ProtectedRoute({ allowedRoles = [] }) {
  const { auth, isAuthenticated, isInitializing } = useAuth()

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0F172A]">
        <div className="flex flex-col items-center">
          <div className="relative flex h-12 w-12 items-center justify-center">
            <div className="absolute h-full w-full animate-ping rounded-full bg-orange-500/20" />
            <div className="h-4 w-4 animate-spin rounded-sm bg-orange-500" />
          </div>
          <div className="mt-8 text-[10px] font-black uppercase tracking-[0.4em] text-slate-500">
            Verifying Secure Session
          </div>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />

  if (allowedRoles.length > 0 && !hasAnyRole(auth?.userRole, allowedRoles)) {
    return <Navigate to="/unauthorized" replace />
  }

  return <Outlet context={auth} />
}

function RoleRoute({ allowedRoles, title, message }) {
  const auth = useOutletContext()

  if (!hasAnyRole(auth?.userRole, allowedRoles)) {
    return (
      <AccessDeniedPage
        title={title}
        message={message}
        allowedRoles={listAllowedRoleLabels(allowedRoles)}
        homePath={getDefaultRouteForRole(auth?.userRole)}
      />
    )
  }

  return <Outlet context={auth} />
}

function HomeRoute() {
  const auth = useOutletContext()
  const userRole = normalizeRole(auth?.userRole)

  // Role-Based Navigation Guard
  if (userRole === 'OPERATOR') {
    return <Navigate to="/operator" replace />
  }

  if (!hasAnyRole(userRole, ['OWNER', 'SUPERVISOR'])) {
    return <Navigate to={getDefaultRouteForRole(userRole)} replace />
  }

  return <DashboardPage auth={auth} />
}

export default function App() {
  const location = useLocation()
  const allowSelfSignup = CONFIG.ENABLE_SELF_SIGNUP

  return (
    <ErrorBoundary resetKey={location.pathname}>
      <Suspense fallback={<div>Loading component...</div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/register"
            element={allowSelfSignup ? <LoginPage initialMode="CREATE_ACCOUNT" /> : <Navigate to="/login" replace />}
          />
          <Route
            path="/register/confirm"
            element={allowSelfSignup ? <LoginPage initialMode="CONFIRM_SIGN_UP" /> : <Navigate to="/login" replace />}
          />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<HomeRoute />} />
              <Route
                path="/unauthorized"
                element={
                  <AccessDeniedPage
                    title="Unauthorized workspace"
                    message="Your Cognito role does not allow this V1.5 workspace. Use the navigation assigned to your role."
                    homePath="/"
                  />
                }
              />
              <Route path="/dashboard" element={<HomeRoute />} />
              <Route
                element={<ProtectedRoute allowedRoles={['OPERATOR']} />}
              >
                <Route path="/operator" element={<WorklistPage />} />
              </Route>
              <Route path="/worklist" element={<WorklistPage />} />
              <Route
                element={<ProtectedRoute allowedRoles={['OWNER', 'SUPERVISOR']} />}
              >
                <Route path="/jobs" element={<JobsPage />} />
                <Route path="/master-data" element={<MasterDataPage />} />
                <Route path="/planning" element={<PlanningPage />} />
              </Route>
              <Route
                element={<ProtectedRoute allowedRoles={['OWNER']} />}
              >
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/users" element={<UserManagement />} />
              </Route>
              <Route path="/notifications" element={<NotificationsPage />} />
            </Route>
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
