import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import MasterDataPage from '../pages/MasterDataPage'

vi.mock('../lib/auth', () => ({
  getAuthContext: vi.fn(),
  logout: vi.fn(),
}))

vi.mock('../lib/metricsApi', () => ({
  fetchWipMetrics: vi.fn(),
  fetchBottleneckMetrics: vi.fn(),
  fetchLateJobsMetrics: vi.fn(),
  fetchCostingSummary: vi.fn(),
}))

vi.mock('../lib/masterDataApi', () => ({
  createCustomer: vi.fn(),
  createMachine: vi.fn(),
  createPart: vi.fn(),
  createShift: vi.fn(),
  createWorker: vi.fn(),
  deleteCustomer: vi.fn(),
  deletePart: vi.fn(),
  deleteShift: vi.fn(),
  deleteWorker: vi.fn(),
  fetchCustomers: vi.fn(),
  fetchMachines: vi.fn(),
  fetchPartById: vi.fn(),
  fetchParts: vi.fn(),
  fetchShifts: vi.fn(),
  fetchWorkers: vi.fn(),
  updateCustomer: vi.fn(),
  updateMachine: vi.fn(),
  updatePart: vi.fn(),
  updateShift: vi.fn(),
  updateWorker: vi.fn(),
}))

vi.mock('../lib/jobsApi', () => ({
  createJob: vi.fn(),
  fetchJobAudit: vi.fn(),
  fetchJobById: vi.fn(),
  fetchJobs: vi.fn(),
}))

vi.mock('../lib/jobOperationsApi', () => ({
  fetchJobOperationAudit: vi.fn(),
  planJobOperation: vi.fn(),
  updateJobOperationStatus: vi.fn(),
}))

vi.mock('../lib/planningApi', () => ({
  fetchPlanningCalendar: vi.fn(),
}))

vi.mock('../lib/notificationsApi', () => ({
  fetchNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
}))

import { getAuthContext } from '../lib/auth'
import { fetchJobAudit, fetchJobById } from '../lib/jobsApi'
import { fetchJobOperationAudit, planJobOperation, updateJobOperationStatus } from '../lib/jobOperationsApi'
import {
  fetchCustomers,
  fetchMachines,
  fetchParts,
  fetchShifts,
  fetchWorkers,
} from '../lib/masterDataApi'
import { fetchWipMetrics } from '../lib/metricsApi'
import { fetchNotifications } from '../lib/notificationsApi'
import { fetchPlanningCalendar } from '../lib/planningApi'

const boardPayload = {
  wip_by_stage: [{ stage: 'CUTTING', count: 1 }],
  stages: [
    {
      stage_id: 'CUTTING',
      stage_name: 'Cutting',
      jobs: [
        {
          job_id: 'JOB-1',
          job_number: 'JW-001',
          quantity: 12,
          due_date: '2026-04-30',
          priority: 'HIGH',
          delayed: false,
          customer_id: 'CUS-1',
        },
      ],
      counts: { total: 1, delayed: 0 },
    },
  ],
}

const jobDetailPayload = {
  job: {
    job_id: 'JOB-1',
    job_number: 'JW-001',
    current_stage: 'CUTTING',
    due_date: '2026-04-30',
    priority: 'HIGH',
  },
  operations: [
    {
      job_operation_id: 'JOP-1',
      operation_id: 'CUTTING',
      sequence_number: 1,
      status: 'READY',
      machine_id: 'MAC-1',
      shift_id: 'SHF-1',
      planned_start_date: '2026-04-10',
      planned_end_date: '2026-04-10',
    },
  ],
}

function setAuth(authOverride = {}) {
  vi.mocked(getAuthContext).mockResolvedValue({
    token: 'token-123',
    tenant_id: 'tenant-123',
    user_role: 'SUPERVISOR',
    ...authOverride,
  })
}

function renderWithProviders(ui, { role = 'SUPERVISOR', route = '/', authOverride = null } = {}) {
  if (authOverride) {
    setAuth(authOverride)
  } else {
    setAuth({ user_role: role })
  }
  return render(
    <MemoryRouter initialEntries={[route]}>
      {ui}
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setAuth({ user_role: 'SUPERVISOR' })
  vi.mocked(fetchNotifications).mockResolvedValue({ unread_count: 0, items: [] })
  vi.mocked(fetchWipMetrics).mockResolvedValue(boardPayload)
  vi.mocked(fetchMachines).mockResolvedValue([{ machine_id: 'MAC-1', name: 'Laser 1', type: 'Laser', is_active: true }])
  vi.mocked(fetchShifts).mockResolvedValue([{ shift_id: 'SHF-1', name: 'Morning', start_time: '08:00', end_time: '16:00' }])
  vi.mocked(fetchCustomers).mockImplementation(async (includeInactive = false) =>
    includeInactive
      ? [{ customer_id: 'CUS-1', name: 'Apex Components', contact: 'Riya', is_active: true }]
      : [{ customer_id: 'CUS-1', name: 'Apex Components', contact: 'Riya', is_active: true }],
  )
  vi.mocked(fetchParts).mockResolvedValue([
    {
      part_id: 'PRT-1',
      part_number: 'PART-AX-204',
      customer_id: 'CUS-1',
      default_operations_route: [
        { operation: 'Cutting', sequence: 1 },
        { operation: 'Machining', sequence: 2 },
      ],
    },
  ])
  vi.mocked(fetchWorkers).mockResolvedValue([{ worker_id: 'WRK-1', name: 'Ravi', role: 'Operator', is_active: true }])
  vi.mocked(fetchJobById).mockResolvedValue(jobDetailPayload)
  vi.mocked(fetchJobAudit).mockResolvedValue({ audit_trail: [] })
  vi.mocked(fetchJobOperationAudit).mockResolvedValue({ audit_trail: [] })
  vi.mocked(fetchPlanningCalendar).mockResolvedValue({})
  vi.mocked(planJobOperation).mockResolvedValue(jobDetailPayload.operations[0])
  vi.mocked(updateJobOperationStatus).mockResolvedValue({ ...jobDetailPayload.operations[0], status: 'IN_PROGRESS' })
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('Access Control', () => {
  it('shows the dashboard task list for an OPERATOR instead of blocking access', async () => {
    renderWithProviders(<App />, { role: 'OPERATOR', route: '/' })

    expect(await screen.findByText(/Main WIP dashboard/i)).toBeInTheDocument()
    expect(await screen.findByText('JW-001')).toBeInTheDocument()
    expect(screen.queryByText(/Access limited/i)).not.toBeInTheDocument()
  })

  it('lets a PLANNER open the planning modal from the dashboard', async () => {
    renderWithProviders(<App />, { role: 'PLANNER', route: '/' })

    expect(await screen.findByText(/Role:\s*Planner/i)).toBeInTheDocument()
    const jobCard = await screen.findByRole('button', { name: /JW-001/i })
    fireEvent.click(jobCard)

    expect(await screen.findByText(/Assign machine and shift/i)).toBeInTheDocument()
    expect(screen.getAllByText(/^View only$/i).length).toBeGreaterThan(0)
  })

  it('hides delete actions in Master Data for a PLANNER role', async () => {
    renderWithProviders(<MasterDataPage />, { role: 'PLANNER' })

    expect(await screen.findByText(/Shape the production backbone/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Apex Components')).toBeInTheDocument())

    expect(screen.getByText(/view-only mode/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Delete$/i })).not.toBeInTheDocument()
  })

  it('shows a clear session error when auth data is incomplete', async () => {
    renderWithProviders(<App />, {
      route: '/notifications',
      authOverride: { token: 'token-123', tenant_id: null, user_role: null },
    })

    expect(await screen.findByText(/The login data is incomplete/i)).toBeInTheDocument()
    expect(screen.getByText(/missing: tenant_id, user_role/i)).toBeInTheDocument()
  })
})
