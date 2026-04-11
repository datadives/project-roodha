import { useEffect, useMemo, useState } from 'react'
import {
  fetchBottleneckMetrics,
  fetchCostingSummary,
  fetchLateJobsMetrics,
  fetchWipMetrics,
} from '../lib/metricsApi'

const EMPTY_COSTING_OVERVIEW = {
  total_jobs: 0,
  active_jobs: 0,
  completed_jobs: 0,
  late_jobs: 0,
  total_estimated_cost: 0,
  open_estimated_cost: 0,
  completed_estimated_cost: 0,
  average_estimated_job_cost: 0,
  highest_estimated_job_cost: 0,
  highest_estimated_job_number: null,
}

const EMPTY_LATE_JOBS = { total_late: 0, jobs: [] }
const EMPTY_COSTING = {
  overview: EMPTY_COSTING_OVERVIEW,
  recent_completed_jobs: [],
  top_estimated_jobs: [],
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function asObject(value, fallback = {}) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : fallback
}

function normalizeLateJobs(value) {
  const safe = asObject(value, EMPTY_LATE_JOBS)
  return {
    total_late: Number(safe.total_late) || 0,
    jobs: asArray(safe.jobs),
  }
}

function normalizeCosting(value) {
  const safe = asObject(value, EMPTY_COSTING)
  return {
    overview: {
      ...EMPTY_COSTING_OVERVIEW,
      ...asObject(safe.overview, EMPTY_COSTING_OVERVIEW),
    },
    recent_completed_jobs: asArray(safe.recent_completed_jobs),
    top_estimated_jobs: asArray(safe.top_estimated_jobs),
  }
}

function normalizeMetricCollection(value, key) {
  const safe = asObject(value)
  return asArray(safe[key])
}

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value || 0)
}

function formatDate(value) {
  if (!value) return 'Pending'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
  }).format(date)
}

function prettyLabel(value) {
  if (!value) return 'Unknown'

  return value
    .toString()
    .replace(/_/g, ' ')
    .toLowerCase()
    .split(' ')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function MetricCard({ label, value, hint, accent }) {
  return (
    <article className="rounded-[28px] border border-white/70 bg-white/88 p-5 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">{label}</p>
      <div className={`mt-3 text-3xl font-semibold ${accent}`}>{value}</div>
      <p className="mt-2 text-sm text-slate-500">{hint}</p>
    </article>
  )
}

function BarList({ items, emptyMessage, valueKey = 'count', labelKey = 'stage' }) {
  const safeItems = asArray(items)
  const maxValue = Math.max(...safeItems.map((item) => item?.[valueKey] || 0), 1)

  if (safeItems.length === 0) {
    return <p className="text-sm text-slate-500">{emptyMessage}</p>
  }

  return (
    <div className="space-y-4">
      {safeItems.map((item) => {
        const value = item?.[valueKey] || 0
        const width = Math.max((value / maxValue) * 100, value > 0 ? 10 : 0)

        return (
          <div key={`${item?.[labelKey] || 'item'}-${value}`} className="space-y-2">
            <div className="flex items-center justify-between gap-3 text-sm text-slate-600">
              <span className="font-semibold text-slate-800">{prettyLabel(item?.[labelKey])}</span>
              <span>{value}</span>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,rgba(14,165,233,0.88),rgba(251,191,36,0.92))]"
                style={{ width: `${width}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function AnalyticsPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [analytics, setAnalytics] = useState({
    wip_by_stage: [],
    bottlenecks: [],
    late_jobs: EMPTY_LATE_JOBS,
    costing: EMPTY_COSTING,
  })

  useEffect(() => {
    async function loadAnalytics() {
      setLoading(true)
      setError('')
      try {
        const [wip, bottlenecks, lateJobs, costing] = await Promise.allSettled([
          fetchWipMetrics(),
          fetchBottleneckMetrics(),
          fetchLateJobsMetrics(),
          fetchCostingSummary(),
        ])

        const failedRequests = [wip, bottlenecks, lateJobs, costing].filter((result) => result.status === 'rejected')
        setAnalytics({
          wip_by_stage: wip.status === 'fulfilled' ? normalizeMetricCollection(wip.value, 'wip_by_stage') : [],
          bottlenecks:
            bottlenecks.status === 'fulfilled' ? normalizeMetricCollection(bottlenecks.value, 'bottlenecks') : [],
          late_jobs: lateJobs.status === 'fulfilled' ? normalizeLateJobs(lateJobs.value) : EMPTY_LATE_JOBS,
          costing: costing.status === 'fulfilled' ? normalizeCosting(costing.value) : EMPTY_COSTING,
        })
        if (failedRequests.length > 0) {
          setError('Some analytics sources could not be loaded. Showing the data that is currently available.')
        }
      } catch {
        setError('Unable to load analytics right now.')
      } finally {
        setLoading(false)
      }
    }

    loadAnalytics()
  }, [])

  const wipByStage = asArray(analytics?.wip_by_stage)
  const bottlenecks = asArray(analytics?.bottlenecks)
  const lateJobs = normalizeLateJobs(analytics?.late_jobs)
  const costing = normalizeCosting(analytics?.costing)
  const overview = costing.overview
  const wipTotal = useMemo(
    () => wipByStage.reduce((sum, stage) => sum + (stage?.count || 0), 0),
    [wipByStage],
  )
  const topBottleneck = bottlenecks[0]

  if (loading) {
    return (
      <div className="rounded-[28px] border border-white/70 bg-white/80 p-8 text-sm text-slate-600 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
        Loading analytics workspace...
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {error ? (
        <div className="rounded-[24px] border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          {error}
        </div>
      ) : null}

      <section className="relative overflow-hidden rounded-[32px] border border-white/80 bg-[radial-gradient(circle_at_top_left,_rgba(34,197,94,0.18),transparent_28%),radial-gradient(circle_at_86%_18%,_rgba(14,165,233,0.2),transparent_24%),linear-gradient(135deg,rgba(255,255,255,0.95),rgba(248,250,252,0.92))] p-6 shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
        <div className="absolute -left-8 top-8 h-28 w-28 rounded-full bg-emerald-200/40 blur-3xl" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500">Version 1 Analytics</p>
            <h1 className="mt-3 text-4xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Factory performance cockpit
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              Review WIP pressure, machine bottlenecks, overdue work, and the current estimated value of the shopfloor without leaving the planner.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-full border border-white/70 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700">
              Total WIP: {wipTotal}
            </div>
            <div className="rounded-full border border-white/70 bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
              Live metrics
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Active Jobs"
          value={overview.active_jobs}
          hint="Jobs not yet completed in this tenant."
          accent="text-sky-700"
        />
        <MetricCard
          label="Late Jobs"
          value={lateJobs.total_late}
          hint="Work orders past due date and still open."
          accent="text-rose-700"
        />
        <MetricCard
          label="Open Estimated Cost"
          value={formatCurrency(overview.open_estimated_cost)}
          hint="Current estimated value sitting on the shopfloor."
          accent="text-emerald-700"
        />
        <MetricCard
          label="Average Estimated Job Cost"
          value={formatCurrency(overview.average_estimated_job_cost)}
          hint="V1 average based on quantity and routed operations."
          accent="text-amber-700"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <article className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">WIP by Stage</p>
              <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
                Stage load
              </h2>
            </div>
            <div className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
              {wipByStage.length} stages
            </div>
          </div>
          <BarList
            items={wipByStage}
            emptyMessage="No active operations are currently contributing to WIP."
          />
        </article>

        <article className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Bottleneck Machines</p>
              <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
                Capacity pressure
              </h2>
            </div>
            <div className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">
              {topBottleneck ? `${topBottleneck.pending_operations} queued` : 'No queue'}
            </div>
          </div>

          {bottlenecks.length > 0 ? (
            <div className="space-y-3">
              {bottlenecks.map((machine, index) => (
                <div key={machine.machine_id || `${machine.machine_name || 'machine'}-${index}`} className="rounded-[22px] border border-slate-100 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Rank {index + 1}</div>
                      <div className="mt-1 text-lg font-semibold text-slate-900">{machine.machine_name}</div>
                      <div className="mt-1 text-xs text-slate-500">{machine.machine_id}</div>
                    </div>
                    <div className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                      {machine.pending_operations} pending
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No assigned machine backlog is currently visible.</p>
          )}
        </article>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <article className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Late Jobs</p>
              <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
                Overdue work orders
              </h2>
            </div>
            <div className="rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-rose-700">
              {lateJobs.total_late} overdue
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left">
              <thead>
                <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  <th className="pb-3 pr-4">Job</th>
                  <th className="pb-3 pr-4">Due date</th>
                  <th className="pb-3 pr-4">Priority</th>
                  <th className="pb-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {lateJobs.jobs.length > 0 ? (
                  lateJobs.jobs.map((job) => (
                    <tr key={job.job_id}>
                      <td className="py-4 pr-4">
                        <div className="font-semibold text-slate-900">{job.job_number}</div>
                        <div className="mt-1 text-xs text-slate-500">{job.customer_id}</div>
                      </td>
                      <td className="py-4 pr-4 text-sm text-slate-600">{formatDate(job.due_date)}</td>
                      <td className="py-4 pr-4 text-sm text-slate-600">{job.priority}</td>
                      <td className="py-4">
                        <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700">{prettyLabel(job.status)}</span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="4" className="py-8 text-sm text-slate-500">
                      No late jobs for this tenant right now.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
          <div className="mb-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Costing Summary</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Estimated value
            </h2>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Total estimated cost</div>
              <div className="mt-2 text-xl font-semibold text-slate-900">{formatCurrency(overview.total_estimated_cost)}</div>
            </div>
            <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Completed estimated cost</div>
              <div className="mt-2 text-xl font-semibold text-slate-900">{formatCurrency(overview.completed_estimated_cost)}</div>
            </div>
            <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-4 sm:col-span-2">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Highest estimated job</div>
              <div className="mt-2 text-xl font-semibold text-slate-900">
                {overview.highest_estimated_job_number || 'No jobs yet'}
              </div>
              <div className="mt-1 text-sm text-slate-500">{formatCurrency(overview.highest_estimated_job_cost)}</div>
            </div>
          </div>

          <div className="mt-6">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Top estimated jobs</p>
            <div className="mt-4 space-y-3">
              {costing.top_estimated_jobs.length > 0 ? (
                costing.top_estimated_jobs.map((job, index) => (
                  <div key={job.job_id} className="rounded-[22px] border border-slate-100 bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Top {index + 1}</div>
                        <div className="mt-1 text-lg font-semibold text-slate-900">{job.job_number}</div>
                        <div className="mt-1 text-sm text-slate-500">
                          {job.customer_name} | {job.operation_count} routed operations | Qty {job.quantity}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold text-slate-900">{formatCurrency(job.estimated_cost)}</div>
                        <div className="mt-1 text-xs text-slate-500">{prettyLabel(job.status)}</div>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">No jobs are available for costing yet.</p>
              )}
            </div>
          </div>
        </article>
      </div>

      <article className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Recently Completed</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Costing preview
            </h2>
          </div>
          <div className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
            {costing.recent_completed_jobs.length} jobs
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left">
            <thead>
              <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <th className="pb-3 pr-4">Job Number</th>
                <th className="pb-3 pr-4">Customer</th>
                <th className="pb-3 pr-4">Completion</th>
                <th className="pb-3 pr-4">Operations</th>
                <th className="pb-3 text-right">Estimated Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {costing.recent_completed_jobs.length > 0 ? (
                costing.recent_completed_jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td className="py-4 pr-4">
                      <div className="font-semibold text-slate-900">{job.job_number}</div>
                      <div className="mt-1 text-xs text-slate-500">{job.job_id}</div>
                    </td>
                    <td className="py-4 pr-4 text-sm text-slate-600">{job.customer_name}</td>
                    <td className="py-4 pr-4 text-sm text-slate-600">{formatDate(job.completion_date || job.due_date)}</td>
                    <td className="py-4 pr-4 text-sm text-slate-600">{job.operation_count}</td>
                    <td className="py-4 text-right text-sm font-semibold text-slate-900">{formatCurrency(job.estimated_cost)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" className="py-8 text-sm text-slate-500">
                    No completed jobs are available for the costing preview yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </article>
    </div>
  )
}
