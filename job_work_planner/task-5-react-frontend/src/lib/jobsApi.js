import api from './api'

export async function createJob(payload) {
  const response = await api.post('/jobs', payload)
  return response.data
}

export async function fetchJobs(params = {}) {
  const response = await api.get('/jobs', { params })
  return response.data
}
