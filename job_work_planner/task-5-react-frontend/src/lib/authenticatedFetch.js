/**
 * PROJECT ROODHA - SECURE API CLIENT
 * FILE: authenticatedFetch.js
 * PURPOSE: Resilient API client with automatic JWT injection, X-Tenant-ID enforcement,
 *          and industrial-grade timeout/retry logic for factory environments.
 */

import { fetchAuthSession } from 'aws-amplify/auth'
import { getLatestAuthContextForRequest, refreshAuthSession } from './auth'
import { CONFIG } from '../config'

// ---------------------------------------------------------
// --- CUSTOM ERROR DEFINITIONS ---
// ---------------------------------------------------------

export class APIError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'APIError'
    this.status = status
    this.detail = detail
  }
}

/**
 * Custom timeout error thrown when the server doesn't respond in time.
 * Appears in UI as a "Machine Link Timeout" signal.
 */
export class TimeoutError extends APIError {
  constructor(url, timeoutMs) {
    super(`Machine Link Timeout: No response from server after ${timeoutMs / 1000}s (${url})`, 0, null)
    this.name = 'TimeoutError'
    this.isTimeout = true
  }
}

// ---------------------------------------------------------
// --- RESILIENCE CONFIGURATION ---
// ---------------------------------------------------------

const BASE_URL = CONFIG.BASE_URL
const DEFAULT_TIMEOUT_MS = 10_000
const RETRY_DELAY_MS = 2_000

// ---------------------------------------------------------
// --- NETWORK UTILITIES ---
// ---------------------------------------------------------

function fetchWithTimeout(url, options, timeoutMs = DEFAULT_TIMEOUT_MS) {
  /** Races a fetch against a timeout to prevent UI hang in low-connectivity zones. */
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  return fetch(url, { ...options, signal: controller.signal })
    .then((response) => {
      clearTimeout(timer)
      return response
    })
    .catch((error) => {
      clearTimeout(timer)
      if (error.name === 'AbortError') {
        throw new TimeoutError(url, timeoutMs)
      }
      throw error
    })
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function appendQueryParams(url, params) {
  if (!params || typeof params !== 'object') return url

  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined && item !== null && item !== '') {
          query.append(key, String(item))
        }
      })
      return
    }
    query.append(key, String(value))
  })

  const queryString = query.toString()
  if (!queryString) return url
  return `${url}${url.includes('?') ? '&' : '?'}${queryString}`
}

function buildRequestUrl(endpoint, params) {
  const baseUrl = endpoint.startsWith('http')
    ? endpoint
    : `${BASE_URL.replace(/\/+$/, '')}/${endpoint.replace(/^\/+/, '')}`

  return appendQueryParams(baseUrl, params)
}

function toCamelCase(key) {
  return key.replace(/[_-]([a-z])/gi, (_match, char) => char.toUpperCase())
}

function camelizeKeys(obj) {
  if (Array.isArray(obj)) {
    return obj.map((item) => camelizeKeys(item))
  }

  if (obj !== null && Object.prototype.toString.call(obj) === '[object Object]') {
    return Object.keys(obj).reduce((result, key) => {
      result[toCamelCase(key)] = camelizeKeys(obj[key])
      return result
    }, {})
  }

  return obj
}

function shouldCamelizeResponse(responseUrl = '') {
  return responseUrl.includes('/api/')
}

async function readResponseData(response, options = {}) {
  if (response.status === 204) return null
  if (options.transformResponse === false) return response

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return response.json().catch(() => null)
  }

  return response.text().catch(() => '')
}

// ---------------------------------------------------------
// --- SECURITY & CONTEXT INJECTION ---
// ---------------------------------------------------------

function isUsableToken(token) {
  return (
    typeof token === 'string' &&
    token.trim() &&
    !['undefined', 'null'].includes(token.trim().toLowerCase())
  )
}

async function getRequestAuthContext() {
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

async function buildHeaders(overrides = {}) {
  /**
   * Injects required security headers including Authorization (JWT) 
   * and X-Tenant-ID for backend isolation verification.
   */
  const auth = await getRequestAuthContext()

  const tenantId = auth?.tenantId || auth?.tenant_id || ''
  const token = typeof auth?.token === 'string' ? auth.token.trim() : ''
  const headers = {
    'Content-Type': 'application/json',
    ...overrides,
  }
  if (isUsableToken(token)) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  // --- MULTI-TENANCY SHIELD ---
  // Mandatory header for backend RLS consistency check.
  if (tenantId) {
    headers['X-Tenant-ID'] = tenantId
  }
  
  return { headers, auth }
}

async function executeRequest(url, fetchOptions, responseOptions = {}) {
  const response = await fetchWithTimeout(url, fetchOptions)
  const data = await readResponseData(response, responseOptions)
  return { response, data }
}

// ---------------------------------------------------------
// --- RESILIENT FETCH IMPLEMENTATION ---
// ---------------------------------------------------------

export async function authenticatedFetch(endpoint, options = {}, _retryCount = 0) {
  const { params, ...requestOptions } = options
  const url = buildRequestUrl(endpoint, params)

  const isCognito = url.includes('amazonaws.com') || url.includes('amazoncognito.com')
  if (isCognito) {
    return fetch(url, requestOptions).then((res) => res.json())
  }

  try {
    const { headers } = await buildHeaders(requestOptions.headers)
    const fetchOptions = { ...requestOptions, headers }

    let response, data
    try {
      ;({ response, data } = await executeRequest(url, fetchOptions))
    } catch (networkError) {
      // --- RESILIENCE LOGIC ---
      // Automatic retry on network failure or timeout
      if (_retryCount === 0) {
        await sleep(RETRY_DELAY_MS)
        return authenticatedFetch(endpoint, options, 1)
      }
      throw new APIError(
        networkError.isTimeout
          ? networkError.message
          : `Connection lost while calling ${url}. Check that the FastAPI server is running on port 8000 and CORS allows this frontend port.`,
        0, networkError
      )
    }

    // --- AUTOMATIC AUTH REFRESH ---
    if (response.status === 401 && _retryCount === 0) {
      try {
        await refreshAuthSession()
      } catch {
        // Fall through to throw 401 if refresh fails
      }
      return authenticatedFetch(endpoint, options, 1)
    }

    if (response.status === 401) {
      throw new APIError('This feed is not authorized for the current session. Please refresh or sign in again if all feeds fail.', 401, data)
    }

    // --- 5xx SERVER RETRY ---
    if (response.status >= 500 && _retryCount === 0) {
      await sleep(RETRY_DELAY_MS)
      return authenticatedFetch(endpoint, options, 1)
    }

    if (!response.ok) {
      const errorMsg = data?.detail || data?.message || response.statusText || 'Request failed'
      throw new APIError(errorMsg, response.status, data)
    }

    const shouldCamelize = shouldCamelizeResponse(response.url)

    // Handle standard API response wrapping { success, data, message }
    if (typeof data?.success === 'boolean') {
      if (!data.success) {
        throw new APIError(data.message || 'API Logic Failure', response.status, data)
      }
      return shouldCamelize ? camelizeKeys(data.data) : data.data
    }

    return shouldCamelize ? camelizeKeys(data) : data
  } catch (error) {
    if (error instanceof APIError) throw error
    console.error('[Fetch] Fatal unexpected error:', error)
    throw new APIError('Connection lost. Please check your network.', 0, error)
  }
}

export default authenticatedFetch
