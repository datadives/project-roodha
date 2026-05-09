import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import MachineLoadRadar from '../components/MachineLoadRadar'

afterEach(() => {
  cleanup()
})

describe('MachineLoadRadar dashboard resilience', () => {
  it('renders the empty-state fallback and does not crash when data is null', () => {
    render(<MachineLoadRadar data={null} jobs={null} machines={null} />)

    expect(
      screen.getByText(/No machine workload data projected for the next 7 days/i),
    ).toBeInTheDocument()
  })

  it('renders the empty-state fallback and does not crash when data is empty', () => {
    render(<MachineLoadRadar data={[]} jobs={[]} machines={[]} />)

    expect(
      screen.getByText(/No machine workload data projected for the next 7 days/i),
    ).toBeInTheDocument()
  })
})
