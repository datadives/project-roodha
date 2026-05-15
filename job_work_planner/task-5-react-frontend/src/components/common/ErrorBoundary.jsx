/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: ErrorBoundary.jsx
 * 
 * 1) Purpose: React component for rendering ErrorBoundary UI elements.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import React from 'react'

/**
 * Global Error Boundary — Industrial Fallback UI.
 *
 * Catches any React render/lifecycle crash and replaces the broken subtree
 * with a high-contrast shop-floor safe panel instead of a white screen.
 *
 * Two modes:
 *  1. `fullscreen` prop — wraps the entire app (main.jsx usage).
 *     Shows the full-page "Factory Link Interrupted" screen.
 *  2. Default — inline card used to isolate individual dashboard widgets.
 *     Shows a smaller "Section offline" tile that doesn't kill the whole page.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
    this._handleReload = this._handleReload.bind(this)
    this._handleReset = this._handleReset.bind(this)
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo })
    console.group('!!! COMPONENT CRASH !!!')
    console.error('Error:', error)
    console.error('Info:', errorInfo)
    console.groupEnd()
    // In production: forward to Sentry / CloudWatch here
  }

  componentDidUpdate(prevProps) {
    if (
      this.state.hasError &&
      this.props.resetKey !== undefined &&
      this.props.resetKey !== prevProps.resetKey
    ) {
      this._handleReset()
    }
  }

  _handleReload() {
    window.location.reload()
  }

  _handleReset() {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    // Allow the caller to supply a completely custom fallback node
    if (this.props.fallback) {
      return this.props.fallback
    }

    // ── Full-screen mode (wraps entire app) ────────────────────────────────
    if (this.props.fullscreen) {
      return (
        <div
          role="alert"
          style={{ fontFamily: 'Inter, system-ui, sans-serif' }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-slate-950 px-6 text-center"
        >
          {/* Safety-orange warning icon */}
          <div
            aria-hidden="true"
            className="mb-8 flex h-20 w-20 items-center justify-center rounded-full border-2 border-orange-500 bg-orange-500/10"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-10 w-10 text-orange-500"
            >
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>

          {/* Eyebrow */}
          <p className="text-[11px] font-black uppercase tracking-[0.4em] text-orange-500">
            System Alert
          </p>

          {/* Main heading */}
          <h1 className="mt-3 text-3xl font-black uppercase tracking-tight text-white">
            Factory Link Interrupted
          </h1>

          {/* Sub-copy */}
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
            A critical error occurred in the workspace. Please check your network
            connection or contact your system administrator.
          </p>

          {/* Error detail (collapsed by default for shop-floor cleanliness) */}
          {this.state.error && (
            <details className="mt-6 max-w-lg rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-left">
              <summary className="cursor-pointer select-none text-xs font-semibold uppercase tracking-widest text-slate-500">
                Technical detail
              </summary>
              <pre className="mt-3 overflow-auto whitespace-pre-wrap break-all text-xs text-slate-400">
                {this.state.error.toString()}
              </pre>
            </details>
          )}

          {/* Primary CTA */}
          <button
            type="button"
            id="error-boundary-reload-btn"
            onClick={this._handleReload}
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-orange-500 px-8 py-3 text-sm font-black uppercase tracking-widest text-white shadow-[0_0_24px_-4px_rgba(249,115,22,0.5)] transition hover:bg-orange-600 active:scale-[0.97]"
          >
            {/* Reload icon */}
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
              aria-hidden="true"
            >
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Reload Workspace
          </button>
        </div>
      )
    }

    // ── Inline widget mode (isolates individual dashboard sections) ─────────
    const moduleName = this.props.moduleName || this.props.label || 'Section'

    return (
      <div
        role="alert"
        className="rounded-[28px] border border-orange-500/30 bg-slate-900 p-6 shadow-sm"
      >
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-orange-500 text-lg font-black text-[#0F172A]">
            !
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-orange-300">
              {moduleName} Offline
            </p>
            <h3 className="mt-1 text-base font-semibold text-white">
              This area paused
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Reset this area or reload the workspace.
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            id="error-boundary-reset-btn"
            onClick={this._handleReset}
            className="rounded-full border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-700"
          >
            Reset section
          </button>
          <button
            type="button"
            id="error-boundary-reload-inline-btn"
            onClick={this._handleReload}
            className="rounded-full bg-orange-500 px-4 py-2 text-xs font-semibold text-white transition hover:bg-orange-600"
          >
            Reload Workspace
          </button>
        </div>
      </div>
    )
  }
}

export default ErrorBoundary
