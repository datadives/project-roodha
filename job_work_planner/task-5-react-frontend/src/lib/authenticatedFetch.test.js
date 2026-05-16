// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest'

const amplifyAuthMock = vi.hoisted(() => ({
  fetchAuthSession: vi.fn(),
}))

const authMock = vi.hoisted(() => ({
  getLatestAuthContextForRequest: vi.fn(),
  refreshAuthSession: vi.fn(),
}))

vi.mock('aws-amplify/auth', () => amplifyAuthMock)
vi.mock('./auth', () => authMock)
vi.mock('../config', () => ({
  CONFIG: { BASE_URL: 'http://backend.test/api' },
}))

function jsonResponse(status, body, url = 'http://backend.test/api/jobs') {
  return {
    status,
    ok: status >= 200 && status < 300,
    statusText: status === 200 ? 'OK' : 'Error',
    url,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
    text: vi.fn().mockResolvedValue(JSON.stringify(body)),
  }
}

describe('authenticatedFetch secure handshake', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    window.history.pushState({}, '', '/login')
    global.fetch = vi.fn()
    authMock.getLatestAuthContextForRequest.mockResolvedValue({
      token: 'cached-token',
      tenantId: 'tenant-a',
      tenant_id: 'tenant-a',
    })
    amplifyAuthMock.fetchAuthSession.mockResolvedValue({
      tokens: {
        idToken: { toString: () => 'latest-id-token' },
      },
    })
  })

  it('injects the latest ID token and tenant header immediately before backend fetch', async () => {
    global.fetch.mockResolvedValueOnce(jsonResponse(200, { success: true, data: { ok: true } }))
    const { authenticatedFetch } = await import('./authenticatedFetch.js')

    await expect(authenticatedFetch('jobs')).resolves.toEqual({ ok: true })

    expect(global.fetch).toHaveBeenCalledTimes(1)
    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer latest-id-token')
    expect(options.headers['X-Tenant-ID']).toBe('tenant-a')
    console.log('AUTH_FETCH_TOKEN latest=ok tenant_header=ok')
  })

  it('bypasses Cognito/AWS URLs without app auth headers', async () => {
    global.fetch.mockResolvedValueOnce(jsonResponse(200, { challenge: 'ok' }, 'https://cognito-idp.ap-south-1.amazonaws.com/'))
    const { authenticatedFetch } = await import('./authenticatedFetch.js')

    await expect(authenticatedFetch('https://cognito-idp.ap-south-1.amazonaws.com/', { method: 'POST' })).resolves.toEqual({ challenge: 'ok' })

    expect(global.fetch).toHaveBeenCalledWith('https://cognito-idp.ap-south-1.amazonaws.com/', { method: 'POST' })
    console.log('AUTH_FETCH_COGNITO_BYPASS headers=clean')
  })

  it('refreshes once on 401 and purges stale state when the retry is still unauthorized', async () => {
    localStorage.setItem('token', 'stale-token')
    sessionStorage.setItem('cached-route', '/dashboard')
    global.fetch
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
    authMock.refreshAuthSession.mockResolvedValue(null)
    const { authenticatedFetch, APIError } = await import('./authenticatedFetch.js')

    await expect(authenticatedFetch('jobs')).rejects.toBeInstanceOf(APIError)

    expect(authMock.refreshAuthSession).toHaveBeenCalledTimes(1)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    console.log('AUTH_FETCH_401_REFRESH retry=1 purge=ok')
  })
})
