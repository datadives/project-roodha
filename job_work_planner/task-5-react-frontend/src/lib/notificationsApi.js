import api from './api'

export async function fetchNotifications(params = {}) {
  const response = await api.get('/notifications/', { params })
  return response.data
}

export async function markNotificationRead(notificationId) {
  const response = await api.patch(`/notifications/${notificationId}/read/`)
  return response.data
}
