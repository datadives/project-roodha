import { getAuthContext } from './auth'

/**
 * Standardized error for authenticated fetch failures.
 */
export class APIError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'APIError'
    this.status = status
    this.detail = detail
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

/**
 * Resilient authenticated fetch utility.
 * - Injects Cognito JWT automatically.
 * - Handles token refresh via getAuthContext.
 * - Parses JSON and handles HTTP errors gracefully.
 */
export async function authenticatedFetch(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL.replace(/\/+$/, '')}/${endpoint.replace(/^\/+/, '')}`
  
  const auth = await getAuthContext()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (auth?.token) {
    headers['Authorization'] = `Bearer ${auth.token}`
  }

  const fetchOptions = {
    ...options,
    headers,
  }

  try {
    const response = await fetch(url, fetchOptions)
    
    // Handle 204 No Content
    if (response.status === 204) {
      return null
    }

    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      const errorMsg = data?.detail || data?.message || response.statusText || 'Request failed'
      throw new APIError(errorMsg, response.status, data)
    }

    // Handle the backend's standard { success, data, message } wrapper if present
    if (typeof data.success === 'boolean') {
      if (!data.success) {
        throw new APIError(data.message || 'Legacy API failure', response.status, data)
      }
      return data.data
    }

    return data
  } catch (error) {
    if (error instanceof APIError) throw error
    
    // Handle network errors
    console.error('[authenticatedFetch] Network Error:', error)
    throw new APIError('Connection lost. Please check your network.', 0, error)
  }
}

export default authenticatedFetch
