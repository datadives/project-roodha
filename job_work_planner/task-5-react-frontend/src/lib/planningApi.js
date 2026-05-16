/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: planningApi.js
 * 
 * 1) Purpose: Utility library or API client for planningApi.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import api from './api'

export async function fetchPlanningCalendar(params = {}) {
  const response = await api.get('/planning', { params })
  return response.data
}

export async function previewAutoSchedule(payload = {}) {
  const response = await api.post('/planning/auto-schedule/preview', payload)
  return response.data
}

export async function applyAutoSchedule(suggestions = []) {
  const response = await api.post('/planning/auto-schedule/apply', { suggestions })
  return response.data
}

export async function fetchWorklist(params = {}) {
  const response = await api.get('/worklist', { params })
  return response.data
}
