// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const authContextMock = vi.hoisted(() => ({
  authValue: {
    auth: {
      isAuthenticated: true,
      token: 'supervisor-ui-token',
      tenantId: 'tenant-supervisor-ui-acceptance',
      tenant_id: 'tenant-supervisor-ui-acceptance',
      userRole: 'SUPERVISOR',
      role: 'SUPERVISOR',
    },
    role: 'SUPERVISOR',
    isAuthenticated: true,
    isInitializing: false,
    logout: vi.fn(() => Promise.resolve()),
  },
}))

const authLibMock = vi.hoisted(() => ({
  getAuthContext: vi.fn(),
  getCachedAuthContextSync: vi.fn(),
  getLatestAuthContextForRequest: vi.fn(),
  getStoredDevAuthContext: vi.fn(),
  logout: vi.fn(() => Promise.resolve()),
  refreshAuthSession: vi.fn(() => Promise.resolve()),
}))

const jobsApiMock = vi.hoisted(() => ({
  createJob: vi.fn(),
  fetchJobAudit: vi.fn(),
}))

const masterDataApiMock = vi.hoisted(() => ({
  fetchCustomers: vi.fn(),
  fetchPartById: vi.fn(),
  fetchParts: vi.fn(),
}))

const customFieldsApiMock = vi.hoisted(() => ({
  fetchCustomFields: vi.fn(),
  saveCustomFieldValue: vi.fn(),
}))

const planningApiMock = vi.hoisted(() => ({
  applyAutoSchedule: vi.fn(),
  previewAutoSchedule: vi.fn(),
}))

const notificationsApiMock = vi.hoisted(() => ({
  fetchNotifications: vi.fn(),
}))

const metricsApiMock = vi.hoisted(() => ({
  fetchBottleneckMetrics: vi.fn(),
  fetchCostingSummary: vi.fn(),
  fetchLateJobsMetrics: vi.fn(),
  fetchOnTimeDeliveryMetrics: vi.fn(),
  fetchWipMetrics: vi.fn(),
}))

const toastMock = vi.hoisted(() => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

vi.mock('../context/AuthContext', () => ({
  AuthProvider: ({ children }) => <>{children}</>,
  useAuth: () => authContextMock.authValue,
}))
vi.mock('../lib/auth', () => authLibMock)
vi.mock('../lib/jobsApi', () => jobsApiMock)
vi.mock('../lib/masterDataApi', () => masterDataApiMock)
vi.mock('../lib/customFieldsApi', () => customFieldsApiMock)
vi.mock('../lib/planningApi', () => planningApiMock)
vi.mock('../lib/notificationsApi', () => notificationsApiMock)
vi.mock('../lib/metricsApi', () => metricsApiMock)
vi.mock('react-hot-toast', () => toastMock)

const supervisorAuth = {
  isAuthenticated: true,
  token: 'supervisor-ui-token',
  tenantId: 'tenant-supervisor-ui-acceptance',
  tenant_id: 'tenant-supervisor-ui-acceptance',
  userRole: 'SUPERVISOR',
  user_role: 'SUPERVISOR',
  role: 'SUPERVISOR',
}

const customer = {
  customer_id: 'customer-supervisor-001',
  name: 'Supervisor Customer',
}

const part = {
  part_id: 'part-supervisor-001',
  customer_id: 'customer-supervisor-001',
  part_number: 'SUP-PART-001',
  default_operations_route: [
    { operation_id: 'operation-cutting', name: 'Cutting', sequence: 1 },
  ],
}

const previewSuggestion = {
  job_operation_id: 'job-operation-supervisor-001',
  job_number: 'SUP-JOB-001',
  operation_name: 'Cutting',
  machine_id: 'machine-original-001',
  machine_name: 'CNC Original',
  planned_start_date: '2026-05-16T08:00:00.000Z',
  planned_end_date: '2026-05-16T10:00:00.000Z',
  estimated_hours: 2,
  due_date_risk: false,
}

async function renderAppAt(path) {
  const { default: App } = await import('../App.jsx')
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('Supervisor persona UI permissions and workflow', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()

    authLibMock.getAuthContext.mockResolvedValue(supervisorAuth)
    authLibMock.getCachedAuthContextSync.mockReturnValue(supervisorAuth)
    authLibMock.getLatestAuthContextForRequest.mockResolvedValue(supervisorAuth)
    authLibMock.getStoredDevAuthContext.mockReturnValue(supervisorAuth)
    notificationsApiMock.fetchNotifications.mockResolvedValue({ notifications: [], unread_count: 0 })

    masterDataApiMock.fetchCustomers.mockResolvedValue([customer])
    masterDataApiMock.fetchParts.mockResolvedValue([part])
    masterDataApiMock.fetchPartById.mockResolvedValue(part)
    customFieldsApiMock.fetchCustomFields.mockResolvedValue([])
    jobsApiMock.createJob.mockResolvedValue({
      job: {
        job_id: 'job-supervisor-001',
        job_number: 'SUP-JOB-001',
        priority: 'MEDIUM',
        current_stage: 'Cutting',
      },
      operations: [
        {
          job_operation_id: 'job-operation-supervisor-001',
          operation_name: 'Cutting',
          sequence_number: 1,
          status: 'NOT_STARTED',
        },
      ],
      costing: { estimated_cost: 2500, operation_count: 1, quantity: 120 },
    })
    planningApiMock.previewAutoSchedule.mockResolvedValue({ suggestions: [previewSuggestion] })
    planningApiMock.applyAutoSchedule.mockResolvedValue({ applied_count: 1 })

    metricsApiMock.fetchWipMetrics.mockResolvedValue({ wip_by_stage: [] })
    metricsApiMock.fetchBottleneckMetrics.mockResolvedValue({ bottlenecks: [] })
    metricsApiMock.fetchLateJobsMetrics.mockResolvedValue({ total_late: 0, jobs: [] })
    metricsApiMock.fetchCostingSummary.mockResolvedValue({ overview: {}, recent_completed_jobs: [], top_estimated_jobs: [] })
    metricsApiMock.fetchOnTimeDeliveryMetrics.mockResolvedValue({ otd_percentage: 100, total_completed: 0, on_time_count: 0 })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('hides user management, blocks forced users route, creates a job, and applies edited auto-plan', async () => {
    await renderAppAt('/jobs')

    expect(await screen.findByText(/launch a new job/i)).toBeInTheDocument()
    expect(screen.queryAllByRole('link', { name: 'Analytics' }).length).toBe(0)
    expect(screen.queryAllByRole('link', { name: 'Users' }).length).toBe(0)
    expect(screen.getAllByRole('link', { name: 'Jobs' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Plan' }).length).toBeGreaterThan(0)

    cleanup()
    await renderAppAt('/users')
    expect(await screen.findByText(/unauthorized workspace/i)).toBeInTheDocument()
    expect(screen.queryByText(/invite employee/i)).not.toBeInTheDocument()

    cleanup()
    await renderAppAt('/jobs')
    expect(await screen.findByText(/launch a new job/i)).toBeInTheDocument()

    const [customerSelect, partSelect, prioritySelect] = screen.getAllByRole('combobox')
    fireEvent.change(customerSelect, { target: { value: 'customer-supervisor-001' } })
    fireEvent.change(partSelect, { target: { value: 'part-supervisor-001' } })
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '120' } })
    fireEvent.change(document.querySelector('input[type="date"]'), { target: { value: '2026-05-23' } })
    fireEvent.change(prioritySelect, { target: { value: 'MEDIUM' } })
    fireEvent.click(screen.getByRole('button', { name: /initialize job/i }))

    await waitFor(() => {
      expect(jobsApiMock.createJob).toHaveBeenCalledWith({
        customer_id: 'customer-supervisor-001',
        part_id: 'part-supervisor-001',
        quantity: 120,
        due_date: '2026-05-23',
        priority: 'MEDIUM',
      })
    })
    expect(toastMock.toast.success).toHaveBeenCalledWith(expect.stringContaining('SUP-JOB-001'))

    cleanup()
    await renderAppAt('/planning')
    fireEvent.change(screen.getByLabelText(/^From/i), { target: { value: '2026-05-16' } })
    fireEvent.change(screen.getByLabelText(/^To/i), { target: { value: '2026-05-23' } })
    fireEvent.click(screen.getByRole('button', { name: /auto plan/i }))

    const previewTable = await screen.findByTestId('auto-plan-preview-table')
    expect(within(previewTable).getByText('SUP-JOB-001')).toBeInTheDocument()
    expect(within(previewTable).getByText('CNC Original')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/machine assignment for sup-job-001/i), {
      target: { value: 'machine-manual-override-002' },
    })
    fireEvent.click(screen.getByRole('button', { name: /accept all/i }))

    await waitFor(() => {
      expect(planningApiMock.applyAutoSchedule).toHaveBeenCalledWith([
        {
          job_operation_id: 'job-operation-supervisor-001',
          machine_id: 'machine-manual-override-002',
          planned_start_date: '2026-05-16T08:00:00.000Z',
          planned_end_date: '2026-05-16T10:00:00.000Z',
        },
      ])
    })

    // eslint-disable-next-line no-console
    console.log('SUPERVISOR_ACCEPTANCE users_hidden=ok job_create=ok auto_plan_save=ok')
  }, 15000)
})
