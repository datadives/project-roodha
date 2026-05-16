// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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

vi.mock('../lib/planningApi', () => planningApiMock)
vi.mock('../lib/masterDataApi', () => masterDataApiMock)
vi.mock('../lib/jobOperationsApi', () => jobOperationsApiMock)

vi.mock('react-hot-toast', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

describe('WorklistPage empty queue state', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    planningApiMock.fetchWorklist.mockResolvedValue({ items: [] })
    masterDataApiMock.fetchMachines.mockResolvedValue([
      { machine_id: 'machine-a', name: 'Machine A' },
    ])
    masterDataApiMock.fetchWorkers.mockResolvedValue([])
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('shows an all caught up empty state when the filtered queue is empty', async () => {
    const { default: WorklistPage } = await import('./WorklistPage.jsx')
    render(<WorklistPage />)

    expect(await screen.findByText(/all caught up/i)).toBeInTheDocument()
    expect(screen.getByText(/no active work is queued/i)).toBeInTheDocument()
    expect(screen.queryByText(/section offline/i)).not.toBeInTheDocument()
  })

  it('renders job tags returned by the worklist API', async () => {
    planningApiMock.fetchWorklist.mockResolvedValueOnce({
      items: [
        {
          job_operation_id: 'work-op-critical',
          job_number: 'TAG-JOB-CRITICAL',
          operation_name: 'Milling',
          part_number: 'TAG-PART',
          quantity: 20,
          status: 'NOT_STARTED',
          previous_operation_status: 'READY',
          planned_start_date: '2026-05-15T09:00:00.000Z',
          customer_name: 'Tagged Customer',
          tags: ['Critical'],
        },
      ],
    })
    const { default: WorklistPage } = await import('./WorklistPage.jsx')
    render(<WorklistPage />)

    expect(await screen.findByText('TAG-JOB-CRITICAL')).toBeInTheDocument()
    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.queryByText(/all caught up/i)).not.toBeInTheDocument()
    // eslint-disable-next-line no-console
    console.log('WORKLIST_TAG_RENDER tag=Critical')
  })
})
