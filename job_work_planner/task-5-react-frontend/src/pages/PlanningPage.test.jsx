// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const planningApiMock = vi.hoisted(() => ({
  applyAutoSchedule: vi.fn(),
  previewAutoSchedule: vi.fn(),
}))

vi.mock('../lib/planningApi', () => planningApiMock)

vi.mock('react-hot-toast', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

const singleSuggestion = {
  job_operation_id: 'op-001',
  job_number: 'JOB-PLAN-001',
  operation_name: 'Turning',
  machine_id: 'machine-001',
  machine_name: 'Lathe-01',
  planned_start_date: '2026-05-15T08:00:00.000Z',
  planned_end_date: '2026-05-15T10:00:00.000Z',
  estimated_hours: 2,
  due_date_risk: false,
}

const millingSuggestions = [
  {
    job_operation_id: 'op-early',
    job_number: 'MILL-EARLY',
    operation_name: 'Milling',
    machine_id: 'machine-milling-001',
    machine_name: 'Milling-01',
    planned_start_date: '2026-05-15T08:00:00.000Z',
    planned_end_date: '2026-05-15T10:00:00.000Z',
    estimated_hours: 2,
    due_date_risk: false,
  },
  {
    job_operation_id: 'op-middle',
    job_number: 'MILL-MIDDLE',
    operation_name: 'Milling',
    machine_id: 'machine-milling-001',
    machine_name: 'Milling-01',
    planned_start_date: '2026-05-15T10:00:00.000Z',
    planned_end_date: '2026-05-15T12:00:00.000Z',
    estimated_hours: 2,
    due_date_risk: false,
  },
  {
    job_operation_id: 'op-late',
    job_number: 'MILL-LATE',
    operation_name: 'Milling',
    machine_id: 'machine-milling-001',
    machine_name: 'Milling-01',
    planned_start_date: '2026-05-15T12:00:00.000Z',
    planned_end_date: '2026-05-15T14:00:00.000Z',
    estimated_hours: 2,
    due_date_risk: false,
  },
]

describe('PlanningPage Auto-Scheduler acceptance', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    planningApiMock.previewAutoSchedule.mockResolvedValue({
      suggestions: [singleSuggestion],
    })
    planningApiMock.applyAutoSchedule.mockResolvedValue({ applied_count: 3 })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders preview, allows local date edit, and cancel clears state without mutations', async () => {
    const { default: PlanningPage } = await import('./PlanningPage.jsx')
    render(<PlanningPage />)

    fireEvent.change(screen.getByLabelText(/^From/i), { target: { value: '2026-05-15' } })
    fireEvent.change(screen.getByLabelText(/^To/i), { target: { value: '2026-05-22' } })

    fireEvent.click(screen.getByRole('button', { name: /auto plan/i }))

    await waitFor(() => {
      expect(planningApiMock.previewAutoSchedule).toHaveBeenCalledWith({
        from_date: '2026-05-15',
        to_date: '2026-05-22',
        limit: 75,
      })
    })

    const previewTable = await screen.findByTestId('auto-plan-preview-table')
    expect(within(previewTable).getByText('JOB-PLAN-001')).toBeInTheDocument()
    expect(within(previewTable).getByText('Lathe-01')).toBeInTheDocument()

    const plannedStart = screen.getByLabelText(/planned start for job-plan-001/i)
    fireEvent.change(plannedStart, { target: { value: '2026-05-16T09:30' } })
    expect(plannedStart).toHaveValue('2026-05-16T09:30')

    fireEvent.click(screen.getByRole('button', { name: /^cancel$/i }))

    expect(screen.queryByTestId('auto-plan-preview-table')).not.toBeInTheDocument()
    expect(screen.queryByText('JOB-PLAN-001')).not.toBeInTheDocument()
    expect(screen.getByText(/run auto plan to generate a preview/i)).toBeInTheDocument()

    expect(planningApiMock.applyAutoSchedule).not.toHaveBeenCalled()
  })

  it('accepts all preview rows in one bulk apply request', async () => {
    planningApiMock.previewAutoSchedule.mockResolvedValueOnce({ suggestions: millingSuggestions })

    const { default: PlanningPage } = await import('./PlanningPage.jsx')
    render(<PlanningPage />)

    fireEvent.change(screen.getByLabelText(/^From/i), { target: { value: '2026-05-15' } })
    fireEvent.change(screen.getByLabelText(/^To/i), { target: { value: '2026-05-22' } })
    fireEvent.click(screen.getByRole('button', { name: /auto plan/i }))

    const previewTable = await screen.findByTestId('auto-plan-preview-table')
    expect(within(previewTable).getByText('MILL-EARLY')).toBeInTheDocument()
    expect(within(previewTable).getByText('MILL-MIDDLE')).toBeInTheDocument()
    expect(within(previewTable).getByText('MILL-LATE')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /accept all/i }))

    await waitFor(() => {
      expect(planningApiMock.applyAutoSchedule).toHaveBeenCalledTimes(1)
    })

    expect(planningApiMock.applyAutoSchedule).toHaveBeenCalledWith([
      {
        job_operation_id: 'op-early',
        machine_id: 'machine-milling-001',
        planned_start_date: '2026-05-15T08:00:00.000Z',
        planned_end_date: '2026-05-15T10:00:00.000Z',
      },
      {
        job_operation_id: 'op-middle',
        machine_id: 'machine-milling-001',
        planned_start_date: '2026-05-15T10:00:00.000Z',
        planned_end_date: '2026-05-15T12:00:00.000Z',
      },
      {
        job_operation_id: 'op-late',
        machine_id: 'machine-milling-001',
        planned_start_date: '2026-05-15T12:00:00.000Z',
        planned_end_date: '2026-05-15T14:00:00.000Z',
      },
    ])

    // eslint-disable-next-line no-console
    console.log(`AUTO_PLAN_ACCEPT_ALL rows=${millingSuggestions.length} bulk_calls=${planningApiMock.applyAutoSchedule.mock.calls.length}`)
  })
})
