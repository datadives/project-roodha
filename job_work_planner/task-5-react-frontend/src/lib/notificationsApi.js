/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: notificationsApi.js
 * 
 * 1) Purpose: Utility library or API client for notificationsApi.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import api from './api'

export async function fetchNotifications(params = {}) {
  const response = await api.get('/notifications', { params })
  return response.data
}

export async function markNotificationRead(notificationId) {
  const response = await api.patch(`/notifications/${notificationId}/read`)
  return response.data
}
