/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: AuditTrailPanel.jsx
 * 
 * 1) Purpose: React component for rendering AuditTrailPanel UI elements.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

function humanizeLabel(value) {
  if (!value) return 'Unknown'

  return value
    .toString()
    .replace(/_/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatTimestamp(value) {
  if (!value) return 'Unknown time'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') {
    return 'N/A'
  }

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  if (Array.isArray(value)) {
    return value.length > 0 ? value.map(formatValue).join(', ') : 'N/A'
  }

  if (typeof value === 'object') {
    return Object.entries(value)
      .slice(0, 4)
      .map(([key, nestedValue]) => `${humanizeLabel(key)}: ${formatValue(nestedValue)}`)
      .join(' | ')
  }

  return String(value)
}

function renderState(state) {
  const entries = Object.entries(state || {})

  if (entries.length === 0) {
    return <p className="text-sm text-slate-400">No values recorded.</p>
  }

  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-2xl bg-slate-950 px-3 py-2 shadow-sm ring-1 ring-slate-800">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{humanizeLabel(key)}</div>
          <div className="mt-1 text-sm leading-6 text-slate-300">{formatValue(value)}</div>
        </div>
      ))}
    </div>
  )
}

function AuditEventCard({ entry }) {
  const hasBefore = Object.keys(entry.beforeState || {}).length > 0
  const hasAfter = Object.keys(entry.afterState || {}).length > 0

  return (
    <article className="rounded-[24px] border border-slate-800 bg-slate-900 p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="inline-flex rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-white">
            {humanizeLabel(entry.action)}
          </div>
          <p className="mt-3 text-sm font-semibold text-white">{formatTimestamp(entry.timestamp)}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">Actor: {entry.userId || 'Unknown'}</p>
        </div>
        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">{entry.auditId}</div>
      </div>

      {(hasBefore || hasAfter) && (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div className="rounded-[22px] border border-slate-800 bg-slate-950 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Before</p>
            <div className="mt-3">{renderState(entry.beforeState)}</div>
          </div>
          <div className="rounded-[22px] border border-orange-500/20 bg-slate-950 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-orange-300">After</p>
            <div className="mt-3">{renderState(entry.afterState)}</div>
          </div>
        </div>
      )}
    </article>
  )
}

export default function AuditTrailPanel({ title, entries, loading, emptyMessage, compact = false }) {
  return (
    <section className={`rounded-[28px] border border-slate-800 bg-slate-900/60 p-4 ${compact ? '' : 'shadow-[0_18px_50px_rgba(15,23,42,0.08)]'}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Audit trail</p>
          <h3 className="mt-2 text-xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
            {title}
          </h3>
        </div>
        <div className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">{entries.length}</div>
      </div>

      {loading ? (
        <p className="mt-5 text-sm text-slate-500">Loading audit history...</p>
      ) : entries.length > 0 ? (
        <div className="mt-5 space-y-3">
          {entries.map((entry) => (
            <AuditEventCard key={entry.auditId} entry={entry} />
          ))}
        </div>
      ) : (
        <p className="mt-5 text-sm leading-6 text-slate-500">{emptyMessage}</p>
      )}
    </section>
  )
}
