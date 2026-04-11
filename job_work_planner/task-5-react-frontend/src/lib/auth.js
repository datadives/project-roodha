import { fetchAuthSession, getCurrentUser, fetchUserAttributes, signIn, signOut, signUp as awsSignUp, confirmSignUp as awsConfirmSignUp, resetPassword as awsResetPassword, confirmResetPassword as awsConfirmResetPassword } from 'aws-amplify/auth'

const DEV_BYPASS_TOKEN = 'test123'
const DEV_BYPASS_USER_KEY = 'roodha:dev-user'
export const DEV_TENANT_ID = 'tenant-123'
const isDevelopment = import.meta.env.MODE === 'development'
const AUTH_CACHE_TTL_MS = 5000
const shouldDebugAuth = import.meta.env.VITE_DEBUG_AUTH === 'true'

let cachedAuthContext = null
let cachedAuthTimestamp = 0
let pendingAuthPromise = null

function logAuthCheck(payload) {
  if (shouldDebugAuth) {
    console.log('Auth Check:', payload)
  }
}

function setCachedAuthContext(authContext) {
  cachedAuthContext = authContext
  cachedAuthTimestamp = Date.now()
  return authContext
}

function clearCachedAuthContext() {
  cachedAuthContext = null
  cachedAuthTimestamp = 0
  pendingAuthPromise = null
}

function getFreshCachedAuthContext() {
  if (!cachedAuthContext) return null
  if (Date.now() - cachedAuthTimestamp > AUTH_CACHE_TTL_MS) return null
  return cachedAuthContext
}

function buildAuthContextFromDevUser(devUser, token = DEV_BYPASS_TOKEN) {
  return {
    user: devUser,
    token,
    user_id: devUser.user_id || devUser.id || null,
    email: devUser.email || null,
    tenant_id: devUser.tenant_id || null,
    role: devUser.user_role || devUser.role || null,
    user_role: devUser.user_role || devUser.role || null,
  }
}

export function getStoredDevAuthContext() {
  if (!isDevelopment) {
    return null
  }

  const token = localStorage.getItem('token')
  const rawDevUser = localStorage.getItem(DEV_BYPASS_USER_KEY)

  if (token !== DEV_BYPASS_TOKEN || !rawDevUser) {
    logAuthCheck({
      token,
      hasUser: Boolean(rawDevUser),
      mode: import.meta.env.MODE,
      source: 'dev-storage-miss',
    })
    return null
  }

  try {
    const devUser = JSON.parse(rawDevUser)
    const authContext = buildAuthContextFromDevUser(devUser, token)
    logAuthCheck({
      token,
      hasUser: true,
      mode: import.meta.env.MODE,
      source: 'dev-storage-hit',
      tenant_id: authContext.tenant_id,
      user_role: authContext.user_role,
      user_id: authContext.user_id,
    })
    return setCachedAuthContext(authContext)
  } catch (error) {
    logAuthCheck({
      token,
      hasUser: true,
      mode: import.meta.env.MODE,
      source: 'dev-storage-invalid',
      error: error?.message,
    })
    return null
  }
}

export async function login(email, password) {
  return signIn({ username: email, password })
}

export async function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem(DEV_BYPASS_USER_KEY)
  clearCachedAuthContext()
  if (isDevelopment) {
    return Promise.resolve()
  }
  return signOut()
}

export function getCachedAuthContextSync() {
  const cached = getFreshCachedAuthContext()
  if (cached) return cached
  return getStoredDevAuthContext()
}

export function storeDevBypassSession(devUser) {
  localStorage.setItem('token', DEV_BYPASS_TOKEN)
  localStorage.setItem(DEV_BYPASS_USER_KEY, JSON.stringify(devUser))
  return setCachedAuthContext(buildAuthContextFromDevUser(devUser))
}

export async function getAuthContext() {
  const cached = getFreshCachedAuthContext()
  if (cached) {
    return cached
  }

  const storedDevAuth = getStoredDevAuthContext()
  if (storedDevAuth) {
    return storedDevAuth
  }

  if (isDevelopment && localStorage.getItem('token') === DEV_BYPASS_TOKEN) {
    logAuthCheck({
      token: localStorage.getItem('token'),
      hasUser: Boolean(localStorage.getItem(DEV_BYPASS_USER_KEY)),
      mode: import.meta.env.MODE,
      source: 'dev-token-without-user',
    })
    const fallbackDevUser = {
      id: 'USER-ROSHAN-DEV',
      user_id: 'USER-ROSHAN-DEV',
      username: 'roshan@test.com',
      email: 'roshan@test.com',
      name: 'Roshan Dev',
      full_name: 'Roshan Dev',
      role: 'ADMIN',
      user_role: 'ADMIN',
      tenant_id: DEV_TENANT_ID,
    }
    return storeDevBypassSession(fallbackDevUser)
  }

  if (pendingAuthPromise) {
    return pendingAuthPromise
  }

  pendingAuthPromise = (async () => {
    try {
      const user = await getCurrentUser()
      const session = await fetchAuthSession()
      const idToken = session.tokens?.idToken?.toString()
      const payload = session.tokens?.idToken?.payload || {}
      let resolvedTenantId = payload['custom:tenant_id'] || payload['tenant_id'] || null
      let resolvedRole =
        payload['custom:user_role'] ||
        payload['user_role'] ||
        payload['cognito:groups']?.[0] ||
        null

      if (!resolvedTenantId || !resolvedRole) {
        const attributes = await fetchUserAttributes().catch(() => null)
        if (!resolvedTenantId) {
          resolvedTenantId = attributes?.['custom:tenant_id'] || attributes?.['tenant_id'] || null
        }
        if (!resolvedRole) {
          resolvedRole = attributes?.['custom:user_role'] || attributes?.['user_role'] || null
        }
      }

      const authContext = {
        user,
        token: idToken,
        user_id: payload["sub"] || user?.userId || null,
        email: payload["email"] || user?.signInDetails?.loginId || null,
        tenant_id: resolvedTenantId,
        role: resolvedRole,
        user_role: resolvedRole,
      }
      logAuthCheck({
        token: authContext.token ? '[cognito-token]' : null,
        hasUser: Boolean(authContext.user),
        mode: import.meta.env.MODE,
        source: 'cognito',
        tenant_id: authContext.tenant_id,
        user_role: authContext.user_role,
        user_id: authContext.user_id,
      })
      return setCachedAuthContext(authContext)
    } catch (error) {
      logAuthCheck({
        token: localStorage.getItem('token'),
        hasUser: Boolean(localStorage.getItem(DEV_BYPASS_USER_KEY)),
        mode: import.meta.env.MODE,
        source: 'cognito-error',
        error: error?.message,
      })
      clearCachedAuthContext()
      throw error
    } finally {
      pendingAuthPromise = null
    }
  })()

  return pendingAuthPromise
}

export async function signUp(params) {
  return awsSignUp(params)
}

export async function confirmSignUp(params) {
  return awsConfirmSignUp(params)
}

export async function resetPassword(params) {
  return awsResetPassword(params)
}

export async function confirmResetPassword(params) {
  return awsConfirmResetPassword(params)
}
