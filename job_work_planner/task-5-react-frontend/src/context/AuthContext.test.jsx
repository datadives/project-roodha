// @vitest-environment jsdom

import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const authLibMock = vi.hoisted(() => ({
  getAuthContext: vi.fn(),
  getCachedAuthContextSync: vi.fn(),
  getStoredDevAuthContext: vi.fn(),
  logout: vi.fn(() => Promise.resolve()),
}))

vi.mock('../lib/auth', () => authLibMock)

function Consumer() {
  const { isInitializing, isAuthenticated, role, tenantId, logout } = useAuth()
  return (
    <div>
      <div data-testid="state">
        {isInitializing ? 'initializing' : 'ready'}|{isAuthenticated ? 'yes' : 'no'}|{role || 'none'}|{tenantId || 'none'}
      </div>
      <button onClick={logout}>Logout</button>
    </div>
  )
}

let AuthProvider
let normalizeContext
let useAuth

describe('AuthContext hydration and purge', () => {
  beforeEach(async () => {
    vi.resetModules()
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    ;({ AuthProvider, normalizeContext, useAuth } = await import('./AuthContext.jsx'))
  })

  afterEach(() => {
    cleanup()
    localStorage.clear()
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('normalizes WORKER to OPERATOR and only authenticates complete sessions', () => {
    expect(normalizeContext({ token: 't', tenant_id: 'tenant-a', role: 'WORKER' })).toMatchObject({
      role: 'OPERATOR',
      userRole: 'OPERATOR',
      tenantId: 'tenant-a',
      isAuthenticated: true,
    })
    expect(normalizeContext({ token: 't', role: 'OWNER' })?.isAuthenticated).toBe(false)
  })

  it('keeps initializing true until fresh session hydration completes', async () => {
    let resolveAuth
    authLibMock.getCachedAuthContextSync.mockReturnValue(null)
    authLibMock.getStoredDevAuthContext.mockReturnValue(null)
    authLibMock.getAuthContext.mockReturnValue(new Promise((resolve) => {
      resolveAuth = resolve
    }))

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )

    expect(screen.getByTestId('state')).toHaveTextContent('initializing|no|none|none')

    resolveAuth({
      token: 'fresh-token',
      tenantId: 'tenant-a',
      role: 'WORKER',
    })

    await waitFor(() => {
      expect(screen.getByTestId('state')).toHaveTextContent('ready|yes|OPERATOR|tenant-a')
    })
    console.log('AUTH_CONTEXT_HYDRATION role=OPERATOR status=ready')
  })

  it('logout clears React auth state and browser storage before sign-out completes', async () => {
    authLibMock.getCachedAuthContextSync.mockReturnValue(null)
    authLibMock.getStoredDevAuthContext.mockReturnValue(null)
    authLibMock.getAuthContext.mockResolvedValue({
      token: 'owner-token',
      tenantId: 'tenant-a',
      role: 'OWNER',
    })
    localStorage.setItem('token', 'owner-token')
    sessionStorage.setItem('draft', 'stale')

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    )

    await screen.findByText('ready|yes|OWNER|tenant-a')
    fireEvent.click(screen.getByRole('button', { name: /logout/i }))

    await waitFor(() => {
      expect(screen.getByTestId('state')).toHaveTextContent('ready|no|none|none')
    })
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    expect(authLibMock.logout).toHaveBeenCalledTimes(1)
    console.log('AUTH_CONTEXT_LOGOUT storage=cleared state=cleared')
  })
})
