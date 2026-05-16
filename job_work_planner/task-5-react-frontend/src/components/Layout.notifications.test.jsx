// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const notificationsApiMock = vi.hoisted(() => ({
  fetchNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
}))

const authMock = vi.hoisted(() => ({
  authValue: {
    auth: {
      isAuthenticated: true,
      token: 'test-token',
      tenantId: 'tenant-notification-ui-test',
      tenant_id: 'tenant-notification-ui-test',
      userRole: 'OWNER',
      role: 'OWNER',
    },
    role: 'OWNER',
    isAuthenticated: true,
    logout: vi.fn(() => Promise.resolve()),
  },
}))

vi.mock('../lib/notificationsApi', () => notificationsApiMock)
vi.mock('../context/AuthContext', () => ({
  useAuth: () => authMock.authValue,
}))
vi.mock('react-hot-toast', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

const highPriorityNotification = {
  notification_id: 'notification-high-priority-001',
  type: 'HIGH_PRIORITY_JOB',
  title: 'High priority job created',
  message: 'Job HP-NOTIF-001 was created with high priority.',
  entity_type: 'JOB',
  entity_id: 'job-high-priority-001',
  is_read: false,
  user_id: null,
  created_at: '2026-05-15T09:00:00.000Z',
}

describe('Layout notification bell state', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    const layoutUnreadCounts = [0, 1]
    notificationsApiMock.fetchNotifications.mockImplementation((params = undefined) => {
      if (params && Object.prototype.hasOwnProperty.call(params, 'unread_only')) {
        return Promise.resolve({
          notifications: [highPriorityNotification],
          unread_count: 1,
        })
      }
      const unread_count = layoutUnreadCounts.shift() ?? 1
      return Promise.resolve({ notifications: [], unread_count })
    })
    notificationsApiMock.markNotificationRead.mockResolvedValue({
      ...highPriorityNotification,
      is_read: true,
      read_at: '2026-05-15T09:05:00.000Z',
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('increments from notification refresh and decrements locally after mark-read succeeds', async () => {
    const { default: Layout } = await import('./Layout.jsx')
    const { default: NotificationsPage } = await import('../pages/NotificationsPage.jsx')

    render(
      <MemoryRouter initialEntries={['/notifications']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/notifications" element={<NotificationsPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText(/job hp-notif-001 was created with high priority/i)
    expect(screen.queryByLabelText(/unread notifications/i)).not.toBeInTheDocument()
    // eslint-disable-next-line no-console
    console.log('NOTIFICATION_BELL_INITIAL unread=0')

    await act(async () => {
      window.dispatchEvent(new CustomEvent('notifications:refresh'))
    })

    expect(await screen.findByLabelText('1 unread notifications')).toBeInTheDocument()
    // eslint-disable-next-line no-console
    console.log('NOTIFICATION_BELL_AFTER_HIGH_PRIORITY unread=1')

    fireEvent.click(screen.getByRole('button', { name: /mark as read/i }))

    await waitFor(() => {
      expect(notificationsApiMock.markNotificationRead).toHaveBeenCalledWith('notification-high-priority-001')
    })
    await waitFor(() => {
      expect(screen.queryByLabelText(/unread notifications/i)).not.toBeInTheDocument()
    })

    expect(screen.getByText('Acknowledged')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /mark as read/i })).not.toBeInTheDocument()
    // eslint-disable-next-line no-console
    console.log('NOTIFICATION_MARK_READ notification=notification-high-priority-001 unread=0')
  })
})
