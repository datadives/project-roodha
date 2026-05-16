/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: authenticatedFetch.ts
 * 
 * 1) Purpose: Utility library or API client for authenticatedFetch.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { fetchAuthSession } from 'aws-amplify/auth'
import { getLatestAuthContextForRequest, refreshAuthSession } from './auth'
import { keysToCamel, keysToSnake } from './caseTransformer'
import { CONFIG } from '../config'

export class APIError extends Error {
  status: number
  detail: any
  
  constructor(message: string, status: number, detail?: any) {
    super(message)
    this.name = 'APIError'
    this.status = status
    this.detail = detail
  }
}

const BASE_URL = CONFIG.BASE_URL
const RETRY_DELAY_MS = 2_000


interface FetchOptions extends RequestInit {
  transformPayload?: boolean
  transformResponse?: boolean
  params?: Record<string, unknown>
}

function isUsableToken(token: unknown): token is string {
  return (
    typeof token === 'string' &&
    Boolean(token.trim()) &&
    !['undefined', 'null'].includes(token.trim().toLowerCase())
  )
}

async function getRequestAuthContext(): Promise<any> {
  const auth = await getLatestAuthContextForRequest().catch(() => null)

  try {
    const session = await fetchAuthSession()
    const idToken = session.tokens?.idToken?.toString()
    if (isUsableToken(idToken)) {
      return {
        ...auth,
        token: idToken.trim(),
      }
    }
  } catch {
    // Fall back to the recovered auth context below.
  }

  return auth
}

function clearStaleAuthAndRedirect() {
  try {
    localStorage.clear()
  } catch {
    // Ignore storage access failures.
  }
  try {
    sessionStorage.clear()
  } catch {
    // Ignore storage access failures.
  }
  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
    window.location.replace('/login')
  }
}

function decodeJwtPayload(token: string): Record<string, any> {
  if (!isUsableToken(token)) return {}
  const parts = token.split('.')
  if (parts.length < 2) return {}
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    return JSON.parse(atob(padded))
  } catch {
    return {}
  }
}

function deriveTenantIdFromToken(token: string): string {
  const payload = decodeJwtPayload(token)
  return String(payload['custom:tenant_id'] || payload.tenant_id || payload.tenantId || '')
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Resilient authenticated fetch utility with automated case transformation.
 */
export async function authenticatedFetch<T = any>(
  endpoint: string, 
  options: FetchOptions = {},
  retryCount = 0,
): Promise<T> {
  const { transformPayload = true, transformResponse = true, params, ...fetchOptions } = options
  
  const baseUrl = endpoint.startsWith('http') 
    ? endpoint 
    : `${BASE_URL.replace(/\/+$/, '')}/${endpoint.replace(/^\/+/, '')}`

  const query = new URLSearchParams()
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, String(value))
    }
  })
  const url = query.toString()
    ? `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}${query.toString()}`
    : baseUrl

  if (url.includes('amazonaws.com') || url.includes('amazoncognito.com')) {
    const response = await fetch(url, fetchOptions)
    return response.json() as Promise<T>
  }
  
  const auth = await getRequestAuthContext()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers,
  })

  const token = typeof auth?.token === 'string' ? auth.token.trim() : ''
  if (isUsableToken(token)) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const tenantId = auth?.tenantId || auth?.tenant_id || deriveTenantIdFromToken(token)
  if (tenantId) {
    headers.set('X-Tenant-ID', String(tenantId))
  }

  // 1. Transform payload to snake_case for backend
  let body = fetchOptions.body
  if (transformPayload && body && typeof body === 'string') {
    try {
      const parsedBody = JSON.parse(body)
      body = JSON.stringify(keysToSnake(parsedBody))
    } catch {
      // Not JSON, leave as is
    }
  }

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      body,
    })
    
    if (response.status === 204) {
      return null as any
    }

    let data = await response.json().catch(() => ({}))

    if (response.status === 401 && retryCount === 0) {
      try {
        await refreshAuthSession()
      } catch {
        // Retry once using whatever token recovery can provide.
      }
      return authenticatedFetch<T>(endpoint, options, 1)
    }

    if (response.status === 401) {
      clearStaleAuthAndRedirect()
      throw new APIError('This session expired. Please sign in again.', response.status, data)
    }

    if (response.status === 403) {
      clearStaleAuthAndRedirect()
      throw new APIError('Your role or access changed. Please sign in again.', response.status, data)
    }

    if (response.status >= 500 && retryCount === 0) {
      await sleep(RETRY_DELAY_MS)
      return authenticatedFetch<T>(endpoint, options, 1)
    }

    if (!response.ok) {
      const errorMsg = data?.detail || data?.message || response.statusText || 'Request failed'
      throw new APIError(errorMsg, response.status, data)
    }

    // Handle legacy wrapper
    if (data.success !== undefined) {
      if (!data.success) {
        throw new APIError(data.message || 'API failure', response.status, data)
      }
      data = data.data
    }

    // 2. Transform response to camelCase for frontend
    return transformResponse ? keysToCamel(data) : data
  } catch (error) {
    if (error instanceof APIError) throw error
    console.error('[authenticatedFetch] Error:', error)
    throw new APIError('Connection lost. Please check your network.', 0, error)
  }
}

export default authenticatedFetch
