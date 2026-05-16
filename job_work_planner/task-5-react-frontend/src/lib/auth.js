/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: auth.js
 * 
 * 1) Purpose: Utility library or API client for auth.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { fetchAuthSession, getCurrentUser, fetchUserAttributes, signIn, signOut, confirmSignIn, signUp as awsSignUp, confirmSignUp as awsConfirmSignUp, resendSignUpCode as awsResendSignUpCode, resetPassword as awsResetPassword, confirmResetPassword as awsConfirmResetPassword } from 'aws-amplify/auth'
import { CONFIG } from '../config'

const DEV_BYPASS_TOKEN = CONFIG.DEV_BYPASS_TOKEN || 'test123'
const DEV_PASS_TOKEN = CONFIG.DEV_PASS_TOKEN || 'roodha-dev-test-123'

const DEV_BYPASS_USER_KEY = 'roodha:dev-user'
export const DEV_TENANT_ID = CONFIG.DEV_TENANT_ID
const isDevelopment = CONFIG.IS_DEV
const allowDevPass = CONFIG.ALLOW_DEV_PASS
const API_BASE_URL = CONFIG.BASE_URL
const AUTH_CACHE_TTL_MS = 5000
const ROODHA_STORAGE_KEY = 'roodha_auth_context'
const ROODHA_PENDING_SIGNUP_KEY = 'roodha_pending_signup'

let cachedAuthContext = null
let cachedAuthTimestamp = 0
let pendingAuthPromise = null

const COGNITO_ERROR_MESSAGES = {
  default: {
    AliasExistsException: 'An account already exists with this email or phone number.',
    CodeMismatchException: 'Invalid verification code.',
    ExpiredCodeException: 'Verification code expired. Request a new code.',
    InvalidParameterException: 'Invalid authentication request. Check email format, password policy, and Cognito user-pool attribute configuration.',
    InvalidPasswordException: 'Password does not meet the required security policy.',
    LimitExceededException: 'Attempt limit exceeded. Try again later.',
    NotAuthorizedException: 'Authentication request is not authorized for this operation.',
    TooManyFailedAttemptsException: 'Too many failed attempts. Try again later.',
    TooManyRequestsException: 'Too many requests. Try again later.',
    UserNotConfirmedException: 'Account is not confirmed. Check your email for the confirmation code.',
    UserNotFoundException: 'No verified account was found for this identity. Create an account and verify the email OTP first.',
    UsernameExistsException: 'An account already exists for this identity.',
    PasswordResetRequiredException: 'Cognito requires a password reset before this user can sign in.',
    NewPasswordRequiredException: 'Cognito requires a new password before this user can sign in.',
    ForceChangePasswordException: 'Cognito has this user in FORCE_CHANGE_PASSWORD state.',
  },
  login: {
    NotAuthorizedException: 'Incorrect username or password.',
    PasswordResetRequiredException: 'Cognito requires a password reset before this user can sign in.',
    NewPasswordRequiredException: 'Cognito requires a new password before this user can sign in.',
    ForceChangePasswordException: 'Cognito has this user in FORCE_CHANGE_PASSWORD state.',
  },
  signUp: {
    NotAuthorizedException: 'Account creation is not enabled for this Cognito app client or user pool. Enable self-service sign-up in AWS Cognito.',
  },
  confirmSignUp: {
    NotAuthorizedException: 'OTP verification is not allowed for this account right now. Request a fresh OTP and try again.',
  },
  resendSignUpCode: {
    NotAuthorizedException: 'This account may already be verified. Try signing in with your email and password instead of registering again.',
  },
  resetPassword: {
    NotAuthorizedException: 'Password recovery is not enabled for this account right now.',
    InvalidParameterException: 'Password recovery is not available until this account is confirmed. Verify the email OTP first.',
  },
}

function resolveCognitoMessage(code, operation, rawMessage) {
  const scopedMessages = COGNITO_ERROR_MESSAGES[operation] || {}
  return (
    scopedMessages[code] ||
    COGNITO_ERROR_MESSAGES.default[code] ||
    rawMessage
  )
}

function normalizeCognitoError(error, operation = 'default') {
  const code = error?.name || error?.code || error?.__type || 'CognitoAuthError'
  const rawMessage = error?.message || ''
  const isRawTransportError = /\b400\b|bad request|network error|failed to fetch/i.test(rawMessage)
  const resolvedMessage = resolveCognitoMessage(code, operation, rawMessage)
  const message =
    resolvedMessage ||
    (isRawTransportError ? 'Authentication request failed. Check your credentials and try again.' : rawMessage) ||
    'Authentication request failed.'

  return {
    code,
    name: code,
    message,
    userMessage: message,
    rawMessage,
    originalError: error,
  }
}

function throwCognitoError(error, operation = 'default') {
  throw normalizeCognitoError(error, operation)
}

function decodeJwtPayload(token) {
  if (!token || typeof token !== 'string') {
    return {}
  }

  const [, payload] = token.split('.')
  if (!payload) {
    return {}
  }

  try {
    const normalizedPayload = payload.replace(/-/g, '+').replace(/_/g, '/')
    const paddedPayload = normalizedPayload.padEnd(normalizedPayload.length + ((4 - (normalizedPayload.length % 4)) % 4), '=')
    const decoded =
      typeof atob === 'function'
        ? atob(paddedPayload)
        : Buffer.from(paddedPayload, 'base64').toString('binary')
    const json = decodeURIComponent(
      decoded
        .split('')
        .map((char) => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`)
        .join('')
    )
    return JSON.parse(json)
  } catch {
    return {}
  }
}

function normalizeRoodhaRole(role) {
  const normalizedRole = String(role || '').trim().toUpperCase()
  if (['OWNER', 'SUPERVISOR', 'OPERATOR'].includes(normalizedRole)) {
    return normalizedRole
  }
  return 'OPERATOR'
}

function deriveTenantIdFromIdentity(identity) {
  const seed = String(identity || '').split('@', 1)[0]
  return seed.replace(/[^A-Za-z0-9]/g, '').toLowerCase() || null
}

function getPendingSignUpProfile() {
  if (typeof localStorage === 'undefined') {
    return null
  }

  try {
    const raw = localStorage.getItem(ROODHA_PENDING_SIGNUP_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function setPendingSignUpProfile(profile) {
  if (typeof localStorage === 'undefined') {
    return null
  }

  if (!profile) {
    localStorage.removeItem(ROODHA_PENDING_SIGNUP_KEY)
    return null
  }

  localStorage.setItem(ROODHA_PENDING_SIGNUP_KEY, JSON.stringify(profile))
  return profile
}

function normalizeCognitoUsername(identity) {
  const username = String(identity || '').trim()
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(username)) {
    return username.toLowerCase()
  }
  return /^\d{10}$/.test(username) ? `+91${username}` : username
}

function buildRawCognitoState({ user = null, session = null, payload = null, attributes = null } = {}) {
  return {
    cognitoUser: user,
    cognitoSession: session,
    cognitoTokenPayload: payload,
    cognitoUserAttributes: attributes,
  }
}

export function slugifyTenantId(organizationName) {
  return String(organizationName || '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w-]+/g, '')
    .replace(/--+/g, '-')
}

function normalizeAuthContext(authContext) {
  if (!authContext) {
    return null
  }

  const tenantId = authContext.tenantId || authContext.tenant_id || null
  const userRole = normalizeRoodhaRole(authContext.userRole || authContext.user_role || authContext.role)
  const userId = authContext.userId || authContext.user_id || authContext.id || null
  const machineId = authContext.machineId || authContext.machine_id || null
  const token = authContext.token || null
  const isAuthenticated = Boolean(token && tenantId && userRole)

  return {
    ...authContext,
    token,
    tenant_id: tenantId,
    tenantId,
    user_role: userRole,
    userRole,
    role: userRole,
    user_id: userId,
    userId,
    machine_id: machineId,
    machineId,
    isAuthenticated,
  }
}

function isUsableToken(token) {
  return typeof token === 'string' && token.trim().length > 0
}

function clearBrowserAuthStorage() {
  try {
    localStorage.clear()
  } catch {
    // Ignore storage access errors in restricted browser modes.
  }
  try {
    sessionStorage.clear()
  } catch {
    // Ignore storage access errors in restricted browser modes.
  }
}

function setCachedAuthContext(authContext) {
  const normalizedAuthContext = normalizeAuthContext(authContext)
  cachedAuthContext = normalizedAuthContext
  cachedAuthTimestamp = Date.now()
  
  // Persist critical session pieces to localStorage for recovery
  if (normalizedAuthContext && typeof localStorage !== 'undefined') {
    if (isUsableToken(normalizedAuthContext.token)) {
      localStorage.setItem('token', normalizedAuthContext.token)
    }

    const persistable = {
      token: normalizedAuthContext.token || localStorage.getItem('token') || null,
      tenant_id: normalizedAuthContext.tenant_id,
      tenantId: normalizedAuthContext.tenantId,
      user_role: normalizedAuthContext.user_role,
      userRole: normalizedAuthContext.userRole,
      user_id: normalizedAuthContext.user_id,
      userId: normalizedAuthContext.userId,
      machine_id: normalizedAuthContext.machine_id,
      machineId: normalizedAuthContext.machineId,
      isAuthenticated: Boolean(
        normalizedAuthContext.isAuthenticated &&
        (normalizedAuthContext.token || localStorage.getItem('token'))
      ),
    }
    localStorage.setItem(ROODHA_STORAGE_KEY, JSON.stringify(persistable))
  }
  
  return normalizedAuthContext
}

function clearCachedAuthContext() {
  cachedAuthContext = null
  cachedAuthTimestamp = 0
  pendingAuthPromise = null
}

function getFreshCachedAuthContext() {
  if (!cachedAuthContext) return null
  if (Date.now() - cachedAuthTimestamp > AUTH_CACHE_TTL_MS) return null
  return normalizeAuthContext(cachedAuthContext)
}

function getRecoveredAuthContext() {
  const recovered = getRecoveredSessionData()
  if (!recovered) {
    return null
  }

  const token = recovered.token || localStorage.getItem('token') || null
  if (!token) {
    return null
  }

  return normalizeAuthContext({
    ...recovered,
    token,
    isAuthenticated: recovered.isAuthenticated ?? Boolean(token),
  })
}

function buildAuthContextFromDevUser(devUser, token = DEV_PASS_TOKEN || DEV_BYPASS_TOKEN) {
  const resolvedUserId = devUser.userId || devUser.user_id || devUser.id || null
  const resolvedTenantId = devUser.tenantId || devUser.tenant_id || null
  const resolvedRole = devUser.userRole || devUser.user_role || devUser.role || null

  return normalizeAuthContext({
    user: devUser,
    token,
    user_id: resolvedUserId,
    userId: resolvedUserId,
    email: devUser.email || null,
    tenant_id: resolvedTenantId,
    tenantId: resolvedTenantId,
    role: resolvedRole,
    user_role: resolvedRole,
    userRole: resolvedRole,
  })
}

export function getStoredDevAuthContext() {
  // Allow bypass in dev mode OR when VITE_ALLOW_DEV_PASS is enabled (S3/staging builds)
  if (!isDevelopment && !allowDevPass) {
    return null
  }
  if (typeof localStorage === 'undefined') {
    return null
  }

  const token = localStorage.getItem('token')
  const rawDevUser = localStorage.getItem(DEV_BYPASS_USER_KEY)

  // Accept either legacy test123 or the production DEV_PASS_TOKEN
  const isValidBypassToken =
    token === DEV_BYPASS_TOKEN ||
    token === DEV_PASS_TOKEN ||
    token === 'test123' ||
    token === 'roodha-dev-test-123'
  if (!isValidBypassToken || !rawDevUser) {
    return null
  }

  try {
    const devUser = JSON.parse(rawDevUser)
    const authContext = buildAuthContextFromDevUser(devUser, token)
    return setCachedAuthContext(authContext)
  } catch {
    return null
  }
}

export function getRecoveredSessionData() {
  if (typeof localStorage === 'undefined') {
    return null
  }

  try {
    const raw = localStorage.getItem(ROODHA_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export async function login(identity, password) {
  const username = normalizeCognitoUsername(identity)

  try {
    return await signIn({ username, password })
  } catch (error) {
    return throwCognitoError(error, 'login')
  }
}

export async function logout() {
  clearCachedAuthContext()
  clearBrowserAuthStorage()
  return signOut().catch(() => null)
}

export function getCachedAuthContextSync() {
  const cached = getFreshCachedAuthContext()
  if (cached) return cached

  const devContext = getStoredDevAuthContext()
  if (devContext) return devContext

  return null
}

export function storeDevBypassSession(devUser) {
  const token = DEV_PASS_TOKEN || DEV_BYPASS_TOKEN
  localStorage.setItem('token', token)
  localStorage.setItem(DEV_BYPASS_USER_KEY, JSON.stringify(devUser))
  return setCachedAuthContext(buildAuthContextFromDevUser(devUser, token))
}

function buildBackendApiUrl(path) {
  const baseUrl = API_BASE_URL.replace(/\/+$/, '')
  const cleanPath = path.replace(/^\/+/, '').replace(/\/+$/, '')
  return baseUrl.endsWith('/api') ? `${baseUrl}/${cleanPath}` : `${baseUrl}/api/${cleanPath}`
}

export async function getAuthContext(options = {}) {
  const forceFresh = Boolean(options?.forceFresh)
  const devContext = getStoredDevAuthContext()
  if (devContext) {
    return devContext
  }

  if (!forceFresh) {
    const cached = getFreshCachedAuthContext()
    if (cached) {
      return cached
    }

    const recoveredContext = getRecoveredAuthContext()
    if (recoveredContext?.token) {
      return setCachedAuthContext(recoveredContext)
    }

    if (pendingAuthPromise) {
      return pendingAuthPromise
    }
  }

  const freshAuthPromise = (async () => {
    try {
      const user = await getCurrentUser()
      const session = await fetchAuthSession()
      const idToken = session.tokens?.idToken?.toString()
      if (!idToken) {
        throw new Error('Cognito sign-in succeeded, but no ID token was returned. Please sign in again.')
      }
      const tokenPayload = decodeJwtPayload(idToken)
      const payload = {
        ...(session.tokens?.idToken?.payload || {}),
        ...tokenPayload,
      }
      let attributes = null
      
      let resolvedTenantId = payload['custom:tenant_id'] || payload['tenant_id'] || payload['tenantId'] || null
      let resolvedRole =
        payload['custom:user_role'] ||
        payload['custom:role'] ||
        payload['user_role'] ||
        payload['userRole'] ||
        null

      if (!resolvedTenantId || !resolvedRole) {
        attributes = await fetchUserAttributes().catch(() => null)
        if (!resolvedTenantId) {
          resolvedTenantId = attributes?.['custom:tenant_id'] || attributes?.['tenant_id'] || null
        }
        if (!resolvedRole) {
          resolvedRole = attributes?.['custom:user_role'] || attributes?.['custom:role'] || null
        }
      }

      const pendingSignUpProfile = getPendingSignUpProfile()
      if (!resolvedTenantId && pendingSignUpProfile?.tenant_id) {
        resolvedTenantId = pendingSignUpProfile.tenant_id
      }
      if (!resolvedTenantId) {
        resolvedTenantId = deriveTenantIdFromIdentity(payload["email"] || user?.signInDetails?.loginId)
      }

      // Standardized backend session handshake: /api/users/me
      let backendUser = null
      try {
        const fetchUrl = buildBackendApiUrl('users/me')
        const response = await fetch(fetchUrl, {
          headers: {
            'Authorization': `Bearer ${idToken}`,
            ...(resolvedTenantId ? { 'X-Tenant-ID': resolvedTenantId } : {}),
            'Content-Type': 'application/json'
          }
        })
        if (response.ok) {
          const result = await response.json()
          backendUser = result.data?.user || result.data || result
        }
      } catch {
        // Fallback to Cognito attributes
      }

      if (backendUser) {
        resolvedTenantId =
          resolvedTenantId ||
          backendUser.tenant_id ||
          backendUser.tenantId ||
          backendUser.tenant ||
          null
        resolvedRole =
          backendUser.user_role ||
          backendUser.userRole ||
          backendUser.role ||
          resolvedRole
      }

      const finalRole = normalizeRoodhaRole(resolvedRole)

        const authContext = normalizeAuthContext({
        ...buildRawCognitoState({ user, session, payload, attributes }),
        user,
        token: idToken,
        user_id: payload["sub"] || user?.userId || null,
        userId: payload["sub"] || user?.userId || null,
          email: payload["email"] || user?.signInDetails?.loginId || null,
          machine_id: payload['custom:machine_id'] || payload['machine_id'] || attributes?.['custom:machine_id'] || attributes?.['machine_id'] || null,
          tenant_id: resolvedTenantId,
        tenantId: resolvedTenantId,
        role: finalRole,
        user_role: finalRole,
        userRole: finalRole,
      })
      setPendingSignUpProfile(null)
      return setCachedAuthContext(authContext)
    } catch (error) {
      clearCachedAuthContext()
      throw error
    } finally {
      pendingAuthPromise = null
    }
  })()

  if (forceFresh) {
    return freshAuthPromise
  }

  pendingAuthPromise = freshAuthPromise
  return pendingAuthPromise
}

export async function currentAuthenticatedUser() {
  return getAuthContext()
}

export async function getLatestAuthContextForRequest() {
  const devContext = getStoredDevAuthContext()
  if (devContext) {
    return devContext
  }

  try {
    const session = await fetchAuthSession()
    const idToken = session.tokens?.idToken?.toString()
    if (idToken) {
      const cached = getFreshCachedAuthContext()
      if (cached?.token === idToken) {
        return cached
      }
      return getAuthContext({ forceFresh: true })
    }
  } catch {
    // Fall through to persisted session recovery before making callers fail.
  }

  const recoveredContext = getRecoveredAuthContext()
  if (recoveredContext?.token) {
    return setCachedAuthContext(recoveredContext)
  }

  return getAuthContext({ forceFresh: true })
}

export async function signUp(params) {
  if (params?.organizationName && params?.email && params?.password) {
    const tenantId = slugifyTenantId(params.organizationName)
    const email = normalizeCognitoUsername(params.email)
    if (!tenantId) {
      throw {
        code: 'ValidationError',
        name: 'ValidationError',
        message: 'Organization name is required to generate a tenant id.',
      }
    }

    try {
      setPendingSignUpProfile({
        email,
        organizationName: params.organizationName.trim(),
        tenant_id: tenantId,
        role: 'OWNER',
      })

      return await awsSignUp({
        username: email,
        password: params.password,
        options: {
          userAttributes: {
            email,
            'custom:user_role': 'OWNER',
            'custom:tenant_id': tenantId,
          },
        },
      })
    } catch (error) {
      return throwCognitoError(error, 'signUp')
    }
  }

  try {
    return await awsSignUp({
      ...params,
      username: normalizeCognitoUsername(params?.username),
    })
  } catch (error) {
    return throwCognitoError(error, 'signUp')
  }
}

export async function confirmSignUp(params) {
  try {
    return await awsConfirmSignUp({
      ...params,
      username: normalizeCognitoUsername(params?.username),
    })
  } catch (error) {
    return throwCognitoError(error, 'confirmSignUp')
  }
}

export async function resendSignUpCode(params) {
  try {
    return await awsResendSignUpCode({
      ...params,
      username: normalizeCognitoUsername(params?.username),
    })
  } catch (error) {
    return throwCognitoError(error, 'resendSignUpCode')
  }
}

export async function resetPassword(params) {
  try {
    return await awsResetPassword({
      ...params,
      username: normalizeCognitoUsername(params?.username),
    })
  } catch (error) {
    return throwCognitoError(error, 'resetPassword')
  }
}

export async function confirmResetPassword(params) {
  try {
    return await awsConfirmResetPassword({
      ...params,
      username: normalizeCognitoUsername(params?.username),
    })
  } catch (error) {
    return throwCognitoError(error, 'resetPassword')
  }
}

export async function handleConfirmSignIn(challengeResponse) {
  if (challengeResponse && typeof challengeResponse === 'object') {
    return confirmSignIn(challengeResponse)
  }
  return confirmSignIn({ challengeResponse })
}

/**
 * Force-refresh the Cognito session tokens.
 * Called by authenticatedFetch when a 401 is received.
 * Clears the in-memory auth cache so the next getAuthContext() fetches a fresh token.
 */
export async function refreshAuthSession() {
  const storedToken = localStorage.getItem('token')
  const isDevBypassSession =
    (isDevelopment || allowDevPass) &&
    (storedToken === DEV_BYPASS_TOKEN || storedToken === DEV_PASS_TOKEN) &&
    Boolean(localStorage.getItem(DEV_BYPASS_USER_KEY))

  // In dev-bypass mode there is no real Cognito session to refresh.
  if (isDevBypassSession) {
    return null
  }
  try {
    // forceRefresh: true tells Amplify to hit Cognito instead of returning cached tokens
    await fetchAuthSession({ forceRefresh: true })
    // Bust the module-level cache so the next call to getAuthContext() re-reads
    clearCachedAuthContext()
  } catch (error) {
    clearCachedAuthContext()
    throw error
  }
}

