/**
 * PROJECT ROODHA - v1.5.9 "Industrial Auth"
 * File: LoginPage.jsx
 *
 * Purpose: Professional Cognito authentication entry for login, sign-up,
 * and password recovery.
 */

import React, { useEffect, useMemo, useState } from 'react'
import { flushSync } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle.js'
import CheckCircle2 from 'lucide-react/dist/esm/icons/check-circle-2.js'
import Factory from 'lucide-react/dist/esm/icons/factory.js'
import Loader2 from 'lucide-react/dist/esm/icons/loader-2.js'
import LockKeyhole from 'lucide-react/dist/esm/icons/lock-keyhole.js'
import MailCheck from 'lucide-react/dist/esm/icons/mail-check.js'
import ShieldCheck from 'lucide-react/dist/esm/icons/shield-check.js'
import { CONFIG } from '../config'
import { useAuth } from '../context/AuthContext'
import {
  confirmSignUp as confirmCognitoSignUp,
  confirmResetPassword as confirmCognitoResetPassword,
  getAuthContext,
  login as cognitoLogin,
  logout as clearStoredAuth,
  resendSignUpCode as resendCognitoSignUpCode,
  resetPassword as requestCognitoPasswordReset,
  signUp as cognitoSignUp,
  storeDevBypassSession,
} from '../lib/auth'
import { authenticatedFetch } from '../lib/authenticatedFetch'

const AUTH_VIEWS = {
  LOGIN: 'LOGIN',
  CREATE_ACCOUNT: 'CREATE_ACCOUNT',
  FORGOT_PASSWORD: 'FORGOT_PASSWORD',
}

const AUTH_VIEW_LABELS = {
  [AUTH_VIEWS.LOGIN]: 'Login',
  [AUTH_VIEWS.CREATE_ACCOUNT]: 'New',
  [AUTH_VIEWS.FORGOT_PASSWORD]: 'Reset',
}

const DASHBOARD_PATH = '/dashboard'
const ENABLE_GOOGLE_OAUTH = import.meta.env.VITE_ENABLE_GOOGLE_OAUTH === 'true'
const ENABLE_SELF_SIGNUP = CONFIG.ENABLE_SELF_SIGNUP
const OTP_RESEND_COOLDOWN_SECONDS = 60

function normalizeAuthIdentity(value) {
  const identity = String(value || '').trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(identity) ? identity.toLowerCase() : identity
}

export function getInitialView(initialMode) {
  if (!ENABLE_SELF_SIGNUP) {
    return AUTH_VIEWS.LOGIN
  }

  if (initialMode === AUTH_VIEWS.CREATE_ACCOUNT || initialMode === 'CREATE_ACCOUNT' || initialMode === 'SIGN_UP') {
    return AUTH_VIEWS.CREATE_ACCOUNT
  }

  if (initialMode === AUTH_VIEWS.FORGOT_PASSWORD || initialMode === 'FORGOT_PASSWORD') {
    return AUTH_VIEWS.FORGOT_PASSWORD
  }

  return AUTH_VIEWS.LOGIN
}

function getErrorDisplay(error) {
  if (typeof error === 'string') {
    return { code: 'AuthenticationError', message: error }
  }

  if (error?.code === 'NotAuthorizedException') {
    return {
      code: error.code,
      message:
        error.message ||
        'This Cognito app client is rejecting the request. For account creation, self-service sign-up may still be disabled in AWS.',
    }
  }

  if (error?.code === 'LimitExceededException' || error?.code === 'TooManyRequestsException') {
    return {
      code: error.code,
      message: 'Too many attempts. Please wait a minute before trying again.',
    }
  }

  if (error?.code === 'ExpiredCodeException') {
    return {
      code: error.code,
      message: 'That code has expired. Request a fresh code and try again.',
    }
  }

  if (error?.code === 'NewPasswordRequiredException') {
    return {
      code: error.code,
      message: error.message || 'This invite needs a new password. If it expired, ask the Owner to resend it.',
    }
  }

  return {
    code: error?.code || error?.name || 'AuthenticationError',
    message: error?.message || 'Authentication request failed. Try again.',
  }
}

function validateSignUpInput({ identity, password, organizationName }) {
  if (!organizationName.trim()) {
    return 'Organization name is required.'
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(identity.trim())) {
    return 'Use a valid owner email address for account creation.'
  }

  if (password.length < 8) {
    return 'Password must be at least 8 characters.'
  }

  return ''
}

function validateIdentityAndPassword({ identity, password }) {
  if (!identity.trim()) {
    return 'Email or mobile is required.'
  }

  if (!password) {
    return 'Password is required.'
  }

  return ''
}

function validateOtp(value, label = 'OTP') {
  const code = String(value || '').trim()
  if (!code) return `${label} is required.`
  if (!/^\d{6}$/.test(code)) return `${label} must be a 6 digit code.`
  return ''
}

function ErrorBanner({ error }) {
  if (!error) return null

  return (
    <div className="mb-6 border-2 border-red-500 bg-red-950/80 p-4 shadow-[6px_6px_0_0_rgba(127,29,29,0.75)]">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
        <div className="min-w-0">
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-red-300">
            Auth Fault: {error.code}
          </p>
          <p className="mt-2 break-words font-mono text-sm font-bold leading-5 text-red-50">
            {error.message}
          </p>
        </div>
      </div>
    </div>
  )
}

function LoadingLabel({ children }) {
  return (
    <span className="inline-flex items-center justify-center gap-2">
      <Loader2 className="h-4 w-4 animate-spin" />
      {children}
    </span>
  )
}

export default function LoginPage({ initialMode = AUTH_VIEWS.LOGIN }) {
  const { isAuthenticated, login: setGlobalAuth } = useAuth()
  const [view, setView] = useState(() => getInitialView(initialMode))
  const [identity, setIdentity] = useState('')
  const [password, setPassword] = useState('')
  const [organizationName, setOrganizationName] = useState('')
  const [confirmationCode, setConfirmationCode] = useState('')
  const [signUpStep, setSignUpStep] = useState('FORM')
  const [recoveryStep, setRecoveryStep] = useState('REQUEST_CODE')
  const [recoveryCode, setRecoveryCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const [otpCooldownSeconds, setOtpCooldownSeconds] = useState(0)
  const navigate = useNavigate()
  const isConfirmMode = initialMode === 'CONFIRM_SIGN_UP'

  useEffect(() => {
    if (isAuthenticated) {
      navigate(DASHBOARD_PATH, { replace: true })
    }
  }, [isAuthenticated, navigate])

  useEffect(() => {
    setView(getInitialView(initialMode))
    setError(null)
    setNotice('')
    if (isConfirmMode) {
      setSignUpStep('VERIFY_OTP')
    }
  }, [initialMode, isConfirmMode])

  useEffect(() => {
    if (otpCooldownSeconds <= 0) return undefined
    const timer = window.setTimeout(() => {
      setOtpCooldownSeconds((seconds) => Math.max(0, seconds - 1))
    }, 1000)
    return () => window.clearTimeout(timer)
  }, [otpCooldownSeconds])

  const copy = useMemo(() => {
    if (ENABLE_SELF_SIGNUP && view === AUTH_VIEWS.CREATE_ACCOUNT) {
      return {
        title: 'Create Workspace',
        subtitle: 'Create the first owner for this factory workspace.',
        icon: Factory,
      }
    }

    if (view === AUTH_VIEWS.FORGOT_PASSWORD) {
      return {
        title: 'Recover Access',
        subtitle: 'Get a recovery code by email.',
        icon: MailCheck,
      }
    }

    return {
      title: 'Secure Login',
      subtitle: 'Sign in to your factory workspace.',
      icon: LockKeyhole,
    }
  }, [view])

  const ModeIcon = copy.icon

  const switchView = (nextView) => {
    if (!ENABLE_SELF_SIGNUP && nextView === AUTH_VIEWS.CREATE_ACCOUNT) {
      setView(AUTH_VIEWS.LOGIN)
      setError(null)
      setNotice('Self-service account creation is disabled for this deployment. Sign in with an existing owner or operator account.')
      return
    }

    setView(nextView)
    setError(null)
    setNotice('')
    if (nextView !== AUTH_VIEWS.CREATE_ACCOUNT) {
      setSignUpStep('FORM')
      setConfirmationCode('')
    }
    if (nextView !== AUTH_VIEWS.FORGOT_PASSWORD) {
      setRecoveryStep('REQUEST_CODE')
      setRecoveryCode('')
      setNewPassword('')
    }
  }

  const openSignupView = (notice) => {
    if (!ENABLE_SELF_SIGNUP) {
      setView(AUTH_VIEWS.LOGIN)
      setSignUpStep('FORM')
      setError(null)
      setNotice(notice || 'Self-service account creation is disabled for this deployment. Sign in with an existing account.')
      return
    }

    setView(AUTH_VIEWS.CREATE_ACCOUNT)
    setSignUpStep('VERIFY_OTP')
    if (notice) {
      setNotice(notice)
    }
  }

  const handleAuthError = (authError) => {
    setError(getErrorDisplay(authError))
  }

  const provisionTenantWorkspace = async () => {
    try {
      return await authenticatedFetch('tenants/create', { method: 'POST' })
    } catch (tenantError) {
      console.error('Tenant provisioning failed:', tenantError)
      return null
    }
  }

  const applyProvisionedRole = (authContext, workspace) => {
    const provisionedRole = workspace?.role || workspace?.userRole || workspace?.user_role || null
    if (!provisionedRole) return authContext
    return {
      ...authContext,
      role: provisionedRole,
      userRole: provisionedRole,
      user_role: provisionedRole,
    }
  }

  const handleGoogleSignIn = () => {
    console.log('Initiate OAuth Flow')
  }

  const handleClearSavedSession = async () => {
    setIsLoading(true)
    setError(null)
    setNotice('')
    try {
      await clearStoredAuth()
      setIdentity('')
      setPassword('')
      setOrganizationName('')
      setConfirmationCode('')
      setRecoveryCode('')
      setNewPassword('')
      setSignUpStep('FORM')
      setRecoveryStep('REQUEST_CODE')
      setView(AUTH_VIEWS.LOGIN)
      toast.success('SAVED SESSION CLEARED')
    } catch (authError) {
      handleAuthError({
        code: 'ClearSessionError',
        name: 'ClearSessionError',
        message: authError?.message || 'Could not clear the saved browser session.',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleDevPass = () => {
    const devUser = {
      userId: 'dev-user-id',
      user_id: 'dev-user-id',
      email: 'dev@example.com',
      tenant_id: CONFIG.DEV_TENANT_ID || 'lalafactory',
      tenantId: CONFIG.DEV_TENANT_ID || 'lalafactory',
      user_role: 'OWNER',
      userRole: 'OWNER',
      role: 'OWNER',
    }
    const authContext = storeDevBypassSession(devUser)
    flushSync(() => {
      setGlobalAuth(authContext)
    })
    toast.success('DEMO ACCESS READY')
    navigate(DASHBOARD_PATH, { replace: true })
  }

  const handleLoginSubmit = async (event) => {
    event.preventDefault()
    setIsLoading(true)
    setError(null)
    setNotice('')

    try {
      const validationError = validateIdentityAndPassword({ identity, password })
      if (validationError) {
        throw {
          code: 'ValidationError',
          name: 'ValidationError',
          message: validationError,
        }
      }

      const normalizedIdentity = normalizeAuthIdentity(identity)
      const result = await cognitoLogin(normalizedIdentity, password)

      if (result?.nextStep?.signInStep === 'CONFIRM_SIGN_UP') {
        throw {
          code: 'UserNotConfirmedException',
          name: 'UserNotConfirmedException',
          message: 'Account is not confirmed. Check your email for the confirmation code.',
        }
      }

      const signInStep = result?.nextStep?.signInStep
      if (
        signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED' ||
        signInStep === 'NEW_PASSWORD_REQUIRED' ||
        signInStep === 'FORCE_CHANGE_PASSWORD'
      ) {
        console.warn('[Cognito] Login blocked by password challenge:', signInStep, result?.nextStep)
        throw {
          code: 'NewPasswordRequiredException',
          name: 'NewPasswordRequiredException',
          message: 'This invite requires a new password. If the invite is older than 7 days, ask the Owner to resend it.',
        }
      }

      const authContext = await getAuthContext({ forceFresh: true })
      if (!authContext?.isAuthenticated || !authContext?.token) {
        throw {
          code: 'SessionHydrationError',
          name: 'SessionHydrationError',
          message: 'Sign-in succeeded, but the app could not create a complete session. Please try again.',
        }
      }
      const workspace = await provisionTenantWorkspace()
      const provisionedAuthContext = applyProvisionedRole(authContext, workspace)
      flushSync(() => {
        setGlobalAuth(provisionedAuthContext)
      })
      toast.success('ACCESS GRANTED')
      navigate(DASHBOARD_PATH, { replace: true })
    } catch (authError) {
      const message = authError?.message || ''
      if (message.toLowerCase().includes('already a signed in user')) {
        const authContext = await getAuthContext({ forceFresh: true })
        if (!authContext?.isAuthenticated || !authContext?.token) {
          handleAuthError({
            code: 'SessionHydrationError',
            name: 'SessionHydrationError',
            message: 'You are signed in with Cognito, but the app could not load your session. Please refresh once and try again.',
          })
          return
        }
        const workspace = await provisionTenantWorkspace()
        const provisionedAuthContext = applyProvisionedRole(authContext, workspace)
        flushSync(() => {
          setGlobalAuth(provisionedAuthContext)
        })
        navigate(DASHBOARD_PATH, { replace: true })
      } else if (authError?.code === 'UserNotConfirmedException') {
        openSignupView('This account exists but is not verified yet. Enter the email OTP if you have it, or use Resend OTP below.')
      } else {
        handleAuthError(authError)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleSignUpSubmit = async (event) => {
    event.preventDefault()
    setIsLoading(true)
    setError(null)
    setNotice('')

    try {
      const validationError = validateSignUpInput({ identity, password, organizationName })
      if (validationError) {
        throw {
          code: 'ValidationError',
          name: 'ValidationError',
          message: validationError,
        }
      }

      const result = await cognitoSignUp({
        organizationName,
        email: normalizeAuthIdentity(identity),
        password,
      })

      const deliveryDetails = result?.nextStep?.codeDeliveryDetails
      const deliveryDestination = deliveryDetails?.destination || normalizeAuthIdentity(identity)
      const deliveryMedium = deliveryDetails?.deliveryMedium || 'EMAIL'

      if (result?.nextStep?.signUpStep === 'CONFIRM_SIGN_UP') {
        setNotice(`OTP requested through Cognito ${deliveryMedium.toLowerCase()} delivery to ${deliveryDestination}. If it does not arrive, use Resend OTP, check spam, then verify the Cognito email sender in AWS SES.`)
        toast.success('OTP REQUESTED')
        setOtpCooldownSeconds(OTP_RESEND_COOLDOWN_SECONDS)
        setSignUpStep('VERIFY_OTP')
        return
      }

      setNotice('Account creation request completed. If Cognito requires verification, use Resend OTP to request a fresh code.')
      toast.success('ACCOUNT CREATED')
      setSignUpStep('VERIFY_OTP')
    } catch (authError) {
      if (authError?.code === 'UsernameExistsException' || authError?.name === 'UsernameExistsException') {
        try {
          const result = await resendCognitoSignUpCode({ username: normalizeAuthIdentity(identity) })
          const deliveryDetails = result?.codeDeliveryDetails
          const deliveryDestination = deliveryDetails?.destination || normalizeAuthIdentity(identity)
          const deliveryMedium = deliveryDetails?.deliveryMedium || 'EMAIL'
          setNotice(`Account already exists but is not fully verified yet. A fresh OTP was requested through Cognito ${deliveryMedium.toLowerCase()} delivery to ${deliveryDestination}. If it still does not arrive, fix Cognito email delivery in AWS SES or admin-confirm this test user.`)
          setOtpCooldownSeconds(OTP_RESEND_COOLDOWN_SECONDS)
          setSignUpStep('VERIFY_OTP')
        } catch (resendError) {
          if (resendError?.code === 'NotAuthorizedException') {
            setNotice('This account already exists, but Cognito did not allow OTP resend right now. Stay on verification, try the existing OTP if you have it, or check Cognito email delivery settings in AWS.')
            setSignUpStep('VERIFY_OTP')
            setView(AUTH_VIEWS.CREATE_ACCOUNT)
          } else {
            handleAuthError(resendError)
          }
        }
      } else {
        handleAuthError(authError)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleConfirmSignUpSubmit = async (event) => {
    event.preventDefault()
    setIsLoading(true)
    setError(null)
    setNotice('')

    try {
      const otpError = validateOtp(confirmationCode, 'Email OTP')
      if (otpError) {
        throw {
          code: 'ValidationError',
          name: 'ValidationError',
          message: otpError,
        }
      }

      await confirmCognitoSignUp({
        username: normalizeAuthIdentity(identity),
        confirmationCode: confirmationCode.trim(),
      })
      toast.success('ACCOUNT VERIFIED')
      setNotice('Account verified. Sign in with your email and password.')
      setSignUpStep('FORM')
      setConfirmationCode('')
      setOrganizationName('')
      setPassword('')
      setView(AUTH_VIEWS.LOGIN)
    } catch (authError) {
      const rawMessage = String(authError?.rawMessage || authError?.originalError?.message || authError?.message || '')
      const alreadyConfirmed =
        authError?.code === 'NotAuthorizedException' &&
        /current status is confirmed|already confirmed|user is already confirmed/i.test(rawMessage)

      if (alreadyConfirmed) {
        toast.success('ACCOUNT ALREADY VERIFIED')
        setNotice('This account is already confirmed. Please sign in with your email and password.')
        setSignUpStep('FORM')
        setConfirmationCode('')
        setView(AUTH_VIEWS.LOGIN)
        return
      }

      if (authError?.code === 'NotAuthorizedException') {
        setNotice('Cognito refused OTP verification for this account right now. This usually means the account state or email delivery flow in AWS is inconsistent. Try Resend OTP first.')
      }
      handleAuthError(authError)
    } finally {
      setIsLoading(false)
    }
  }

  const handleResendOtp = async () => {
    if (otpCooldownSeconds > 0) {
      setNotice(`Please wait ${otpCooldownSeconds}s before requesting another OTP.`)
      return
    }

    setIsLoading(true)
    setError(null)
    setNotice('')

    try {
      const result = await resendCognitoSignUpCode({ username: normalizeAuthIdentity(identity) })
      const deliveryDetails = result?.codeDeliveryDetails
      const deliveryDestination = deliveryDetails?.destination || normalizeAuthIdentity(identity)
      const deliveryMedium = deliveryDetails?.deliveryMedium || 'EMAIL'
      setNotice(`A fresh OTP was requested through Cognito ${deliveryMedium.toLowerCase()} delivery to ${deliveryDestination}. If it still does not arrive, the AWS Cognito/SES sender needs to be verified or the test user must be admin-confirmed.`)
      toast.success('OTP SENT')
      setOtpCooldownSeconds(OTP_RESEND_COOLDOWN_SECONDS)
    } catch (authError) {
      if (authError?.code === 'NotAuthorizedException') {
        setNotice('Cognito did not allow OTP resend for this account. If no OTP ever arrived, the AWS Cognito email delivery setup likely needs attention.')
      }
      handleAuthError(authError)
    } finally {
      setIsLoading(false)
    }
  }

  const handleForgotPasswordSubmit = async (event) => {
    event.preventDefault()
    setIsLoading(true)
    setError(null)
    setNotice('')

    try {
      if (!normalizeAuthIdentity(identity)) {
        throw {
          code: 'ValidationError',
          name: 'ValidationError',
          message: 'Email or mobile is required to request recovery.',
        }
      }

      await requestCognitoPasswordReset({ username: normalizeAuthIdentity(identity) })
      setNotice('Recovery code requested. Enter the OTP and your new password below.')
      toast.success('RECOVERY CODE SENT')
      setRecoveryStep('RESET_PASSWORD')
    } catch (authError) {
      if (
        authError?.code === 'InvalidParameterException' ||
        authError?.code === 'UserNotConfirmedException'
      ) {
        openSignupView('This account is not confirmed yet. Verify the email OTP first, or use the recovery flow from the Login screen.')
      }
      handleAuthError(authError)
    } finally {
      setIsLoading(false)
    }
  }

  const handleConfirmResetPasswordSubmit = async (event) => {
    event.preventDefault()
    setIsLoading(true)
    setError(null)
    setNotice('')

    try {
      const otpError = validateOtp(recoveryCode, 'Recovery OTP')
      if (otpError) {
        throw {
          code: 'ValidationError',
          name: 'ValidationError',
          message: otpError,
        }
      }
      if (newPassword.length < 8) {
        throw {
          code: 'ValidationError',
          name: 'ValidationError',
          message: 'New password must be at least 8 characters.',
        }
      }

      await confirmCognitoResetPassword({
        username: normalizeAuthIdentity(identity),
        confirmationCode: recoveryCode.trim(),
        newPassword,
      })
      toast.success('PASSWORD UPDATED')
      setNotice('Password updated. Sign in with your new password.')
      setPassword('')
      setRecoveryCode('')
      setNewPassword('')
      setRecoveryStep('REQUEST_CODE')
      setView(AUTH_VIEWS.LOGIN)
    } catch (authError) {
      handleAuthError(authError)
    } finally {
      setIsLoading(false)
    }
  }

  const labelStyle = 'mb-2 block text-[10px] font-black uppercase tracking-[0.22em] text-slate-400'
  const inputStyle =
    'h-12 w-full border-2 border-slate-700 bg-slate-950 px-4 font-mono text-sm font-bold text-slate-100 outline-none transition focus:border-orange-500 focus:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60'
  const primaryButtonStyle =
    'min-h-[52px] w-full border-2 border-orange-400 bg-orange-500 px-5 text-sm font-black uppercase tracking-normal text-slate-950 shadow-[6px_6px_0_0_#7c2d12] transition hover:bg-orange-300 hover:shadow-[3px_3px_0_0_#7c2d12] hover:translate-x-[3px] hover:translate-y-[3px] disabled:translate-x-0 disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none'
  const secondaryButtonStyle =
    'min-h-[46px] w-full border-2 border-slate-700 bg-slate-950 px-4 text-sm font-black uppercase tracking-normal text-slate-100 transition hover:border-slate-500 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60'
  const tabStyle =
    'min-h-[40px] min-w-0 border border-slate-700 px-2 text-xs font-black uppercase tracking-normal transition disabled:cursor-not-allowed disabled:opacity-60'
  const visibleViews = ENABLE_SELF_SIGNUP
    ? Object.values(AUTH_VIEWS)
    : [AUTH_VIEWS.LOGIN, AUTH_VIEWS.FORGOT_PASSWORD]
  const tabCols = ENABLE_SELF_SIGNUP ? 'grid-cols-3' : 'grid-cols-2'

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-orange-500 selection:text-slate-950">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(249,115,22,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(249,115,22,0.06)_1px,transparent_1px)] bg-[size:44px_44px]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_24%_16%,rgba(249,115,22,0.18),transparent_34%),radial-gradient(circle_at_78%_84%,rgba(148,163,184,0.12),transparent_32%)]" />

      <main className="relative flex min-h-screen items-center justify-center px-4 py-10">
        <section className="w-full max-w-[500px] border-2 border-slate-700 bg-slate-900/95 p-5 shadow-[12px_12px_0_0_rgba(15,23,42,0.9)] sm:p-8">
          <div className="mb-6 flex items-start justify-between gap-4 border-b-2 border-slate-800 pb-5">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 border border-orange-500/50 bg-orange-500/10 px-3 py-1">
                <ShieldCheck className="h-4 w-4 text-orange-300" />
                <span className="font-mono text-[10px] font-black uppercase tracking-[0.24em] text-orange-200">
                  Cognito Guard
                </span>
              </div>
              <h1 className="text-3xl font-black uppercase tracking-normal text-white sm:text-4xl">ROODHA</h1>
              <p className="mt-2 max-w-xs text-xs font-medium leading-5 text-slate-500">{copy.subtitle}</p>
            </div>
            <div className="flex h-12 w-12 shrink-0 items-center justify-center border-2 border-slate-700 bg-slate-950">
              <ModeIcon className="h-6 w-6 text-orange-400" />
            </div>
          </div>

          <div className={`mb-6 grid ${tabCols} gap-2 rounded-sm bg-slate-950/70 p-1`}>
            {visibleViews.map((mode) => (
              <button
                key={mode}
                type="button"
                disabled={isLoading}
                onClick={() => switchView(mode)}
                className={`${tabStyle} ${
                  view === mode
                    ? 'border-orange-400 bg-orange-500 text-slate-950'
                    : 'bg-slate-950 text-slate-400 hover:border-orange-500/70 hover:text-slate-100'
                }`}
              >
                <span className="block truncate">{AUTH_VIEW_LABELS[mode]}</span>
              </button>
            ))}
          </div>

          <div className="mb-6">
            <p className="font-mono text-[10px] font-black uppercase tracking-[0.28em] text-slate-500">
              Auth Mode
            </p>
            <h2 className="mt-1 text-xl font-black uppercase text-slate-50">{copy.title}</h2>
          </div>

          <ErrorBanner error={error} />

          {notice && (
            <div className="mb-6 border-2 border-emerald-500/70 bg-emerald-950/50 p-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />
                <p className="font-mono text-sm font-bold leading-5 text-emerald-50">{notice}</p>
              </div>
            </div>
          )}

          {ENABLE_GOOGLE_OAUTH && (view === AUTH_VIEWS.LOGIN || view === AUTH_VIEWS.CREATE_ACCOUNT) && (
            <button
              type="button"
              className={`${secondaryButtonStyle} mb-5 flex items-center justify-center gap-3`}
              disabled={isLoading}
              onClick={handleGoogleSignIn}
            >
              <span className="flex h-6 w-6 shrink-0 items-center justify-center bg-white font-black text-blue-600">G</span>
              <span className="truncate">Sign in with Google</span>
            </button>
          )}

          {view === AUTH_VIEWS.LOGIN && (
            <form className="space-y-5" onSubmit={handleLoginSubmit} autoComplete="off" noValidate>
              <div>
                <label className={labelStyle} htmlFor="identity">
                  Email or Mobile
                </label>
                <input
                  id="identity"
                  name="roodha-login-identity"
                  className={inputStyle}
                  type="text"
                  value={identity}
                  onChange={(event) => setIdentity(event.target.value)}
                  onBlur={() => setIdentity((current) => normalizeAuthIdentity(current))}
                  placeholder="EMAIL_OR_MOBILE"
                  autoComplete="off"
                  disabled={isLoading}
                  required
                />
              </div>

              <div>
                <label className={labelStyle} htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  name="roodha-login-passcode"
                  className={inputStyle}
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="PASSWORD"
                  autoComplete="new-password"
                  disabled={isLoading}
                  required
                />
              </div>

              <button type="submit" className={primaryButtonStyle} disabled={isLoading}>
                {isLoading ? <LoadingLabel>Validating</LoadingLabel> : 'Establish Session'}
              </button>

              {CONFIG.ALLOW_DEV_PASS && (
                <button
                  type="button"
                  className={secondaryButtonStyle}
                  disabled={isLoading}
                  onClick={handleDevPass}
                >
                  Demo Access
                </button>
              )}
            </form>
          )}

          {ENABLE_SELF_SIGNUP && view === AUTH_VIEWS.CREATE_ACCOUNT && (
            <>
              {signUpStep === 'FORM' && (
                <form className="space-y-5" onSubmit={handleSignUpSubmit} autoComplete="off" noValidate>
                  <div>
                    <label className={labelStyle} htmlFor="organization-name">
                      Organization Name
                    </label>
                    <input
                      id="organization-name"
                      name="roodha-organization-name"
                      className={inputStyle}
                      type="text"
                      value={organizationName}
                      onChange={(event) => setOrganizationName(event.target.value)}
                      placeholder="PRODUCTION_UNIT"
                      autoComplete="off"
                      disabled={isLoading}
                      required
                    />
                  </div>

                  <div>
                    <label className={labelStyle} htmlFor="signup-identity">
                      Owner Email
                    </label>
                    <input
                      id="signup-identity"
                      name="roodha-owner-email"
                      className={inputStyle}
                      type="email"
                      value={identity}
                      onChange={(event) => setIdentity(event.target.value)}
                      onBlur={() => setIdentity((current) => normalizeAuthIdentity(current))}
                      placeholder="OWNER@COMPANY.COM"
                      autoComplete="off"
                      disabled={isLoading}
                      required
                    />
                  </div>

                  <div>
                    <label className={labelStyle} htmlFor="signup-password">
                      Password
                    </label>
                    <input
                      id="signup-password"
                      name="roodha-owner-new-passcode"
                      className={inputStyle}
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="PASSWORD"
                      autoComplete="new-password"
                      disabled={isLoading}
                      required
                    />
                  </div>

                  <button type="submit" className={primaryButtonStyle} disabled={isLoading}>
                    {isLoading ? <LoadingLabel>Sending OTP</LoadingLabel> : 'Create Account'}
                  </button>
                </form>
              )}

              {signUpStep === 'VERIFY_OTP' && (
                <form className="space-y-5" onSubmit={handleConfirmSignUpSubmit} autoComplete="off" noValidate>
                  <div className="border-2 border-slate-700 bg-slate-950 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
                      Verification Target
                    </p>
                    <p className="mt-2 break-all font-mono text-sm font-bold text-orange-200">
                      {identity}
                    </p>
                  </div>

                  <div>
                    <label className={labelStyle} htmlFor="confirmation-code">
                      Email OTP
                    </label>
                    <input
                      id="confirmation-code"
                      className={inputStyle}
                      type="text"
                      value={confirmationCode}
                      onChange={(event) => setConfirmationCode(event.target.value)}
                      placeholder="6_DIGIT_CODE"
                      autoComplete="one-time-code"
                      inputMode="numeric"
                      disabled={isLoading}
                      required
                    />
                  </div>

                  <button type="submit" className={primaryButtonStyle} disabled={isLoading}>
                    {isLoading ? <LoadingLabel>Verifying OTP</LoadingLabel> : 'Verify OTP'}
                  </button>

                  <button
                    type="button"
                    className={secondaryButtonStyle}
                    disabled={isLoading || otpCooldownSeconds > 0}
                    onClick={handleResendOtp}
                  >
                    {otpCooldownSeconds > 0 ? `Resend OTP in ${otpCooldownSeconds}s` : 'Resend OTP'}
                  </button>

                  <button
                    type="button"
                    className={secondaryButtonStyle}
                    disabled={isLoading}
                    onClick={() => setSignUpStep('FORM')}
                  >
                    Edit Account Details
                  </button>
                </form>
              )}
            </>
          )}

          {view === AUTH_VIEWS.FORGOT_PASSWORD && (
            <>
              {recoveryStep === 'REQUEST_CODE' && (
                <form className="space-y-5" onSubmit={handleForgotPasswordSubmit} autoComplete="off" noValidate>
                  <div>
                    <label className={labelStyle} htmlFor="recovery-identity">
                      Email or Mobile
                    </label>
                    <input
                      id="recovery-identity"
                      name="roodha-recovery-identity"
                      className={inputStyle}
                      type="text"
                      value={identity}
                      onChange={(event) => setIdentity(event.target.value)}
                      onBlur={() => setIdentity((current) => normalizeAuthIdentity(current))}
                      placeholder="EMAIL_OR_MOBILE"
                      autoComplete="off"
                      disabled={isLoading}
                      required
                    />
                  </div>

                  <button type="submit" className={primaryButtonStyle} disabled={isLoading}>
                    {isLoading ? <LoadingLabel>Routing Code</LoadingLabel> : 'Request Recovery Code'}
                  </button>
                </form>
              )}

              {recoveryStep === 'RESET_PASSWORD' && (
                <form className="space-y-5" onSubmit={handleConfirmResetPasswordSubmit} autoComplete="off" noValidate>
                  <div className="border-2 border-slate-700 bg-slate-950 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
                      Recovery Target
                    </p>
                    <p className="mt-2 break-all font-mono text-sm font-bold text-orange-200">
                      {identity}
                    </p>
                  </div>

                  <div>
                    <label className={labelStyle} htmlFor="recovery-code">
                      Recovery OTP
                    </label>
                    <input
                      id="recovery-code"
                      className={inputStyle}
                      type="text"
                      value={recoveryCode}
                      onChange={(event) => setRecoveryCode(event.target.value)}
                      placeholder="6_DIGIT_CODE"
                      autoComplete="one-time-code"
                      inputMode="numeric"
                      disabled={isLoading}
                      required
                    />
                  </div>

                  <div>
                    <label className={labelStyle} htmlFor="new-password">
                      New Password
                    </label>
                    <input
                      id="new-password"
                      name="roodha-recovery-new-passcode"
                      className={inputStyle}
                      type="password"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      placeholder="NEW_PASSWORD"
                      autoComplete="new-password"
                      disabled={isLoading}
                      required
                    />
                  </div>

                  <button type="submit" className={primaryButtonStyle} disabled={isLoading}>
                    {isLoading ? <LoadingLabel>Updating Password</LoadingLabel> : 'Update Password'}
                  </button>

                  <button
                    type="button"
                    className={secondaryButtonStyle}
                    disabled={isLoading}
                    onClick={handleForgotPasswordSubmit}
                  >
                    Resend Recovery Code
                  </button>
                </form>
              )}
            </>
          )}

          <div className="mt-8 border-t-2 border-slate-800 pt-5">
            <button
              type="button"
              className="mb-4 w-full border border-slate-800 bg-slate-950 px-4 py-3 text-xs font-black uppercase tracking-[0.18em] text-slate-500 transition hover:border-orange-500/60 hover:text-orange-300 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoading}
              onClick={handleClearSavedSession}
            >
              Clear Saved Session
            </button>
            <p className="text-center font-mono text-[10px] font-black uppercase tracking-[0.26em] text-slate-600">
              Secure Protocol Active
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}
