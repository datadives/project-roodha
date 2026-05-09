/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: AccessDeniedPage.jsx
 * 
 * 1) Purpose: React component for rendering AccessDeniedPage UI elements.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { Link } from 'react-router-dom'

export default function AccessDeniedPage({
  title = 'Access limited',
  message = 'Your role does not have permission to use this area yet.',
  allowedRoles = '',
  homePath = '/notifications',
}) {
  return (
    <section className="rounded-[32px] border border-white/80 bg-[linear-gradient(145deg,rgba(255,255,255,0.96),rgba(248,250,252,0.92))] p-6 shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
      <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500">Role-based access</p>
      <h1 className="mt-3 text-4xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
        {title}
      </h1>
      <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">{message}</p>
      {allowedRoles ? (
        <div className="mt-5 inline-flex rounded-full bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700">
          Available for: {allowedRoles}
        </div>
      ) : null}
      <div className="mt-6">
        <Link
          to={homePath}
          className="inline-flex rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Go to your workspace
        </Link>
      </div>
    </section>
  )
}
