// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const authContextMock = vi.hoisted(() => ({
  value: {
    auth: null,
    isAuthenticated: false,
    isInitializing: true,
    logout: vi.fn(),
  },
}))

const notificationsApiMock = vi.hoisted(() => ({
  fetchNotifications: vi.fn(),
}))

vi.mock('./context/AuthContext', () => ({
  useAuth: () => authContextMock.value,
}))

vi.mock('./pages/DashboardPage', () => ({ default: () => <div>Dashboard Page</div> }))
vi.mock('./pages/JobsPage', () => ({ default: () => <div>Jobs Page</div> }))
vi.mock('./pages/MasterDataPage', () => ({ default: () => <div>Master Data Page</div> }))
vi.mock('./pages/AnalyticsPage', () => ({ default: () => <div>Analytics Page</div> }))
vi.mock('./pages/NotificationsPage', () => ({ default: () => <div>Notifications Page</div> }))
vi.mock('./pages/PlanningPage', () => ({ default: () => <div>Planning Page</div> }))
vi.mock('./pages/SettingsPage', () => ({ default: () => <div>Settings Page</div> }))
vi.mock('./pages/UserManagement', () => ({ default: () => <div>User Management Page</div> }))
vi.mock('./pages/WorklistPage', () => ({ default: () => <div>Operator Execution Page</div> }))
vi.mock('./pages/LoginPage', () => ({ default: () => <div>Login Page</div> }))
vi.mock('./lib/notificationsApi', () => notificationsApiMock)

function authValue(role, overrides = {}) {
  return {
    auth: {
      isAuthenticated: true,
      token: `${role.toLowerCase()}-token`,
      tenantId: 'tenant-auth-routing',
      tenant_id: 'tenant-auth-routing',
      userRole: role,
      user_role: role,
      role,
    },
    role,
    userRole: role,
    isAuthenticated: true,
    isInitializing: false,
    logout: vi.fn(() => Promise.resolve()),
    ...overrides,
  }
}

async function renderApp(path = '/') {
  const { default: App } = await import('./App.jsx')
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('auth routing guards', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    notificationsApiMock.fetchNotifications.mockResolvedValue({ notifications: [], unread_count: 0 })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders the hydration guard without redirecting to login while auth initializes', async () => {
    authContextMock.value = {
      auth: null,
      isAuthenticated: false,
      isInitializing: true,
      logout: vi.fn(),
    }

    await renderApp('/dashboard')

    expect(screen.getByText(/verifying secure session/i)).toBeInTheDocument()
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
    console.log('AUTH_ROUTING_HYDRATION spinner=ok no_login_redirect=ok')
  })

  it('routes Owner to dashboard and shows admin navigation', async () => {
    authContextMock.value = authValue('OWNER')

    await renderApp('/')

    expect(await screen.findByText('Dashboard Page')).toBeInTheDocument()
    for (const label of ['Board', 'Jobs', 'Plan', 'Work', 'Master', 'Analytics', 'Users', 'Settings', 'Alerts']) {
      expect(screen.getAllByRole('link', { name: label }).length).toBeGreaterThan(0)
    }
    console.log('AUTH_ROUTING_OWNER route=/dashboard nav=admin')
  })

  it('routes Supervisor to dashboard and hides Owner-only navigation', async () => {
    authContextMock.value = authValue('SUPERVISOR')

    await renderApp('/dashboard')

    expect(await screen.findByText('Dashboard Page')).toBeInTheDocument()
    for (const label of ['Jobs', 'Plan', 'Work', 'Master', 'Alerts']) {
      expect(screen.getAllByRole('link', { name: label }).length).toBeGreaterThan(0)
    }
    for (const hiddenLabel of ['Users', 'Settings', 'Analytics']) {
      expect(screen.queryAllByRole('link', { name: hiddenLabel }).length).toBe(0)
    }
    console.log('AUTH_ROUTING_SUPERVISOR route=/dashboard owner_tabs=hidden')
  })

  it('routes Operator and Worker aliases to the operator execution page', async () => {
    authContextMock.value = authValue('OPERATOR')
    await renderApp('/')
    expect(await screen.findByText('Operator Execution Page')).toBeInTheDocument()
    for (const hiddenLabel of ['Board', 'Jobs', 'Plan', 'Master', 'Analytics', 'Users', 'Settings']) {
      expect(screen.queryAllByRole('link', { name: hiddenLabel }).length).toBe(0)
    }

    cleanup()
    authContextMock.value = authValue('WORKER')
    await renderApp('/dashboard')
    expect(await screen.findByText('Operator Execution Page')).toBeInTheDocument()
    expect(screen.queryByText('Dashboard Page')).not.toBeInTheDocument()
    console.log('AUTH_ROUTING_OPERATOR route=/operator worker_alias=ok')
  })
})
