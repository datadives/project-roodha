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
import { getLatestAuthContextForRequest } from './auth'
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


interface FetchOptions extends RequestInit {
  transformPayload?: boolean
  transformResponse?: boolean
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

/**
 * Resilient authenticated fetch utility with automated case transformation.
 */
export async function authenticatedFetch<T = any>(
  endpoint: string, 
  options: FetchOptions = {}
): Promise<T> {
  const { transformPayload = true, transformResponse = true, ...fetchOptions } = options
  
  const url = endpoint.startsWith('http') 
    ? endpoint 
    : `${BASE_URL.replace(/\/+$/, '')}/${endpoint.replace(/^\/+/, '')}`
  
  const auth = await getRequestAuthContext()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers,
  })

  const token = typeof auth?.token === 'string' ? auth.token.trim() : ''
  if (isUsableToken(token)) {
    headers.set('Authorization', `Bearer ${token}`)
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
