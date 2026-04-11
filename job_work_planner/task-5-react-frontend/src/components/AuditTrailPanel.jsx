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
        <div key={key} className="rounded-2xl bg-white/90 px-3 py-2 shadow-sm ring-1 ring-slate-100">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{humanizeLabel(key)}</div>
          <div className="mt-1 text-sm leading-6 text-slate-700">{formatValue(value)}</div>
        </div>
      ))}
    </div>
  )
}

function AuditEventCard({ entry }) {
  const hasBefore = Object.keys(entry.before_state || {}).length > 0
  const hasAfter = Object.keys(entry.after_state || {}).length > 0

  return (
    <article className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="inline-flex rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-white">
            {humanizeLabel(entry.action)}
          </div>
          <p className="mt-3 text-sm font-semibold text-slate-900">{formatTimestamp(entry.timestamp)}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">Actor: {entry.user_id || 'Unknown'}</p>
        </div>
        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">{entry.audit_id}</div>
      </div>

      {(hasBefore || hasAfter) && (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div className="rounded-[22px] bg-rose-50/70 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-600">Before</p>
            <div className="mt-3">{renderState(entry.before_state)}</div>
          </div>
          <div className="rounded-[22px] bg-emerald-50/70 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-600">After</p>
            <div className="mt-3">{renderState(entry.after_state)}</div>
          </div>
        </div>
      )}
    </article>
  )
}

export default function AuditTrailPanel({ title, entries, loading, emptyMessage, compact = false }) {
  return (
    <section className={`rounded-[28px] border border-slate-200 bg-slate-50/75 p-4 ${compact ? '' : 'shadow-[0_18px_50px_rgba(15,23,42,0.08)]'}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Audit trail</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
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
            <AuditEventCard key={entry.audit_id} entry={entry} />
          ))}
        </div>
      ) : (
        <p className="mt-5 text-sm leading-6 text-slate-500">{emptyMessage}</p>
      )}
    </section>
  )
}
