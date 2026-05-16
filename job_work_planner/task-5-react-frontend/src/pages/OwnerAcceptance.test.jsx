// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const authMock = vi.hoisted(() => ({
  authValue: {
    auth: {
      isAuthenticated: true,
      token: 'owner-ui-token',
      tenantId: 'tenant-owner-ui-acceptance',
      tenant_id: 'tenant-owner-ui-acceptance',
      userRole: 'OWNER',
      role: 'OWNER',
    },
    role: 'OWNER',
    isAuthenticated: true,
    logout: vi.fn(() => Promise.resolve()),
  },
}))

const authenticatedFetchMock = vi.hoisted(() => ({
  authenticatedFetch: vi.fn(),
}))

const masterDataApiMock = vi.hoisted(() => ({
  fetchMachines: vi.fn(),
}))

const metricsApiMock = vi.hoisted(() => ({
  fetchBottleneckMetrics: vi.fn(),
  fetchCostingSummary: vi.fn(),
  fetchLateJobsMetrics: vi.fn(),
  fetchOnTimeDeliveryMetrics: vi.fn(),
  fetchWipMetrics: vi.fn(),
}))

const notificationsApiMock = vi.hoisted(() => ({
  fetchNotifications: vi.fn(),
}))

const toastMock = vi.hoisted(() => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => authMock.authValue,
}))
vi.mock('../lib/authenticatedFetch', () => authenticatedFetchMock)
vi.mock('../lib/masterDataApi', () => masterDataApiMock)
vi.mock('../lib/metricsApi', () => metricsApiMock)
vi.mock('../lib/notificationsApi', () => notificationsApiMock)
vi.mock('react-hot-toast', () => toastMock)

function renderOwnerWorkspace(initialPath = '/dashboard') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<div>Owner dashboard shell</div>} />
          <Route path="/jobs" element={<div>Jobs shell</div>} />
          <Route path="/planning" element={<div>Planning shell</div>} />
          <Route path="/worklist" element={<div>Work shell</div>} />
          <Route path="/master-data" element={<div>Master shell</div>} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/users" element={<UserManagement />} />
          <Route path="/settings" element={<div>Settings shell</div>} />
          <Route path="/notifications" element={<div>Alerts shell</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

let Layout
let UserManagement
let AnalyticsPage

describe('Owner persona frontend acceptance', () => {
  beforeEach(async () => {
    vi.resetModules()
    vi.clearAllMocks()

    notificationsApiMock.fetchNotifications.mockResolvedValue({ notifications: [], unread_count: 0 })
    masterDataApiMock.fetchMachines.mockResolvedValue([])
    metricsApiMock.fetchWipMetrics.mockResolvedValue({
      wip_by_stage: [{ stage: 'Cutting', count: 3 }],
    })
    metricsApiMock.fetchBottleneckMetrics.mockResolvedValue({
      bottlenecks: [{ machine_id: 'machine-1', machine_name: 'Lathe-01', pending_operations: 2 }],
    })
    metricsApiMock.fetchLateJobsMetrics.mockResolvedValue({ total_late: 1, jobs: [] })
    metricsApiMock.fetchCostingSummary.mockResolvedValue({
      overview: {
        total_jobs: 10,
        active_jobs: 7,
        completed_jobs: 3,
        late_jobs: 1,
        total_estimated_cost: 25000,
        open_estimated_cost: 17500,
        completed_estimated_cost: 7500,
        average_estimated_job_cost: 2500,
        highest_estimated_job_cost: 6000,
        highest_estimated_job_number: 'JOB-HIGH-001',
      },
      recent_completed_jobs: [],
      top_estimated_jobs: [],
    })
    metricsApiMock.fetchOnTimeDeliveryMetrics.mockResolvedValue({
      otd_percentage: 92.5,
      total_completed: 40,
      on_time_count: 37,
      late_count: 3,
    })
    authenticatedFetchMock.authenticatedFetch.mockImplementation((endpoint) => {
      if (endpoint === 'users/invite') {
        return Promise.resolve({ email: 'ravi.supervisor@example.com', role: 'SUPERVISOR' })
      }
      if (endpoint === 'exports/jobs') {
        return Promise.resolve({
          downloadUrl: 'data:text/csv;charset=utf-8,job_number%0AJOB-001',
          filename: 'owner_jobs.csv',
        })
      }
      return Promise.resolve({})
    })

    ;({ default: Layout } = await import('../components/Layout.jsx'))
    ;({ default: UserManagement } = await import('./UserManagement.jsx'))
    ;({ default: AnalyticsPage } = await import('./AnalyticsPage.jsx'))
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('allows an Owner to invite a Supervisor, view analytics metrics, and trigger CSV export', async () => {
    const anchorClickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    renderOwnerWorkspace()

    for (const label of ['Board', 'Jobs', 'Plan', 'Work', 'Master', 'Analytics', 'Users', 'Settings', 'Alerts']) {
      expect(screen.getAllByRole('link', { name: label }).length).toBeGreaterThan(0)
    }

    fireEvent.click(screen.getAllByRole('link', { name: 'Users' })[0])

    expect(await screen.findByRole('heading', { name: /invite employee/i })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Ravi Supervisor' } })
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'ravi.supervisor@example.com' } })
    fireEvent.change(screen.getByLabelText(/^role$/i), { target: { value: 'SUPERVISOR' } })
    fireEvent.click(screen.getByRole('button', { name: /invite employee/i }))

    await waitFor(() => {
      expect(authenticatedFetchMock.authenticatedFetch).toHaveBeenCalledWith('users/invite', {
        method: 'POST',
        body: JSON.stringify({
          name: 'Ravi Supervisor',
          email: 'ravi.supervisor@example.com',
          role: 'SUPERVISOR',
          machine_id: null,
        }),
      })
    })
    expect(toastMock.toast.success).toHaveBeenCalledWith('Employee invite sent')
    expect(toastMock.toast.error).not.toHaveBeenCalled()

    fireEvent.click(screen.getAllByRole('link', { name: 'Analytics' })[0])

    expect(await screen.findByText('Active Jobs')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText('On-time %')).toBeInTheDocument()
    expect(screen.getByText('92.5%')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /export all jobs/i }))

    await waitFor(() => {
      expect(authenticatedFetchMock.authenticatedFetch).toHaveBeenCalledWith('exports/jobs', { method: 'POST' })
    })
    expect(anchorClickSpy).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/unable to export/i)).not.toBeInTheDocument()

    // eslint-disable-next-line no-console
    console.log('OWNER_ACCEPTANCE invite=ok analytics=ok export=ok')
  })
})
