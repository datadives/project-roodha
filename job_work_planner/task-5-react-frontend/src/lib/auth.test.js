import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const authMocks = vi.hoisted(() => ({
  fetchAuthSession: vi.fn(),
  getCurrentUser: vi.fn(),
  fetchUserAttributes: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
  confirmSignIn: vi.fn(),
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
  resendSignUpCode: vi.fn(),
  resetPassword: vi.fn(),
  confirmResetPassword: vi.fn(),
}))

vi.mock('aws-amplify/auth', () => authMocks)

function makeJwtPayload(payload) {
  const encoded = Buffer.from(JSON.stringify(payload)).toString('base64url')
  return `header.${encoded}.signature`
}

async function loadAuthModule() {
  return import('./auth.js')
}

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/api')
  vi.stubEnv('VITE_COGNITO_REGION', 'ap-south-1')
  vi.stubEnv('VITE_COGNITO_USER_POOL_ID', 'ap-south-1_U3JeTevgw')
  vi.stubEnv('VITE_COGNITO_CLIENT_ID', '3ab798pg0k2p8hp7v6bbtlh4mj')
  vi.stubEnv('VITE_ALLOW_DEV_PASS', 'false')
  vi.resetModules()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.clearAllMocks()
})

describe('auth helpers', () => {
  it('normalizes phone identities before sign-in', async () => {
    authMocks.signIn.mockResolvedValue({ nextStep: { signInStep: 'DONE' } })
    const { login } = await loadAuthModule()

    await login('9876543210', 'secret-pass')

    expect(authMocks.signIn).toHaveBeenCalledWith({
      username: '+919876543210',
      password: 'secret-pass',
    })
  })

  it('prefers the backend role when hydrating auth context', async () => {
    const tokenPayload = {
      sub: 'user-123',
      email: 'owner@example.com',
      'custom:tenant_id': 'tenant-cognito',
      'custom:user_role': 'OPERATOR',
    }

    authMocks.getCurrentUser.mockResolvedValue({
      userId: 'user-123',
      signInDetails: { loginId: 'owner@example.com' },
    })
    authMocks.fetchAuthSession.mockResolvedValue({
      tokens: {
        idToken: {
          toString: () => makeJwtPayload(tokenPayload),
          payload: tokenPayload,
        },
      },
    })
    authMocks.fetchUserAttributes.mockResolvedValue(null)

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          user: {
            tenant_id: 'tenant-db',
            user_role: 'OWNER',
            role: 'OWNER',
            user_id: 'user-123',
          },
        },
      }),
    })

    const { getAuthContext } = await loadAuthModule()
    const authContext = await getAuthContext({ forceFresh: true })

    expect(authContext.userRole).toBe('OWNER')
    expect(authContext.role).toBe('OWNER')
    expect(authContext.user_role).toBe('OWNER')
    expect(authContext.tenantId).toBe('tenant-cognito')
  })
})
