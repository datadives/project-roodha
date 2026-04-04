import axios from 'axios'
import { toast } from 'react-hot-toast'
import { getAuthContext } from './auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 15000,
})

api.interceptors.request.use(async (config) => {
  const auth = await getAuthContext().catch(() => null)
  if (auth?.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && typeof payload.success === 'boolean') {
      if (!payload.success) {
        toast.error(payload.message || 'Request failed')
      }
      response.data = payload.data
    }
    return response
  },
  (error) => {
    toast.error(error?.response?.data?.detail || error.message || 'Network error')
    return Promise.reject(error)
  },
)

export default api
