// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const masterDataMock = vi.hoisted(() => ({
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
  fetchParts: vi.fn(),
  fetchShifts: vi.fn(),
  fetchWorkers: vi.fn(),
  updateCustomer: vi.fn(),
  updateMachine: vi.fn(),
  updatePart: vi.fn(),
  updateShift: vi.fn(),
  updateWorker: vi.fn(),
}))

const customFieldsMock = vi.hoisted(() => ({
  fetchCustomFields: vi.fn(),
}))

vi.mock('../lib/masterDataApi', () => masterDataMock)
vi.mock('../lib/customFieldsApi', () => customFieldsMock)
vi.mock('../lib/auth', () => ({
  DEV_TENANT_ID: 'lalafactory',
  getAuthContext: vi.fn().mockResolvedValue({
    tenant_id: 'tenant-ui-custom-field-test',
    user_role: 'OWNER',
  }),
}))
vi.mock('react-hot-toast', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

describe('MasterDataPage custom fields', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    masterDataMock.fetchCustomers.mockResolvedValue([
      { customer_id: 'customer-001', name: 'Apex Components', is_active: true },
    ])
    masterDataMock.fetchMachines.mockResolvedValue([])
    masterDataMock.fetchParts.mockResolvedValue([])
    masterDataMock.fetchShifts.mockResolvedValue([])
    masterDataMock.fetchWorkers.mockResolvedValue([])
    customFieldsMock.fetchCustomFields.mockImplementation((entityType) => {
      if (entityType === 'PART') {
        return Promise.resolve([
          {
            field_id: 'field-material-thickness',
            entity_type: 'PART',
            field_name: 'Material Thickness',
            field_type: 'NUMBER',
            options_json: [],
          },
        ])
      }
      return Promise.resolve([])
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders PART number custom field and blocks alphabetic values before API submit', async () => {
    const { default: MasterDataPage } = await import('./MasterDataPage.jsx')
    render(<MasterDataPage />)

    fireEvent.click(await screen.findByRole('button', { name: /parts/i }))

    const materialThickness = await screen.findByLabelText(/material thickness/i)
    expect(materialThickness).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/part number/i), { target: { value: 'PART-THICK-001' } })
    fireEvent.change(screen.getByLabelText(/customer/i), { target: { value: 'customer-001' } })
    fireEvent.change(materialThickness, { target: { value: 'abc' } })

    expect(await screen.findByText(/material thickness must be a number/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /create part/i }))

    await waitFor(() => {
      expect(masterDataMock.createPart).not.toHaveBeenCalled()
    })
    expect(screen.getByText(/material thickness must be a number/i)).toBeInTheDocument()
  })
})
