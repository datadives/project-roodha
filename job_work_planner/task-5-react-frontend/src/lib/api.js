import axios from 'axios'
import { toast } from 'react-hot-toast'
import { getAuthContext, getCachedAuthContextSync } from './auth'

const resolvedBaseUrl =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.MODE === 'development' ? '/api' : '')
const resolvedTimeout = Number(import.meta.env.VITE_API_TIMEOUT_MS || 30000)

const api = axios.create({
  baseURL: resolvedBaseUrl.replace(/\/+$/, ''),
  timeout: Number.isFinite(resolvedTimeout) && resolvedTimeout > 0 ? resolvedTimeout : 30000,
})

let lastErrorToastMessage = ''
let lastErrorToastAt = 0

function withTrailingSlash(url) {
  if (!url || typeof url !== 'string') return url
  if (/^https?:\/\//i.test(url)) return url
  if (url === '/') return url
  return url.endsWith('/') ? url : `${url}/`
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
  const syncAuth = getCachedAuthContextSync()
  const auth = syncAuth || (await getAuthContext().catch(() => null))
  if (auth?.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
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
  (error) => {
    showErrorToast(describeRequestError(error))
    return Promise.reject(error)
  },
)

export default api
