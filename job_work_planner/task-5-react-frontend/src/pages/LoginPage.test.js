// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import React from 'react'
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
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

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/api')
  vi.stubEnv('VITE_COGNITO_REGION', 'ap-south-1')
  vi.stubEnv('VITE_COGNITO_USER_POOL_ID', 'ap-south-1_U3JeTevgw')
  vi.stubEnv('VITE_COGNITO_CLIENT_ID', '3ab798pg0k2p8hp7v6bbtlh4mj')
  vi.stubEnv('VITE_ENABLE_SELF_SIGNUP', 'false')
  vi.resetModules()
})

afterEach(() => {
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
})
