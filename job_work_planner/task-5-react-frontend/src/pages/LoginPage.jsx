import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { DEV_TENANT_ID, login, storeDevBypassSession, signUp, resetPassword, confirmResetPassword } from '../lib/auth'

const isDevelopment = import.meta.env.MODE === 'development'
const developerBypassUser = {
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

export default function LoginPage() {
  const [mode, setMode] = useState('SIGN_IN')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [code, setCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()

  const onSignInSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      const result = await login(email.trim(), password)
      if (result?.isSignedIn) {
        toast.success('Login successful')
        navigate('/')
      } else if (result?.nextStep?.signInStep) {
        toast.success(`Next step: ${result.nextStep.signInStep}`)
        navigate('/')
      } else {
        toast.success('Authentication successful')
        navigate('/')
      }
    } catch (error) {
      toast.error(error?.message || 'Unable to sign in')
    } finally {
      setSubmitting(false)
    }
  }

  const onSignUpSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    toast.loading('Creating account...', { id: 'auth-toast' })
    try {
      if (isDevelopment && email.includes('@test.com')) {
        toast.success('Sign up mocked successfully (Dev mode)', { id: 'auth-toast' })
        setMode('SIGN_IN')
        return
      }
      await signUp({
        username: email.trim(),
        password,
        options: {
          userAttributes: {
            'custom:tenant_id': companyName.trim(),
            email: email.trim(),
          }
        }
      })
      toast.success('Account created! Please sign in.', { id: 'auth-toast' })
      setMode('SIGN_IN')
    } catch (error) {
      console.error("COGNITO_FAILURE_DETAILS:", error);
      toast.error(error?.message || 'Unable to create account', { id: 'auth-toast' })
    } finally {
      setSubmitting(false)
    }
  }

  const onForgotPasswordSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    toast.loading('Sending code...', { id: 'auth-toast' })
    try {
      if (isDevelopment && email.includes('@test.com')) {
        toast.success('Code mocked successfully (Dev mode)', { id: 'auth-toast' })
        setMode('CONFIRM_NEW_PASSWORD')
        return
      }
      await resetPassword({ username: email.trim() })
      toast.success('Recovery code sent to your email', { id: 'auth-toast' })
      setMode('CONFIRM_NEW_PASSWORD')
    } catch (error) {
      toast.error(error?.message || 'Failed to send recovery code', { id: 'auth-toast' })
    } finally {
      setSubmitting(false)
    }
  }

  const onConfirmNewPasswordSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    toast.loading('Resetting password...', { id: 'auth-toast' })
    try {
      if (isDevelopment && email.includes('@test.com')) {
        toast.success('Password reset mocked successfully', { id: 'auth-toast' })
        setMode('SIGN_IN')
        return
      }
      await confirmResetPassword({ username: email.trim(), confirmationCode: code, newPassword: password })
      toast.success('Password reset successfully. Please sign in.', { id: 'auth-toast' })
      setMode('SIGN_IN')
    } catch (error) {
      toast.error(error?.message || 'Failed to reset password', { id: 'auth-toast' })
    } finally {
      setSubmitting(false)
    }
  }

  const onDeveloperLogin = () => {
    storeDevBypassSession(developerBypassUser)
    toast.success('Demo workspace ready')
    navigate('/')
  }

  // Common input styling
  const inputClassName = "mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm transition-colors focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
  const labelClassName = "text-sm font-medium text-slate-700"
  
  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(251,191,36,0.08),transparent_28%),linear-gradient(160deg,rgba(248,250,252,0.96),rgba(226,232,240,0.92))] px-4">
      <div className="w-full max-w-[420px] rounded-[32px] border border-white/80 bg-white/95 p-8 shadow-[0_30px_80px_rgba(15,23,42,0.12)]">
        
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-xl shadow-slate-900/20">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Project Roodha</h1>
          <p className="mt-2 text-sm text-slate-500">
            {mode === 'SIGN_IN' && 'Welcome back. Enter your credentials to access your workspace.'}
            {mode === 'SIGN_UP' && 'Create your workspace and start managing production seamlessly.'}
            {mode === 'FORGOT_PASSWORD' && 'Enter your email to receive a password reset code.'}
            {mode === 'CONFIRM_NEW_PASSWORD' && 'Enter the reset code and your new password.'}
          </p>
        </div>

        {/* SIGN IN FORM */}
        {mode === 'SIGN_IN' && (
          <form onSubmit={onSignInSubmit} className="space-y-5">
            <div>
              <label className={labelClassName}>Corporate Email</label>
              <input
                className={inputClassName}
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <label className={labelClassName}>Password</label>
                <button 
                  type="button" 
                  onClick={() => setMode('FORGOT_PASSWORD')}
                  className="text-xs font-medium text-slate-500 hover:text-slate-900"
                >
                  Forgot Password?
                </button>
              </div>
              <input
                className={inputClassName}
                placeholder="••••••••"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            
            <button disabled={submitting} className="w-full rounded-2xl bg-slate-900 py-3.5 font-semibold text-white shadow-lg shadow-slate-900/20 transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0">
              {submitting ? 'Authenticating...' : 'Sign In'}
            </button>
            
            <div className="mt-6 text-center text-sm text-slate-500">
              Don't have an account?{' '}
              <button type="button" onClick={() => setMode('SIGN_UP')} className="font-semibold text-slate-900 hover:underline">
                Create Account
              </button>
            </div>
          </form>
        )}

        {/* SIGN UP FORM */}
        {mode === 'SIGN_UP' && (
          <form onSubmit={onSignUpSubmit} className="space-y-4">
            <div>
              <label className={labelClassName}>Company Name</label>
              <input
                className={inputClassName}
                placeholder="e.g. Acme Manufacturing"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                required
              />
            </div>
            <div>
              <label className={labelClassName}>Professional Email</label>
              <input
                className={inputClassName}
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>
            <div>
              <label className={labelClassName}>Secure Password</label>
              <input
                className={inputClassName}
                placeholder="••••••••"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </div>
            
            <button disabled={submitting} className="w-full rounded-2xl bg-slate-900 py-3.5 font-semibold text-white shadow-lg shadow-slate-900/20 transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0">
              {submitting ? 'Creating account...' : 'Create Account'}
            </button>
            
            <div className="mt-6 text-center text-sm text-slate-500">
              Already have an account?{' '}
              <button type="button" onClick={() => setMode('SIGN_IN')} className="font-semibold text-slate-900 hover:underline">
                Sign In
              </button>
            </div>
          </form>
        )}

        {/* FORGOT PASSWORD FORM */}
        {mode === 'FORGOT_PASSWORD' && (
          <form onSubmit={onForgotPasswordSubmit} className="space-y-5">
            <div>
              <label className={labelClassName}>Email Address</label>
              <input
                className={inputClassName}
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            
            <button disabled={submitting} className="w-full rounded-2xl bg-slate-900 py-3.5 font-semibold text-white shadow-lg shadow-slate-900/20 transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0">
              {submitting ? 'Sending...' : 'Send Recovery Code'}
            </button>
            
            <div className="mt-6 text-center text-sm text-slate-500">
              Wait, I remember it!{' '}
              <button type="button" onClick={() => setMode('SIGN_IN')} className="font-semibold text-slate-900 hover:underline">
                Back to Sign In
              </button>
            </div>
          </form>
        )}

        {/* CONFIRM NEW PASSWORD FORM */}
        {mode === 'CONFIRM_NEW_PASSWORD' && (
          <form onSubmit={onConfirmNewPasswordSubmit} className="space-y-4">
            <div>
              <label className={labelClassName}>Recovery Code</label>
              <input
                className={inputClassName}
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
              />
            </div>
            <div>
              <label className={labelClassName}>New Password</label>
              <input
                className={inputClassName}
                placeholder="••••••••"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            
            <button disabled={submitting} className="w-full rounded-2xl bg-slate-900 py-3.5 font-semibold text-white shadow-lg shadow-slate-900/20 transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0">
              {submitting ? 'Resetting...' : 'Set New Password'}
            </button>
            
            <div className="mt-6 text-center text-sm text-slate-500">
              <button type="button" onClick={() => setMode('SIGN_IN')} className="font-semibold text-slate-900 hover:underline">
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* DEMO BYPASS (SECONDARY) */}
        {isDevelopment && (
          <div className="mt-10 border-t border-slate-100 pt-6">
            <button
              type="button"
              onClick={onDeveloperLogin}
              className="w-full rounded-[20px] bg-slate-50 px-4 py-3.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
            >
              Demo Login (Fast Track)
            </button>
          </div>
        )}

      </div>
    </div>
  )
}
