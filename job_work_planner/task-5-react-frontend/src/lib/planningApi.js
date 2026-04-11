import api from './api'

export async function fetchPlanningCalendar(params = {}) {
  const response = await api.get('/planning/', { params })
  return response.data
}
