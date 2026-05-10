/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: metricsApi.js
 * 
 * 1) Purpose: Utility library or API client for metricsApi.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { authenticatedFetch } from './authenticatedFetch'

export async function fetchWipMetrics(params = {}) {
  return await authenticatedFetch('metrics/wip', { params })
}

export async function fetchBottleneckMetrics(params = {}) {
  return await authenticatedFetch('metrics/bottlenecks', { params })
}

export async function fetchLateJobsMetrics() {
  return await authenticatedFetch('metrics/late-jobs')
}

export async function fetchCostingSummary() {
  return await authenticatedFetch('metrics/costing-summary')
}

export async function fetchMachineLoadMetrics() {
  return await authenticatedFetch('planning/machine-load')
}
