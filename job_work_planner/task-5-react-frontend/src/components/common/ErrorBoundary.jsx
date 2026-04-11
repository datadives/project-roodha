import React from 'react'

/**
 * Principal-grade Error Boundary to isolate component failures.
 * Prevents a single crashed widget from taking down the entire shop-floor console.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.group('!!! COMPONENT CRASH !!!')
    console.error('Error:', error)
    console.error('Info:', errorInfo)
    console.groupEnd()
    
    // In a real production app, we would send this to Sentry/CloudWatch
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="rounded-[28px] border border-rose-200 bg-rose-50 p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-600 text-lg font-bold text-white">
              !
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-rose-600">Component Error</p>
              <h3 className="text-lg font-semibold text-slate-900">This section is temporarily offline</h3>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-600">
            A background task in this module failed. The rest of the dashboard remains functional.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-4 rounded-xl border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100"
          >
            Attempt reset
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
