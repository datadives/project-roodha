import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import MachineLoadRadar from '../components/dashboard/MachineLoadRadar';

describe('MachineLoadRadar Resilience UI Tests', () => {
  
  it('renders a friendly fallback message when data is completely null', () => {
    // Simulating a backend failure or loading state
    render(<MachineLoadRadar data={null} />);
    
    // It should not throw a mapping error, it should show text
    expect(screen.getByText(/No data available/i)).toBeInTheDocument();
  });

  it('renders a friendly fallback message when data is an empty array', () => {
    // Simulating a brand new factory with no jobs yet
    render(<MachineLoadRadar data={[]} />);
    
    expect(screen.getByText(/No data available/i)).toBeInTheDocument();
  });

  it('renders the chart container when valid data is passed', () => {
    const mockData = [
      { machine_name: 'CNC-1', planned_hours: 8 },
      { machine_name: 'Laser-2', planned_hours: 12 }
    ];
    
    const { container } = render(<MachineLoadRadar data={mockData} />);
    // Ensure the fallback text is NOT there
    expect(screen.queryByText(/No data available/i)).not.toBeInTheDocument();
  });
});