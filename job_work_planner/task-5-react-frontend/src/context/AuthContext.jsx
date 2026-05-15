import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react'
import { getAuthContext, getCachedAuthContextSync, getStoredDevAuthContext, logout as libLogout } from '../lib/auth'

const AuthContext = createContext({
  auth: null,
  role: null,
  tenant_id: null,
  tenantId: null,
  userRole: null,
  isAuthenticated: false,
  isInitializing: true,
  login: () => {},
  logout: () => {},
  refresh: () => {},
})

function normalizeContext(context) {
  if (!context) {
    return null
  }

  const role = context.role || context.userRole || context.user_role || null
  const tenantId = context.tenantId || context.tenant_id || null
  const machineId = context.machineId || context.machine_id || null

  return {
    ...context,
    role,
    userRole: role,
    user_role: role,
    tenantId,
    tenant_id: tenantId,
    machineId,
    machine_id: machineId,
    isAuthenticated: Boolean(context.isAuthenticated),
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => normalizeContext(getCachedAuthContextSync()))
  const [isInitializing, setIsInitializing] = useState(true)
  const authEpochRef = useRef(0)

  const initializeAuth = useCallback(async () => {
    const initEpoch = authEpochRef.current
    try {
      const devContext = getStoredDevAuthContext()
      const context = devContext || await getAuthContext({ forceFresh: true })
      if (authEpochRef.current === initEpoch) {
        setAuth(normalizeContext(context))
      }
    } catch (error) {
      if (authEpochRef.current === initEpoch) {
        setAuth(null)
      }
    } finally {
      if (authEpochRef.current === initEpoch) {
        setIsInitializing(false)
      }
    }
  }, [])

  useEffect(() => {
    initializeAuth()
  }, [initializeAuth])

  const logout = useCallback(async () => {
    authEpochRef.current += 1
    setAuth(null)
    setIsInitializing(false)
    await libLogout()
  }, [])

  const setAuthenticatedContext = useCallback((newAuth) => {
    authEpochRef.current += 1
    setAuth(normalizeContext(newAuth))
    setIsInitializing(false)
  }, [])

  const value = {
    auth,
    role: auth?.role || null,
    tenant_id: auth?.tenant_id || null,
    tenantId: auth?.tenantId || null,
    userRole: auth?.userRole || null,
    isAuthenticated: !!auth?.isAuthenticated,
    isInitializing,
    login: setAuthenticatedContext,
    logout,
    refresh: initializeAuth,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
