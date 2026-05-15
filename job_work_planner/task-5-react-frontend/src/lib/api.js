/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: api.js
 * 
 * 1) Purpose: Utility library or API client for api.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import axios from 'axios'
import { toast } from 'react-hot-toast'
import { fetchAuthSession } from 'aws-amplify/auth'
import { getLatestAuthContextForRequest, refreshAuthSession } from './auth'
import { CONFIG } from '../config'

const resolvedBaseUrl = CONFIG.BASE_URL
const resolvedTimeout = CONFIG.API_TIMEOUT_MS

const api = axios.create({
  baseURL: resolvedBaseUrl.replace(/\/+$/, ''),
  timeout: Number.isFinite(resolvedTimeout) && resolvedTimeout > 0 ? resolvedTimeout : 30000,
})

let lastErrorToastMessage = ''
let lastErrorToastAt = 0
let authRedirectInProgress = false
const AUTH_REDIRECT_COOLDOWN_MS = 15000
const AUTH_REDIRECT_AT_KEY = 'roodha_auth_redirect_at'

function withTrailingSlash(url) {
  return url 
}

function isUsableToken(token) {
  return (
    typeof token === 'string' &&
    token.trim() &&
    !['undefined', 'null'].includes(token.trim().toLowerCase())
  )
}

function decodeJwtPayload(token) {
  if (!isUsableToken(token)) return {}
  const parts = token.split('.')
  if (parts.length < 2) return {}
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    const decoded = atob(padded)
    return JSON.parse(decoded)
  } catch {
    return {}
  }
}

function deriveTenantIdFromToken(token) {
  const payload = decodeJwtPayload(token)
  const claimTenant =
    payload['custom:tenant_id'] ||
    payload.tenant_id ||
    payload.tenantId
  if (claimTenant) return String(claimTenant)

  const email = payload.email || payload['cognito:username'] || payload.username
  if (!email || typeof email !== 'string') return ''
  const seed = email.split('@', 1)[0] || ''
  return seed.replace(/[^A-Za-z0-9]/g, '').toLowerCase()
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

function showErrorToast(message) {
  const now = Date.now()
  if (message === lastErrorToastMessage && now - lastErrorToastAt < 2500) {
    return
  }
  lastErrorToastMessage = message
  lastErrorToastAt = now
  toast.error(message)
}

function forceReauth() {
  if (authRedirectInProgress) return

  const now = Date.now()
  const lastRedirectAt = Number(sessionStorage.getItem(AUTH_REDIRECT_AT_KEY) || 0)
  if (lastRedirectAt && now - lastRedirectAt < AUTH_REDIRECT_COOLDOWN_MS) {
    return
  }

  try {
    localStorage.removeItem('token')
    localStorage.removeItem('roodha_auth_context')
  } catch {
    // ignore storage errors
  }

  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
    authRedirectInProgress = true
    sessionStorage.setItem(AUTH_REDIRECT_AT_KEY, String(now))
    window.location.replace('/login')
  }
}

api.interceptors.request.use(async (config) => {
  config.url = withTrailingSlash(config.url)
  const auth = await getRequestAuthContext()
  const token = typeof auth?.token === 'string' ? auth.token.trim() : ''
  
  if (isUsableToken(token)) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const tenantId = auth?.tenantId || auth?.tenant_id || deriveTenantIdFromToken(token)
  if (tenantId) {
    config.headers['X-Tenant-ID'] = tenantId
  }
  return config
})

function describeErrorDetail(detail) {
  if (!detail) return 'Network error'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => describeErrorDetail(item)).filter(Boolean).join(', ')
  }
  if (typeof detail === 'object') {
    return detail.error || detail.message || detail.detail || 'Request failed'
  }
  return String(detail)
}

function describeRequestError(error) {
  if (error?.message === 'Network Error' || (!error?.response && !error?.code)) {
    return 'Unable to connect to the server. Please try again.'
  }
  if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
    return 'The request timed out. Please try again.'
  }
  return describeErrorDetail(error?.response?.data?.detail || error?.response?.data || error?.message)
}

api.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && typeof payload.success === 'boolean') {
      if (!payload.success) {
        const message = payload.message || 'Request failed'
        showErrorToast(message)
        return Promise.reject(
          Object.assign(new Error(message), {
            response: {
              ...response,
              data: payload,
            },
          }),
        )
      }
      response.meta = { message: payload.message || 'OK' }
      response.data = payload.data
    }
    return response
  },
  async (error) => {
    if (error?.response?.status === 401) {
      const requestConfig = error?.config || {}
      const canRetry = !requestConfig._retriedAfterRefresh
      if (canRetry) {
        try {
          await refreshAuthSession()
          requestConfig._retriedAfterRefresh = true
          return api.request(requestConfig)
        } catch {
          // fall through to user-facing unauthorized toast below
        }
      }
      const detailMessage =
        error?.response?.data?.detail ||
        error?.response?.data?.message ||
        'Session expired. Please sign in again.'
      const detailText = typeof detailMessage === 'string' ? detailMessage : 'Session expired. Please sign in again.'
      const isBackendDnsValidationIssue =
        /security validation failed/i.test(detailText) &&
        /name or service not known|temporary failure in name resolution|getaddrinfo/i.test(detailText)

      showErrorToast(detailText)
      if (!isBackendDnsValidationIssue) {
        forceReauth()
      }
      return Promise.reject(error)
    }
    if (error?.response?.status === 403) {
      showErrorToast('Your role or access changed. Please sign in again.')
      forceReauth()
      return Promise.reject(error)
    }
    showErrorToast(describeRequestError(error))
    return Promise.reject(error)
  },
)

export default api
