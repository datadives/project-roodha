import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/api')
  vi.stubEnv('VITE_COGNITO_REGION', 'ap-south-1')
  vi.stubEnv('VITE_COGNITO_USER_POOL_ID', 'ap-south-1_U3JeTevgw')
  vi.stubEnv('VITE_COGNITO_CLIENT_ID', 'client-id')
  vi.resetModules()
})

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('frontend runtime config', () => {
  it('does not expose dev pass outside Vite development mode', async () => {
    vi.stubEnv('VITE_ALLOW_DEV_PASS', 'true')
    vi.stubEnv('MODE', 'production')

    const { CONFIG } = await import('./config')

    expect(CONFIG.ALLOW_DEV_PASS).toBe(false)
  })
})
