import api from './api'

export async function createJob(payload) {
  const response = await api.post('/jobs/', payload)
  return response.data
}

export async function fetchJobs(params = {}) {
  const response = await api.get('/jobs/', { params })
  return response.data
}

export async function fetchJobById(jobId) {
  const response = await api.get(`/jobs/${jobId}/`)
  return response.data
}

export async function fetchJobAudit(jobId) {
  const response = await api.get(`/jobs/${jobId}/audit/`)
  return response.data
}

export async function fetchJobCostSummary(jobId) {
  const response = await api.get(`/jobs/${jobId}/cost-summary/`)
  return response.data
}

export async function recalculateJobCost(jobId) {
  const response = await api.post(`/jobs/${jobId}/recalculate-cost/`)
  return response.data
}

export async function downloadJobInvoice(jobId) {
  const response = await api.get(`/jobs/${jobId}/download-invoice/`, { responseType: 'blob' })
  return response.data // Blob
}

export async function setJobQuotedPrice(jobId, quotedPrice) {
  const response = await api.patch(`/jobs/${jobId}/quoted-price/`, { quoted_price: quotedPrice })
  return response.data
}
