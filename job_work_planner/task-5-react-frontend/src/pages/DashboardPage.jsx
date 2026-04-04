import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { fetchJobById } from '../lib/jobsApi'
import { updateJobOperationStatus } from '../lib/jobOperationsApi'
import { fetchWipMetrics } from '../lib/metricsApi'

const defaultStageOrder = ['CUTTING', 'MACHINING', 'QC', 'DISPATCH']

function prettifyStage(stageId) {
  if (!stageId) return 'Unknown'
  return stageId
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function getCurrentOperation(operations = []) {
  return [...operations]
    .sort((left, right) => left.sequence_number - right.sequence_number)
    .find((operation) => operation.status !== 'COMPLETED')
}

function buildColumns(stages = []) {
  const stageMap = new Map(stages.map((stage) => [stage.stage_id, stage]))
  const orderedIds = [
    ...defaultStageOrder.filter((stageId) => stageMap.has(stageId)),
    ...stages
      .map((stage) => stage.stage_id)
      .filter((stageId) => !defaultStageOrder.includes(stageId)),
  ]

  const baseIds = orderedIds.length > 0 ? orderedIds : defaultStageOrder

  return baseIds.map((stageId) => {
    const stage = stageMap.get(stageId)
    return {
      stage_id: stageId,
      stage_name: stage?.stage_name || prettifyStage(stageId),
      jobs: stage?.jobs || [],
      counts: stage?.counts || {
        total: stage?.jobs?.length || 0,
        delayed: (stage?.jobs || []).filter((job) => job.delayed).length,
      },
    }
  })
}

function JobCard({ job, onOpen }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(job)}
      className={`w-full rounded-[24px] border bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${job.delayed ? 'border-rose-400 ring-2 ring-rose-100' : 'border-slate-200'}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{job.job_id}</p>
          <h3 className="mt-2 text-lg font-semibold text-slate-900">{job.job_number}</h3>
        </div>
        {job.priority === 'HIGH' && (
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-lg font-black text-amber-300">
            !
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">Qty {job.qty ?? job.quantity}</span>
        <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-700">{job.priority}</span>
        {job.delayed && <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-700">Delayed</span>}
      </div>

      <div className="mt-4 text-sm text-slate-600">
        <div>Due {job.due_date}</div>
        <div className="mt-1 text-xs text-slate-400">Customer {job.customer_id}</div>
      </div>
    </button>
  )
}

function JobActionModal({ open, jobDetail, loading, actionLoading, onClose, onStart, onComplete }) {
  if (!open) return null

  const currentOperation = getCurrentOperation(jobDetail?.operations || [])
  const canStart = currentOperation && !['IN_PROGRESS', 'COMPLETED'].includes(currentOperation.status)
  const canComplete = currentOperation && currentOperation.status !== 'COMPLETED'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-[32px] border border-white/70 bg-white p-6 shadow-[0_28px_90px_rgba(15,23,42,0.28)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Current operation control</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              {jobDetail?.job?.job_number || 'Loading job'}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600">
            Close
          </button>
        </div>

        {loading ? (
          <p className="mt-8 text-sm text-slate-500">Loading job details...</p>
        ) : (
          <div className="mt-6 space-y-6">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-[24px] bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Current stage</div>
                <div className="mt-2 text-lg font-semibold text-slate-900">{prettifyStage(jobDetail?.job?.current_stage)}</div>
              </div>
              <div className="rounded-[24px] bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Due date</div>
                <div className="mt-2 text-lg font-semibold text-slate-900">{jobDetail?.job?.due_date}</div>
              </div>
              <div className="rounded-[24px] bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Priority</div>
                <div className="mt-2 text-lg font-semibold text-slate-900">{jobDetail?.job?.priority}</div>
              </div>
            </div>

            <div className="rounded-[26px] border border-slate-100 bg-slate-50/80 p-5">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Current operation</p>
                  <h3 className="mt-2 text-xl font-semibold text-slate-900">
                    {currentOperation ? `${prettifyStage(currentOperation.operation_id)} (${currentOperation.status})` : 'No open operation'}
                  </h3>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={!canStart || actionLoading}
                    onClick={onStart}
                    className="rounded-full border border-sky-200 bg-sky-50 px-5 py-2.5 text-sm font-semibold text-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {actionLoading === 'start' ? 'Starting...' : 'Start'}
                  </button>
                  <button
                    type="button"
                    disabled={!canComplete || actionLoading}
                    onClick={onComplete}
                    className="rounded-full border border-emerald-200 bg-emerald-50 px-5 py-2.5 text-sm font-semibold text-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {actionLoading === 'complete' ? 'Completing...' : 'Complete'}
                  </button>
                </div>
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Operation timeline</p>
              <div className="mt-4 space-y-3">
                {(jobDetail?.operations || [])
                  .slice()
                  .sort((left, right) => left.sequence_number - right.sequence_number)
                  .map((operation) => (
                    <div key={operation.job_operation_id} className={`rounded-[22px] border p-4 ${currentOperation?.job_operation_id === operation.job_operation_id ? 'border-sky-300 bg-sky-50' : 'border-slate-100 bg-white'}`}>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">
                            Step {operation.sequence_number}: {prettifyStage(operation.operation_id)}
                          </p>
                          <p className="text-xs text-slate-500">{operation.job_operation_id}</p>
                        </div>
                        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">{operation.status}</span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [board, setBoard] = useState({ wip_by_stage: [], stages: [] })
  const [selectedJob, setSelectedJob] = useState(null)
  const [jobDetail, setJobDetail] = useState(null)
  const [jobLoading, setJobLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState('')

  const columns = useMemo(() => buildColumns(board.stages), [board.stages])
  const totalWip = useMemo(
    () => board.wip_by_stage.reduce((sum, stage) => sum + (stage.count || 0), 0),
    [board.wip_by_stage],
  )

  async function loadBoard() {
    setLoading(true)
    try {
      const data = await fetchWipMetrics()
      setBoard(data)
    } catch {
      // Toasts are already handled by the shared API layer.
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBoard()
  }, [])

  async function openJob(job) {
    setSelectedJob(job)
    setJobLoading(true)
    setJobDetail(null)
    try {
      const data = await fetchJobById(job.job_id)
      setJobDetail(data)
    } catch {
      setSelectedJob(null)
    } finally {
      setJobLoading(false)
    }
  }

  async function updateCurrentOperation(status, actionKey) {
    const currentOperation = getCurrentOperation(jobDetail?.operations || [])
    if (!currentOperation) return

    setActionLoading(actionKey)
    try {
      const updatedOperation = await updateJobOperationStatus(currentOperation.job_operation_id, { status })
      toast.success(`${prettifyStage(updatedOperation.operation_id)} marked ${status}`)
      const refreshedJob = await fetchJobById(selectedJob.job_id)
      setJobDetail(refreshedJob)
      await loadBoard()
    } catch {
      // Toasts are already handled by the shared API layer.
    } finally {
      setActionLoading('')
    }
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[32px] border border-white/80 bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.24),transparent_28%),radial-gradient(circle_at_85%_18%,_rgba(14,165,233,0.18),transparent_24%),linear-gradient(135deg,rgba(255,255,255,0.95),rgba(248,250,252,0.92))] p-6 shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
        <div className="absolute -right-8 top-10 h-32 w-32 rounded-full bg-amber-200/40 blur-3xl" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500">Single Source Of Truth</p>
            <h1 className="mt-3 text-4xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Main WIP dashboard
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              Track live jobs by current factory stage, spot delayed work immediately, and move operations forward without leaving the board.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-full border border-white/70 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700">Active WIP: {totalWip}</div>
            <div className="rounded-full border border-white/70 bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Manager view</div>
          </div>
        </div>
      </section>

      <section className="overflow-x-auto pb-2">
        <div className="flex min-w-max gap-5">
          {columns.map((column) => (
            <article key={column.stage_id} className="w-[320px] rounded-[28px] border border-white/70 bg-white/88 p-4 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Stage</p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
                    {prettifyStage(column.stage_name || column.stage_id)}
                  </h2>
                </div>
                <div className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">{column.counts.total}</div>
              </div>

              <div className="mb-4 rounded-[20px] bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Delayed in column: {column.counts.delayed}
              </div>

              <div className="space-y-3">
                {column.jobs.length > 0 ? (
                  column.jobs.map((job) => <JobCard key={job.job_id} job={job} onOpen={openJob} />)
                ) : (
                  <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50/80 p-6 text-sm text-slate-400">
                    No jobs in this stage.
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      {loading && <div className="rounded-[24px] border border-white/70 bg-white/85 p-5 text-sm text-slate-500 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">Refreshing WIP board...</div>}

      <JobActionModal
        open={Boolean(selectedJob)}
        jobDetail={jobDetail}
        loading={jobLoading}
        actionLoading={actionLoading}
        onClose={() => {
          setSelectedJob(null)
          setJobDetail(null)
          setActionLoading('')
        }}
        onStart={() => updateCurrentOperation('IN_PROGRESS', 'start')}
        onComplete={() => updateCurrentOperation('COMPLETED', 'complete')}
      />
    </div>
  )
}
