import api from './api'

export async function updateJobOperationStatus(jobOperationId, payload) {
  const response = await api.patch(`/job-operations/${jobOperationId}/status/`, payload)
  return response.data
}

export async function planJobOperation(jobOperationId, payload) {
  const response = await api.patch(`/job-operations/${jobOperationId}/plan/`, payload)
  return response.data
}

export async function fetchJobOperationAudit(jobOperationId) {
  const response = await api.get(`/job-operations/${jobOperationId}/audit/`)
  return response.data
}
