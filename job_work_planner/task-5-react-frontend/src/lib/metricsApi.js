import api from './api'

export async function fetchWipMetrics(params = {}) {
  const response = await api.get('/metrics/wip', { params })
  return response.data
}
