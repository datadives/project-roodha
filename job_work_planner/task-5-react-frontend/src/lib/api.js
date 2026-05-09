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
import { getLatestAuthContextForRequest } from './auth'
import { CONFIG } from '../config'

const resolvedBaseUrl = CONFIG.BASE_URL
const resolvedTimeout = CONFIG.API_TIMEOUT_MS

const api = axios.create({
  baseURL: resolvedBaseUrl.replace(/\/+$/, ''),
  timeout: Number.isFinite(resolvedTimeout) && resolvedTimeout > 0 ? resolvedTimeout : 30000,
})

let lastErrorToastMessage = ''
let lastErrorToastAt = 0

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

api.interceptors.request.use(async (config) => {
  config.url = withTrailingSlash(config.url)
  const auth = await getRequestAuthContext()
  const token = typeof auth?.token === 'string' ? auth.token.trim() : ''
  
  if (isUsableToken(token)) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const tenantId = auth?.tenantId || auth?.tenant_id
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
    return 'Connection lost. Please check if the server is running.'
  }
  if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
    return 'Request timed out. Make sure the backend is running, DATABASE_URL is valid, and try again in a few seconds.'
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
      showErrorToast('This request is not authorized for the current session.')
      return Promise.reject(error)
    }
    showErrorToast(describeRequestError(error))
    return Promise.reject(error)
  },
)

export default api
