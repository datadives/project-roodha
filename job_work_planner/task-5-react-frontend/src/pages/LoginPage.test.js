// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import React from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const authMock = vi.hoisted(() => ({
  authValue: {
    isAuthenticated: false,
    login: vi.fn(),
  },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => authMock.authValue,
}))

vi.mock('../lib/auth', () => ({
  confirmSignUp: vi.fn(),
  confirmResetPassword: vi.fn(),
  getAuthContext: vi.fn(),
  handleConfirmSignIn: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  resendSignUpCode: vi.fn(),
  resetPassword: vi.fn(),
  signUp: vi.fn(),
  storeDevBypassSession: vi.fn((devUser) => ({
    ...devUser,
    token: 'roodha-dev-test-123',
    isAuthenticated: true,
  })),
}))

const authenticatedFetchMock = vi.hoisted(() => ({
  authenticatedFetch: vi.fn(),
}))

vi.mock('../lib/authenticatedFetch', () => authenticatedFetchMock)

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/api')
  vi.stubEnv('VITE_COGNITO_REGION', 'ap-south-1')
  vi.stubEnv('VITE_COGNITO_USER_POOL_ID', 'ap-south-1_U3JeTevgw')
  vi.stubEnv('VITE_COGNITO_CLIENT_ID', '3ab798pg0k2p8hp7v6bbtlh4mj')
  vi.stubEnv('VITE_ENABLE_SELF_SIGNUP', 'false')
  vi.resetModules()
  authMock.authValue.login.mockReset()
  authenticatedFetchMock.authenticatedFetch.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllEnvs()
})

describe('LoginPage helper logic', () => {
  it('forces the login view when self-signup is disabled', async () => {
    const { getInitialView } = await import('./LoginPage.jsx')

    expect(getInitialView('CREATE_ACCOUNT')).toBe('LOGIN')
    expect(getInitialView('SIGN_UP')).toBe('LOGIN')
    expect(getInitialView('FORGOT_PASSWORD')).toBe('LOGIN')
  })

  it('renders the login screen without the section-offline fallback', async () => {
    const { default: LoginPage } = await import('./LoginPage.jsx')

    render(
      React.createElement(
        MemoryRouter,
        { initialEntries: ['/login'] },
        React.createElement(LoginPage),
      ),
    )

    expect(screen.getByText(/Secure Login/i)).toBeInTheDocument()
    expect(screen.queryByText(/Section Offline/i)).not.toBeInTheDocument()
  })

  it('completes Cognito invited-user new password challenge inline', async () => {
    const auth = await import('../lib/auth')
    auth.login.mockResolvedValue({
      nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED' },
    })
    auth.handleConfirmSignIn.mockResolvedValue({ nextStep: { signInStep: 'DONE' } })
    auth.getAuthContext.mockResolvedValue({
      token: 'id-token',
      tenantId: 'tenant-invite-test',
      tenant_id: 'tenant-invite-test',
      userRole: 'OPERATOR',
      user_role: 'OPERATOR',
      role: 'OPERATOR',
      isAuthenticated: true,
    })
    authenticatedFetchMock.authenticatedFetch.mockResolvedValue({ role: 'OPERATOR' })

    const { default: LoginPage } = await import('./LoginPage.jsx')

    render(
      React.createElement(
        MemoryRouter,
        { initialEntries: ['/login'] },
        React.createElement(LoginPage),
      ),
    )

    fireEvent.change(screen.getByLabelText(/Email or Mobile/i), {
      target: { value: 'roshan.analytics101@gmail.com' },
    })
    fireEvent.change(screen.getByLabelText(/^Password$/i), {
      target: { value: 'TempPassword123!' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Establish Session/i }))

    expect(await screen.findByRole('heading', { name: /Set New Password/i })).toBeInTheDocument()
    expect(screen.getByText(/roshan.analytics101@gmail.com/i)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/New Password/i), {
      target: { value: 'Permanent123!' },
    })
    fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
      target: { value: 'Different123!' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Set Password & Sign In/i }))

    await waitFor(() => {
      expect(screen.getByText(/New password and confirmation must match/i)).toBeInTheDocument()
    })
    expect(auth.handleConfirmSignIn).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
      target: { value: 'Permanent123!' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Set Password & Sign In/i }))

    await waitFor(() => {
      expect(auth.handleConfirmSignIn).toHaveBeenCalledWith({ challengeResponse: 'Permanent123!' })
      expect(authMock.authValue.login).toHaveBeenCalledWith(
        expect.objectContaining({
          isAuthenticated: true,
          role: 'OPERATOR',
        }),
      )
    })
    expect(authenticatedFetchMock.authenticatedFetch).toHaveBeenCalledWith('tenants/create', { method: 'POST' })
  })
})
