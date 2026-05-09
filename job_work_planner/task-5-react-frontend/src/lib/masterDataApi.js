/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: masterDataApi.js
 * 
 * 1) Purpose: Utility library or API client for masterDataApi.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import api from './api'

function normalizeCollection(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.data)) return payload.data
  return []
}

export async function fetchCustomers(includeInactive = false) {
  const response = await api.get('/master-data/customers', {
    params: { include_inactive: includeInactive },
  })
  return normalizeCollection(response.data)
}

export async function createCustomer(payload) {
  const response = await api.post('/master-data/customers', payload)
  return response.data
}

export async function updateCustomer(customerId, payload) {
  const response = await api.patch(`/master-data/customers/${customerId}`, payload)
  return response.data
}

export async function deleteCustomer(customerId) {
  const response = await api.delete(`/master-data/customers/${customerId}`)
  return response.data
}

export async function fetchMachines() {
  const response = await api.get('/master-data/machines')
  return normalizeCollection(response.data)
}

export async function createMachine(payload) {
  const response = await api.post('/master-data/machines', payload)
  return response.data
}

export async function updateMachine(machineId, payload) {
  const response = await api.patch(`/master-data/machines/${machineId}`, payload)
  return response.data
}

export async function fetchParts() {
  const response = await api.get('/master-data/parts')
  return normalizeCollection(response.data)
}

export async function fetchPartById(partId) {
  const response = await api.get(`/master-data/parts/${partId}`)
  return response.data
}

export async function createPart(payload) {
  const response = await api.post('/master-data/parts', payload)
  return response.data
}

export async function updatePart(partId, payload) {
  const response = await api.patch(`/master-data/parts/${partId}`, payload)
  return response.data
}

export async function deletePart(partId) {
  const response = await api.delete(`/master-data/parts/${partId}`)
  return response.data
}

export async function fetchShifts() {
  const response = await api.get('/master-data/shifts')
  return normalizeCollection(response.data)
}

export async function createShift(payload) {
  const response = await api.post('/master-data/shifts', payload)
  return response.data
}

export async function updateShift(shiftId, payload) {
  const response = await api.patch(`/master-data/shifts/${shiftId}`, payload)
  return response.data
}

export async function deleteShift(shiftId) {
  const response = await api.delete(`/master-data/shifts/${shiftId}`)
  return response.data
}

export async function fetchWorkers(includeInactive = true) {
  const response = await api.get('/master-data/workers', {
    params: { include_inactive: includeInactive },
  })
  return normalizeCollection(response.data)
}

export async function createWorker(payload) {
  const response = await api.post('/master-data/workers', payload)
  return response.data
}

export async function updateWorker(workerId, payload) {
  const response = await api.patch(`/master-data/workers/${workerId}`, payload)
  return response.data
}

export async function deleteWorker(workerId) {
  const response = await api.delete(`/master-data/workers/${workerId}`)
  return response.data
}
