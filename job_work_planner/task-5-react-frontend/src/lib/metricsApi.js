import api from './api'

export async function fetchWipMetrics(params = {}) {
  const response = await api.get('/metrics/wip/', { params })
  return response.data
}

export async function fetchBottleneckMetrics(params = {}) {
  const response = await api.get('/metrics/bottlenecks/', { params })
  return response.data
}

export async function fetchLateJobsMetrics() {
  const response = await api.get('/metrics/late-jobs/')
  return response.data
}

export async function fetchCostingSummary() {
  const response = await api.get('/metrics/costing-summary/')
  return response.data
}
