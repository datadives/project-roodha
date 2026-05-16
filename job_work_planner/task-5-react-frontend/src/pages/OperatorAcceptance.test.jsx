// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const authContextMock = vi.hoisted(() => ({
  authValue: {
    auth: {
      isAuthenticated: true,
      token: 'operator-ui-token',
      tenantId: 'tenant-operator-ui-acceptance',
      tenant_id: 'tenant-operator-ui-acceptance',
      userRole: 'OPERATOR',
      role: 'OPERATOR',
      machineId: 'machine-operator-001',
      machine_id: 'machine-operator-001',
    },
    role: 'OPERATOR',
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

const planningApiMock = vi.hoisted(() => ({
  fetchWorklist: vi.fn(),
}))

const masterDataApiMock = vi.hoisted(() => ({
  fetchMachines: vi.fn(),
  fetchWorkers: vi.fn(),
}))

const jobOperationsApiMock = vi.hoisted(() => ({
  updateJobOperationStatus: vi.fn(),
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
  AuthProvider: ({ children }) => <>{children}</>,
  useAuth: () => authContextMock.authValue,
}))
vi.mock('../lib/auth', () => authLibMock)
vi.mock('../lib/planningApi', () => planningApiMock)
vi.mock('../lib/masterDataApi', () => masterDataApiMock)
vi.mock('../lib/jobOperationsApi', () => jobOperationsApiMock)
vi.mock('../lib/notificationsApi', () => notificationsApiMock)
vi.mock('react-hot-toast', () => toastMock)

const operatorAuth = {
  isAuthenticated: true,
  token: 'operator-ui-token',
  tenantId: 'tenant-operator-ui-acceptance',
  tenant_id: 'tenant-operator-ui-acceptance',
  userRole: 'OPERATOR',
  user_role: 'OPERATOR',
  role: 'OPERATOR',
  machineId: 'machine-operator-001',
  machine_id: 'machine-operator-001',
}

const assignedOperation = {
  job_operation_id: 'operator-operation-001',
  job_number: 'OP-JOB-001',
  operation_name: 'Cutting',
  part_number: 'OP-PART-001',
  quantity: 50,
  status: 'NOT_STARTED',
  previous_operation_status: 'READY',
  planned_start_date: '2026-05-16T09:00:00.000Z',
  customer_name: 'Operator Customer',
  machine_id: 'machine-operator-001',
  machine_name: 'Operator Machine',
}

async function renderAppAt(path) {
  const { default: App } = await import('../App.jsx')
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('Operator persona UI restrictions and work execution', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()

    authLibMock.getAuthContext.mockResolvedValue(operatorAuth)
    authLibMock.getCachedAuthContextSync.mockReturnValue(operatorAuth)
    authLibMock.getLatestAuthContextForRequest.mockResolvedValue(operatorAuth)
    authLibMock.getStoredDevAuthContext.mockReturnValue(operatorAuth)
    notificationsApiMock.fetchNotifications.mockResolvedValue({ notifications: [], unread_count: 0 })
    masterDataApiMock.fetchMachines.mockResolvedValue([
      { machine_id: 'machine-operator-001', name: 'Operator Machine' },
    ])
    masterDataApiMock.fetchWorkers.mockResolvedValue([])
    planningApiMock.fetchWorklist.mockResolvedValue({ items: [assignedOperation] })
    jobOperationsApiMock.updateJobOperationStatus.mockResolvedValue({})
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('hides management UI, shows assigned work only, starts and completes operation with quantities', async () => {
    await renderAppAt('/worklist')

    expect(await screen.findByText('OP-JOB-001')).toBeInTheDocument()
    expect(screen.queryByText('OTHER-JOB-001')).not.toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Operator Kanban' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Work' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Alerts' }).length).toBeGreaterThan(0)

    for (const hiddenNav of ['Board', 'Jobs', 'Plan', 'Master', 'Analytics', 'Users', 'Settings']) {
      expect(screen.queryAllByRole('link', { name: hiddenNav }).length).toBe(0)
    }
    expect(screen.queryByText(/export/i)).not.toBeInTheDocument()

    cleanup()
    for (const route of ['/jobs', '/planning', '/master-data', '/analytics', '/users']) {
      await renderAppAt(route)
      expect(await screen.findByText(/unauthorized workspace/i)).toBeInTheDocument()
      expect(screen.queryByText(/job intake/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/auto plan/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/team access/i)).not.toBeInTheDocument()
      cleanup()
    }

    await renderAppAt('/worklist')
    expect(await screen.findByText('OP-JOB-001')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^start$/i }))
    await waitFor(() => {
      expect(jobOperationsApiMock.updateJobOperationStatus).toHaveBeenCalledWith('operator-operation-001', {
        status: 'IN_PROGRESS',
      })
    })
    expect(await screen.findByText('IN_PROGRESS')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^complete$/i }))
    expect(await screen.findByText(/complete operation/i)).toBeInTheDocument()
    const [completedInput, rejectedInput] = screen.getAllByRole('spinbutton')
    fireEvent.change(completedInput, { target: { value: '48' } })
    fireEvent.change(rejectedInput, { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: /confirm complete/i }))

    await waitFor(() => {
      expect(jobOperationsApiMock.updateJobOperationStatus).toHaveBeenCalledWith('operator-operation-001', {
        status: 'COMPLETED',
        quantity_completed: 48,
        quantity_rejected: 2,
      })
    })
    expect(screen.queryByText('OP-JOB-001')).not.toBeInTheDocument()
    expect(screen.getByText(/all caught up/i)).toBeInTheDocument()

    // eslint-disable-next-line no-console
    console.log('OPERATOR_ACCEPTANCE nav=restricted start=ok complete=ok')
  }, 15000)
})
