import api from './api'

export async function fetchCustomFields(entityType = '') {
  const response = await api.get('/settings/custom-fields', {
    params: entityType ? { entity_type: entityType } : {},
  })
  return response.data?.fields || []
}

export async function createCustomField(payload) {
  const response = await api.post('/settings/custom-fields', payload)
  return response.data
}

export async function saveCustomFieldValue(payload) {
  const response = await api.post('/settings/custom-fields/values', payload)
  return response.data
}
