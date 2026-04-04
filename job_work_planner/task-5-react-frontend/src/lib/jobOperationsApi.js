import api from './api'

export async function updateJobOperationStatus(jobOperationId, payload) {
  const response = await api.patch(`/job-operations/${jobOperationId}/status`, payload)
  return response.data
}
