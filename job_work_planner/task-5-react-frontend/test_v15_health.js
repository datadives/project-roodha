/*
 * JobWork Planner V1.5 local health probe.
 *
 * Run this in the browser console while logged in, or include it temporarily
 * from the Vite app. It uses the active browser localStorage token.
 */

const API_BASE_URL = 'http://localhost:8000/api'

function readStoredJson(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function getStoredAuth() {
  const storedContext = readStoredJson('roodha_auth_context') || {}
  const token = localStorage.getItem('token') || storedContext.token || ''
  const tenantId =
    storedContext.tenant_id ||
    storedContext.tenantId ||
    localStorage.getItem('tenant_id') ||
    localStorage.getItem('tenantId') ||
    ''

  return {
    token: String(token || '').trim(),
    tenantId: String(tenantId || '').trim(),
  }
}

async function probe(label, path, options = {}) {
  const { token, tenantId } = getStoredAuth()
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }

  if (token && !['undefined', 'null'].includes(token.toLowerCase())) {
    headers.Authorization = `Bearer ${token}`
  }
  if (tenantId) {
    headers['X-Tenant-ID'] = tenantId
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
    const text = await response.text()
    let payload = text
    try {
      payload = text ? JSON.parse(text) : null
    } catch {
      // Keep raw text for debugging.
    }

    if (response.ok) {
      console.log(`\u2705 PASS ${label}`, { status: response.status, payload })
      return true
    }

    console.error(`\u274C FAIL ${label}`, { status: response.status, payload })
    return false
  } catch (error) {
    console.error(`\u274C FAIL ${label}`, error)
    return false
  }
}

async function runV15HealthProbe() {
  console.log('Roodha V1.5 health probe starting...')
  const results = [
    await probe('User profile /api/users/me', '/users/me'),
    await probe('Kanban /api/kanban', '/kanban'),
    await probe('Machine load /api/planning/machine-load', '/planning/machine-load'),
  ]
  const passed = results.filter(Boolean).length
  console.log(`V1.5 health probe finished: ${passed}/${results.length} passed`)
  return results
}

if (typeof window !== 'undefined') {
  window.runV15HealthProbe = runV15HealthProbe
}

runV15HealthProbe()
