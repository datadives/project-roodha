/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: jobOperationsApi.js
 * 
 * 1) Purpose: Utility library or API client for jobOperationsApi.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

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
