import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import AuditTrailPanel from '../components/AuditTrailPanel'
import { getAuthContext } from '../lib/auth'
import { fetchJobAudit, fetchJobById, fetchJobCostSummary, recalculateJobCost, downloadJobInvoice, setJobQuotedPrice } from '../lib/jobsApi'
import { fetchJobOperationAudit, planJobOperation, updateJobOperationStatus } from '../lib/jobOperationsApi'
import { fetchMachines, fetchShifts } from '../lib/masterDataApi'
import { fetchWipMetrics } from '../lib/metricsApi'
import { fetchPlanningCalendar } from '../lib/planningApi'
import { hasPermission, normalizeRole } from '../lib/roles'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts'
import useOptimisticUI from '../hooks/useOptimisticUI'
import ErrorBoundary from '../components/common/ErrorBoundary'

function formatINR(value) {
  if (value == null || value === '') return '—'
  const num = Number(value)
  if (Number.isNaN(num)) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num)
}

const defaultStageOrder = ['CUTTING', 'MACHINING', 'QC', 'DISPATCH']

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function isoDateWithOffset(days = 0) {
  const value = new Date()
  value.setDate(value.getDate() + days)
  return value.toISOString().slice(0, 10)
}

function prettifyStage(stageId) {
  if (!stageId) return 'Unknown'
  return stageId
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function getCurrentOperation(operations = []) {
  return [...asArray(operations)]
    .sort((left, right) => left.sequence_number - right.sequence_number)
    .find((operation) => operation.status !== 'COMPLETED')
}

function buildColumns(stages = []) {
  const safeStages = asArray(stages)
  const stageMap = new Map(safeStages.map((stage) => [stage.stage_id, stage]))
  const orderedIds = [
    ...defaultStageOrder.filter((stageId) => stageMap.has(stageId)),
    ...safeStages
      .map((stage) => stage.stage_id)
      .filter((stageId) => !defaultStageOrder.includes(stageId)),
  ]

  const baseIds = orderedIds.length > 0 ? orderedIds : defaultStageOrder

  return baseIds.map((stageId) => {
    const stage = stageMap.get(stageId)
    return {
      stage_id: stageId,
      stage_name: stage?.stage_name || prettifyStage(stageId),
      jobs: asArray(stage?.jobs),
      counts: stage?.counts || {
        total: asArray(stage?.jobs).length,
        delayed: asArray(stage?.jobs)?.filter((job) => job?.delayed).length || 0,
      },
    }
  })
}

function flattenMachineSchedule(calendarPayload, machineId) {
  const machineSchedule = calendarPayload?.[machineId] || {}

  return Object.entries(machineSchedule)
    .flatMap(([shiftId, dates]) =>
      Object.entries(dates || {}).flatMap(([date, operations]) =>
        (asArray(operations)?.map((operation) => ({
          ...operation,
          shift_id: shiftId,
          planned_date: date,
        })) || []),
      ),
    )
    .sort((left, right) => {
      if (left.planned_date === right.planned_date) {
        return (left.sequence_number || 0) - (right.sequence_number || 0)
      }
      return (left.planned_date || '').localeCompare(right.planned_date || '')
    })
}

function machineNameFor(machineId, machines = []) {
  return asArray(machines)?.find((machine) => machine.machine_id === machineId)?.name || machineId || 'Unassigned'
}

function shiftNameFor(shiftId, shifts = []) {
  return asArray(shifts)?.find((shift) => shift.shift_id === shiftId)?.name || shiftId || 'No shift'
}

function describeDashboardError(error, fallbackMessage) {
  if (!error) return fallbackMessage
  const responseDetail = error?.response?.data?.detail
  if (typeof responseDetail === 'string' && responseDetail.trim()) return responseDetail
  if (typeof error?.message === 'string' && error.message.trim()) {
    if (error.message === 'Network Error') {
      return 'Backend is unreachable. Start the API on port 8000 and refresh the dashboard.'
    }
    return error.message
  }
  return fallbackMessage
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

function JobActionModal({
  open,
  auth,
  machines,
  shifts,
  resourceLoading,
  jobDetail,
  loading,
  actionLoading,
  auditLoading,
  jobAuditEntries,
  operationAuditEntries,
  costSummary,
  recalculating,
  downloadingPdf,
  quotedPriceInput,
  setQuotedPriceInput,
  saveQuotedPrice,
  onClose,
  onStart,
  onComplete,
  onPlan,
  onRecalculate,
  onDownloadInvoice,
}) {
  const [planningLoading, setPlanningLoading] = useState(false)
  const [planningError, setPlanningError] = useState(null)
  const [machineScheduleLoading, setMachineScheduleLoading] = useState(false)
  const [machineSchedule, setMachineSchedule] = useState([])
  const [showCompleteModal, setShowCompleteModal] = useState(false)
  const [completeForm, setCompleteForm] = useState({ quantity_completed: 0, quantity_rejected: 0, actual_start_time: '', actual_end_time: '' })
  const [planForm, setPlanForm] = useState({
    machine_id: '',
    shift_id: '',
    planned_start_date: isoDateWithOffset(0),
    planned_end_date: isoDateWithOffset(7),
    ignore_conflicts: false,
    reason: '',
  })

  const currentOperation = getCurrentOperation(jobDetail?.operations || [])
  const normalizedRole = normalizeRole(auth?.user_role)
  const canExecute = hasPermission(normalizedRole, 'execute')
  const canStart = canExecute && currentOperation && !['IN_PROGRESS', 'COMPLETED'].includes(currentOperation.status)
  const canComplete = canExecute && currentOperation && currentOperation.status !== 'COMPLETED'
  const canPlan = hasPermission(normalizedRole, 'plan')
  const canOverride = hasPermission(normalizedRole, 'overridePlan')
  const activeMachines = asArray(machines)?.filter((machine) => machine?.is_active !== false) || []

  useEffect(() => {
    setPlanningError(null)
    setMachineSchedule([])
    setPlanForm({
      machine_id: currentOperation?.machine_id || '',
      shift_id: currentOperation?.shift_id || '',
      planned_start_date: currentOperation?.planned_start_date || isoDateWithOffset(0),
      planned_end_date: currentOperation?.planned_end_date || isoDateWithOffset(7),
      ignore_conflicts: false,
      reason: '',
    })
  }, [currentOperation?.job_operation_id, currentOperation?.machine_id, currentOperation?.shift_id, currentOperation?.planned_start_date, currentOperation?.planned_end_date])

  useEffect(() => {
    async function loadMachineSchedule() {
      if (!open || !planForm.machine_id || !planForm.planned_start_date || !planForm.planned_end_date) {
        setMachineSchedule([])
        return
      }

      setMachineScheduleLoading(true)
      try {
        const response = await fetchPlanningCalendar({
          machine_id: planForm.machine_id,
          from_date: planForm.planned_start_date,
          to_date: planForm.planned_end_date,
        })
        setMachineSchedule(flattenMachineSchedule(response, planForm.machine_id))
      } catch {
        setMachineSchedule([])
      } finally {
        setMachineScheduleLoading(false)
      }
    }

    loadMachineSchedule()
  }, [open, planForm.machine_id, planForm.planned_start_date, planForm.planned_end_date])

  if (!open) return null
  if (!machines || !Array.isArray(machines)) return null

  async function handlePlanSubmit(event) {
    event.preventDefault()
    if (!currentOperation || !canPlan) return

    setPlanningLoading(true)
    setPlanningError(null)

    try {
      await onPlan({
        machine_id: planForm.machine_id,
        shift_id: planForm.shift_id || null,
        planned_start_date: planForm.planned_start_date,
        planned_end_date: planForm.planned_end_date,
        ignore_conflicts: canOverride ? planForm.ignore_conflicts : false,
        force: canOverride ? planForm.ignore_conflicts : false,
        reason: canOverride ? planForm.reason || null : null,
      })
    } catch (error) {
      const detail = error?.response?.data?.detail
      if (detail && typeof detail === 'object') {
        setPlanningError(detail)
      } else {
        setPlanningError({ error: detail || 'Unable to assign the plan right now.' })
      }
    } finally {
      setPlanningLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-5xl overflow-auto rounded-[32px] border border-white/70 bg-white p-6 shadow-[0_28px_90px_rgba(15,23,42,0.28)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Execution and planning</p>
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
                  {currentOperation ? (
                    <p className="mt-2 text-sm text-slate-500">
                      Step {currentOperation.sequence_number} | Machine {machineNameFor(currentOperation.machine_id, machines)} | Shift{' '}
                      {shiftNameFor(currentOperation.shift_id, shifts)}
                    </p>
                  ) : null}
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
                    onClick={() => setShowCompleteModal(true)}
                    className="rounded-full border border-emerald-200 bg-emerald-50 px-5 py-2.5 text-sm font-semibold text-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {actionLoading === 'complete' ? 'Completing...' : 'Complete'}
                  </button>
                </div>
              </div>
              {!canExecute && currentOperation ? (
                <p className="mt-4 text-sm text-slate-500">
                  Execution controls are available only to operators, supervisors, owners, and admins.
                </p>
              ) : null}
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
              <section className="rounded-[28px] border border-slate-100 bg-slate-50/80 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Planning workflow</p>
                    <h3 className="mt-2 text-2xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
                      Assign machine and shift
                    </h3>
                  </div>
                  <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                    {canPlan ? normalizedRole || 'Planner' : 'View only'}
                  </span>
                </div>

                {planningError ? (
                  <div className="mt-5 rounded-[22px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
                    <p className="font-semibold">{planningError.error || 'Planning conflict detected.'}</p>
                    {planningError.resolution ? <p className="mt-2">{planningError.resolution}</p> : null}
                    {Array.isArray(planningError.clashes) && planningError.clashes.length > 0 ? (
                      <div className="mt-3 space-y-2">
                        {(asArray(planningError.clashes)?.map((clash) => (
                          <div key={clash.job_operation_id} className="rounded-2xl bg-white/80 px-3 py-2 text-xs text-rose-900 shadow-sm">
                            {clash.job_number} | Step {clash.sequence_number} | {clash.planned_start_date} to {clash.planned_end_date} | Shift{' '}
                            {shiftNameFor(clash.shift_id, shifts)}
                          </div>
                        ))) || []}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {resourceLoading ? (
                  <div className="mt-5 rounded-[22px] border border-slate-200 bg-white p-4 text-sm text-slate-500">
                    Loading machines...
                  </div>
                ) : null}

                {!resourceLoading && canPlan && currentOperation ? (
                  <form className="mt-5 space-y-4" onSubmit={handlePlanSubmit}>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Machine</label>
                        <select
                          className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                          value={planForm.machine_id}
                          onChange={(event) => setPlanForm((current) => ({ ...current, machine_id: event.target.value }))}
                          disabled={resourceLoading || planningLoading}
                          required
                        >
                          <option value="">Select machine</option>
                          {(asArray(activeMachines)?.map((machine) => (
                            <option key={machine.machine_id} value={machine.machine_id}>
                              {machine.name} ({machine.type})
                            </option>
                          ))) || []}
                        </select>
                      </div>

                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Shift</label>
                        <select
                          className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                          value={planForm.shift_id}
                          onChange={(event) => setPlanForm((current) => ({ ...current, shift_id: event.target.value }))}
                          disabled={resourceLoading || planningLoading}
                        >
                          <option value="">Select shift</option>
                          {(asArray(shifts)?.map((shift) => (
                            <option key={shift.shift_id} value={shift.shift_id}>
                              {shift.name} ({shift.start_time} - {shift.end_time})
                            </option>
                          ))) || []}
                        </select>
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Planned start date</label>
                        <input
                          type="date"
                          className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                          value={planForm.planned_start_date}
                          onChange={(event) => setPlanForm((current) => ({ ...current, planned_start_date: event.target.value }))}
                          disabled={planningLoading}
                          required
                        />
                      </div>
                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Planned end date</label>
                        <input
                          type="date"
                          className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                          value={planForm.planned_end_date}
                          onChange={(event) => setPlanForm((current) => ({ ...current, planned_end_date: event.target.value }))}
                          disabled={planningLoading}
                          required
                        />
                      </div>
                    </div>

                    {canOverride ? (
                      <div className="rounded-[22px] border border-amber-200 bg-amber-50/70 p-4">
                        <label className="flex items-start gap-3 text-sm text-slate-700">
                          <input
                            type="checkbox"
                            checked={planForm.ignore_conflicts}
                            onChange={(event) =>
                              setPlanForm((current) => ({
                                ...current,
                                ignore_conflicts: event.target.checked,
                                reason: event.target.checked ? current.reason : '',
                              }))
                            }
                            className="mt-1 h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                          />
                          <span>
                            Override capacity conflicts if needed
                            <span className="mt-1 block text-xs uppercase tracking-[0.16em] text-slate-500">
                              Supervisor/Admin/Owner only
                            </span>
                          </span>
                        </label>
                        {planForm.ignore_conflicts ? (
                          <textarea
                            className="mt-3 min-h-[96px] w-full rounded-2xl border border-amber-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                            placeholder="Reason for overriding the detected conflict"
                            value={planForm.reason}
                            onChange={(event) => setPlanForm((current) => ({ ...current, reason: event.target.value }))}
                            required
                          />
                        ) : null}
                      </div>
                    ) : (
                      <div className="rounded-[22px] border border-slate-200 bg-white p-4 text-sm text-slate-500">
                        Override controls are available only to Supervisors, Admins, and Owners.
                      </div>
                    )}

                    <div className="flex flex-wrap gap-3">
                      <button
                        type="submit"
                        disabled={planningLoading || resourceLoading}
                        className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {planningLoading ? 'Saving plan...' : 'Save plan'}
                      </button>
                      <div className="rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-500">
                        Step {currentOperation.sequence_number} currently {currentOperation.status}
                      </div>
                    </div>
                  </form>
                ) : !resourceLoading ? (
                  <div className="mt-5 rounded-[22px] border border-slate-200 bg-white p-4 text-sm text-slate-500">
                    {currentOperation
                      ? 'Only Planners, Supervisors, Admins, or Owners can assign schedules.'
                      : 'There is no open operation available to plan.'}
                  </div>
                ) : null}
              </section>

              <section className="rounded-[28px] border border-slate-100 bg-slate-50/80 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Selected machine schedule</p>
                <h3 className="mt-2 text-2xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
                  Capacity preview
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  Review planned work for the chosen machine in the selected window before you lock the schedule.
                </p>

                {machineScheduleLoading ? (
                  <p className="mt-5 text-sm text-slate-500">Loading machine schedule...</p>
                ) : machineSchedule.length > 0 ? (
                  <div className="mt-5 space-y-3">
                    {(asArray(machineSchedule)?.slice(0, 8).map((scheduledOperation) => (
                      <div key={scheduledOperation.job_operation_id} className="rounded-[22px] border border-slate-100 bg-white p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{scheduledOperation.job_number}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {scheduledOperation.planned_date} | Shift {shiftNameFor(scheduledOperation.shift_id, shifts)}
                            </p>
                            <p className="mt-2 text-sm text-slate-600">
                              {scheduledOperation.op_name} | Step {scheduledOperation.sequence_number}
                            </p>
                          </div>
                          <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                            {scheduledOperation.status}
                          </span>
                        </div>
                      </div>
                    ))) || []}
                  </div>
                ) : (
                  <div className="mt-5 rounded-[22px] border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">
                    Pick a machine and date window to preview its planned workload.
                  </div>
                )}
              </section>
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Operation timeline</p>
              <div className="mt-4 space-y-3">
                {asArray(jobDetail?.operations)
                  .slice()
                  .sort((left, right) => left.sequence_number - right.sequence_number)
                  .map((operation) => (
                    <div key={operation.job_operation_id} className={`rounded-[22px] border p-4 ${currentOperation?.job_operation_id === operation.job_operation_id ? 'border-sky-300 bg-sky-50' : 'border-slate-100 bg-white'}`}>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">
                            Step {operation.sequence_number}: {prettifyStage(operation.operation_id)}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {operation.job_operation_id} | Machine {machineNameFor(operation.machine_id, machines)} | Shift {shiftNameFor(operation.shift_id, shifts)}
                          </p>
                          {(operation.planned_start_date || operation.planned_end_date) ? (
                            <p className="mt-1 text-xs text-slate-500">
                              Planned {operation.planned_start_date || 'TBD'} to {operation.planned_end_date || 'TBD'}
                            </p>
                          ) : null}
                        </div>
                        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">{operation.status}</span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <AuditTrailPanel
                compact
                title="Job history"
                entries={jobAuditEntries}
                loading={auditLoading}
                emptyMessage="No job audit entries are available for this selection yet."
              />
              <AuditTrailPanel
                compact
                title="Current operation history"
                entries={operationAuditEntries}
                loading={auditLoading}
                emptyMessage="No current-operation audit entries are available yet."
              />
            </div>

            {/* Financial Summary Card */}
            <ErrorBoundary fallback={<div className="p-6 bg-emerald-50 rounded-[28px] border border-emerald-100 text-emerald-800 text-sm">Financial summary is temporarily unavailable.</div>}>
              <div className="rounded-[28px] border border-emerald-100 bg-gradient-to-br from-emerald-50 to-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">Financial Summary</p>
                <h3 className="mt-2 text-2xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>Job Cost Breakdown</h3>
                {costSummary ? (
                  <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    {[
                      { label: 'Machine Cost', value: costSummary.machine_cost, color: 'bg-sky-50 border-sky-100 text-sky-700' },
                      { label: 'Labour Cost', value: costSummary.labour_cost, color: 'bg-violet-50 border-violet-100 text-violet-700' },
                      { label: 'Material Cost', value: costSummary.material_cost, color: 'bg-amber-50 border-amber-100 text-amber-700' },
                      { label: 'Total Cost', value: costSummary.total_cost, color: 'bg-emerald-100 border-emerald-200 text-emerald-800' },
                    ].map(({ label, value, color }) => (
                      <div key={label} className={`rounded-[22px] border p-4 ${color}`}>
                        <div className="text-xs font-semibold uppercase tracking-[0.18em] opacity-70">{label}</div>
                        <div className="mt-2 text-xl font-bold">{formatINR(value)}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-slate-500">
                    Cost data is calculated nightly by the EventBridge cron job. Run the job or wait for the scheduled calculation to populate this summary.
                  </p>
                )}
                {costSummary?.last_calculated_at ? (
                  <p className="mt-3 text-xs text-slate-400">Last calculated: {new Date(costSummary.last_calculated_at).toLocaleString('en-IN')}</p>
                ) : null}

                {/* Profitability Bar Chart */}
                {costSummary && (quotedPriceInput !== '' || costSummary.total_cost != null) ? (() => {
                  const actual = costSummary.total_cost ?? 0
                  const quoted = parseFloat(quotedPriceInput) || 0
                  const chartData = [
                    { name: 'Production Cost', value: Number(actual), fill: '#0ea5e9' },
                    { name: 'Quoted Price', value: quoted, fill: '#10b981' },
                  ]
                  return (
                    <div className="mt-6">
                      <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Profitability Comparison</p>
                      <ResponsiveContainer width="100%" height={160}>
                        <BarChart data={chartData} barSize={40} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
                          <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} tickFormatter={(v) => `Rs.${(v / 1000).toFixed(0)}k`} />
                          <Tooltip
                            formatter={(value) => [formatINR(value), '']}
                            contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }}
                          />
                          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                            {chartData.map((entry) => (
                              <Cell key={entry.name} fill={entry.fill} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                      {quoted > 0 && (
                        <div className={`mt-3 rounded-[18px] border px-4 py-2.5 text-sm font-semibold ${quoted >= actual ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-rose-200 bg-rose-50 text-rose-700'}`}>
                          {quoted >= actual
                            ? `Profitable — margin of ${formatINR(quoted - actual)}`
                            : `Under-priced — shortfall of ${formatINR(actual - quoted)}`}
                        </div>
                      )}
                    </div>
                  )
                })() : null}

                {/* Quoted Price + Download Row */}
                <div className="mt-5 flex flex-wrap items-end gap-4">
                  <div className="flex-1 min-w-[200px]">
                    <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Quoted Price (₹)</label>
                    <div className="mt-2 flex gap-2">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                        placeholder="e.g. 25000.00"
                        value={quotedPriceInput}
                        onChange={(e) => setQuotedPriceInput(e.target.value)}
                      />
                      <button
                        type="button"
                        disabled={savingQuotedPrice || quotedPriceInput === ''}
                        onClick={saveQuotedPrice}
                        className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                      >
                        {savingQuotedPrice ? 'Saving…' : 'Save'}
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      disabled={recalculating}
                      onClick={onRecalculate}
                      className="rounded-full border border-emerald-300 bg-white px-4 py-2 text-sm font-semibold text-emerald-700 shadow-sm hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {recalculating ? 'Calculating...' : '⟳ Recalculate'}
                    </button>
                    <button
                      type="button"
                      disabled={downloadingPdf}
                      onClick={onDownloadInvoice}
                      className="rounded-full border border-violet-300 bg-violet-50 px-4 py-2 text-sm font-semibold text-violet-700 shadow-sm hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {downloadingPdf ? 'Generating PDF…' : '↓ Download Invoice'}
                    </button>
                  </div>
                </div>
              </div>
            </ErrorBoundary>
          </div>
        )}
      </div>

      {/* Complete with Quantities Modal */}
      {showCompleteModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[28px] border border-white/70 bg-white p-6 shadow-[0_28px_80px_rgba(15,23,42,0.28)]">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Mark as Complete</p>
            <h3 className="mt-2 text-2xl font-semibold text-slate-900">Record production quantities</h3>
            <div className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Qty Completed *</label>
                  <input
                    type="number"
                    min="0"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                    value={completeForm.quantity_completed}
                    onChange={(e) => setCompleteForm((c) => ({ ...c, quantity_completed: parseInt(e.target.value, 10) || 0 }))}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Qty Rejected</label>
                  <input
                    type="number"
                    min="0"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
                    value={completeForm.quantity_rejected}
                    onChange={(e) => setCompleteForm((c) => ({ ...c, quantity_rejected: parseInt(e.target.value, 10) || 0 }))}
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Actual Start</label>
                  <input
                    type="datetime-local"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                    value={completeForm.actual_start_time}
                    onChange={(e) => setCompleteForm((c) => ({ ...c, actual_start_time: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Actual End</label>
                  <input
                    type="datetime-local"
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                    value={completeForm.actual_end_time}
                    onChange={(e) => setCompleteForm((c) => ({ ...c, actual_end_time: e.target.value }))}
                  />
                </div>
              </div>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                disabled={actionLoading === 'complete'}
                onClick={() => {
                  onComplete(completeForm)
                  setShowCompleteModal(false)
                  setCompleteForm({ quantity_completed: 0, quantity_rejected: 0, actual_start_time: '', actual_end_time: '' })
                }}
                className="rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {actionLoading === 'complete' ? 'Saving...' : 'Confirm Complete'}
              </button>
              <button type="button" onClick={() => setShowCompleteModal(false)} className="rounded-full border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function DashboardPage({ auth: initialAuth = null }) {
  const [auth, setAuth] = useState(initialAuth)
  const [loading, setLoading] = useState(true)
  const [boardError, setBoardError] = useState('')
  const [board, setBoard] = useState({ wip_by_stage: [], stages: [] })
  const [selectedJob, setSelectedJob] = useState(null)
  const [jobLoading, setJobLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState('')
  const [auditLoading, setAuditLoading] = useState(false)
  const [jobAuditEntries, setJobAuditEntries] = useState([])
  const [operationAuditEntries, setOperationAuditEntries] = useState([])
  const [resourceLoading, setResourceLoading] = useState(true)
  const [resourceError, setResourceError] = useState('')
  const [machines, setMachines] = useState([])
  const [shifts, setShifts] = useState([])
  const [costSummary, setCostSummary] = useState(null)
  const [recalculating, setRecalculating] = useState(false)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [quotedPriceInput, setQuotedPriceInput] = useState('')
  const [savingQuotedPrice, setSavingQuotedPrice] = useState(false)

  const { data: jobDetail, mutate: mutateJobDetail, setData: setJobDetail } = useOptimisticUI(null)

  const columns = useMemo(() => buildColumns(board?.stages), [board?.stages])
  const totalWip = useMemo(
    () => (Array.isArray(board?.wip_by_stage) ? board.wip_by_stage : []).reduce((sum, stage) => sum + (stage.count || 0), 0),
    [board?.wip_by_stage],
  )

  async function loadBoard() {
    setLoading(true)
    setBoardError('')
    try {
      const data = await fetchWipMetrics()
      setBoard({
        wip_by_stage: Array.isArray(data?.wip_by_stage) ? data.wip_by_stage : [],
        stages: Array.isArray(data?.stages) ? data.stages : [],
      })
    } catch (error) {
      setBoard({ wip_by_stage: [], stages: [] })
      setBoardError(describeDashboardError(error, 'Unable to load the WIP dashboard right now.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBoard()
  }, [])

  useEffect(() => {
    async function loadPlanningResources() {
      setResourceLoading(true)
      setResourceError('')
      try {
        const [authContext, machineList, shiftList] = await Promise.all([
          initialAuth ? Promise.resolve(initialAuth) : getAuthContext().catch(() => null),
          fetchMachines(),
          fetchShifts(),
        ])
        setAuth(authContext)
        setMachines(asArray(machineList))
        setShifts(asArray(shiftList))
      } catch (error) {
        setMachines([])
        setShifts([])
        setResourceError(describeDashboardError(error, 'Planning resources are temporarily unavailable.'))
      } finally {
        setResourceLoading(false)
      }
    }

    loadPlanningResources()
  }, [initialAuth])

  async function loadAuditTrails(detail) {
    const currentOperation = getCurrentOperation(detail?.operations || [])
    if (!detail?.job?.job_id) {
      setJobAuditEntries([])
      setOperationAuditEntries([])
      return
    }

    setAuditLoading(true)
    try {
      const [jobAuditResponse, operationAuditResponse] = await Promise.all([
        fetchJobAudit(detail.job.job_id),
        currentOperation
          ? fetchJobOperationAudit(currentOperation.job_operation_id)
          : Promise.resolve({ audit_trail: [] }),
      ])

      setJobAuditEntries(jobAuditResponse.audit_trail || [])
      setOperationAuditEntries(operationAuditResponse.audit_trail || [])
    } catch {
      setJobAuditEntries([])
      setOperationAuditEntries([])
    } finally {
      setAuditLoading(false)
    }
  }

  async function openJob(job) {
    setSelectedJob(job)
    setJobLoading(true)
    setJobDetail(null)
    setJobAuditEntries([])
    setOperationAuditEntries([])
    setCostSummary(null)
    setQuotedPriceInput('')
    try {
      const data = await fetchJobById(job.job_id)
      setJobDetail(data)
      // Pre-fill quoted price if already set
      if (data?.job?.quoted_price != null) {
        setQuotedPriceInput(String(data.job.quoted_price))
      }
      await loadAuditTrails(data)
      try {
        const summary = await fetchJobCostSummary(job.job_id)
        setCostSummary(summary)
      } catch {
        setCostSummary(null)
      }
    } catch {
      setSelectedJob(null)
    } finally {
      setJobLoading(false)
    }
  }

  async function downloadCurrentInvoice() {
    if (!selectedJob?.job_id) return
    setDownloadingPdf(true)
    try {
      const blob = await downloadJobInvoice(selectedJob.job_id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `Invoice_${selectedJob.job_number || selectedJob.job_id}.pdf`
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      URL.revokeObjectURL(url)
      toast.success('Invoice downloaded')
    } catch {
      toast.error('Invoice generation failed. Ensure the backend has fpdf2 installed.')
    } finally {
      setDownloadingPdf(false)
    }
  }

  async function saveQuotedPrice() {
    if (!selectedJob?.job_id || quotedPriceInput === '') return
    const parsed = parseFloat(quotedPriceInput)
    if (Number.isNaN(parsed) || parsed < 0) {
      toast.error('Enter a valid positive price')
      return
    }
    setSavingQuotedPrice(true)
    try {
      await setJobQuotedPrice(selectedJob.job_id, parsed)
      toast.success(`Quoted price set to ${formatINR(parsed)}`)
    } catch {
      toast.error('Could not save quoted price')
    } finally {
      setSavingQuotedPrice(false)
    }
  }

  async function updateCurrentOperation(status, actionKey, extraPayload = {}) {
    const currentOp = getCurrentOperation(jobDetail?.operations || [])
    if (!currentOp) return

    setActionLoading(actionKey)
    
    // Optimistic Update
    const optimisticUpdater = (prev) => {
      if (!prev) return prev
      return {
        ...prev,
        operations: prev.operations.map(op => 
          op.job_operation_id === currentOp.job_operation_id 
            ? { ...op, status } 
            : op
        ),
        job: {
          ...prev.job,
          current_stage: status === 'COMPLETED' ? (prev.job.current_stage) : prev.job.current_stage // Simple heuristic
        }
      }
    }

    try {
      await mutateJobDetail(optimisticUpdater, async () => {
        const payload = {
          status,
          quantity_completed: extraPayload.quantity_completed ?? 0,
          quantity_rejected: extraPayload.quantity_rejected ?? 0,
          ...(extraPayload.actual_start_time && { actual_start_time: extraPayload.actual_start_time }),
          ...(extraPayload.actual_end_time && { actual_end_time: extraPayload.actual_end_time }),
        }
        await updateJobOperationStatus(currentOp.job_operation_id, payload)
        
        // Background sync to ensure consistency
        const refreshedJob = await fetchJobById(selectedJob.job_id)
        setJobDetail(refreshedJob)
        await loadAuditTrails(refreshedJob)
        await loadBoard()
      })
      toast.success(`${prettifyStage(currentOp.operation_id)} marked ${status}`)
    } catch {
      // Rollback is handled by mutateJobDetail
    } finally {
      setActionLoading('')
    }
  }

  async function planCurrentOperation(payload) {
    const currentOperation = getCurrentOperation(jobDetail?.operations || [])
    if (!currentOperation) return

    const updatedOperation = await planJobOperation(currentOperation.job_operation_id, payload)
    toast.success(`${prettifyStage(updatedOperation.operation_id)} assigned to ${machineNameFor(updatedOperation.machine_id, machines)}`)
    const refreshedJob = await fetchJobById(selectedJob.job_id)
    setJobDetail(refreshedJob)
    await loadAuditTrails(refreshedJob)
    await loadBoard()
  }

  async function recalculateCurrentJob() {
    if (!selectedJob?.job_id) return
    setRecalculating(true)
    try {
      const result = await recalculateJobCost(selectedJob.job_id)
      setCostSummary(result)
      toast.success(`Costs recalculated — Total: ${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(result.total_cost ?? 0)}`)
    } catch {
      toast.error('Cost recalculation failed. Ensure the job has COMPLETED operations with rate data.')
    } finally {
      setRecalculating(false)
    }
  }

  if (!auth?.token) {
    return (
      <div className="rounded-[24px] border border-white/70 bg-white/85 p-6 text-sm text-slate-600 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
        Loading your dashboard session...
      </div>
    )
  }

  if (!auth?.tenant_id || !auth?.user_role) {
    return (
      <div className="rounded-[24px] border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
        Dashboard session is incomplete. Please sign in again so tenant and role information can be restored.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <ErrorBoundary>
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
      </ErrorBoundary>iv>
      </section>

      {boardError ? (
        <div className="rounded-[24px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          {boardError}
        </div>
      ) : null}

      {resourceError ? (
        <div className="rounded-[24px] border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          {resourceError}
        </div>
      ) : null}

      {!loading && !boardError && columns.every((column) => asArray(column?.jobs).length === 0) ? (
        <div className="rounded-[24px] border border-dashed border-slate-200 bg-white/85 p-6 text-sm text-slate-600 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          <p className="font-semibold text-slate-900">No jobs are moving through the factory yet.</p>
          <p className="mt-2">Start with your first customer and part, then create a job to bring this dashboard to life.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link to="/master-data" className="rounded-full border border-slate-200 bg-white px-4 py-2 font-semibold text-slate-700 shadow-sm">
              Add master data
            </Link>
            <Link to="/jobs" className="rounded-full bg-slate-900 px-4 py-2 font-semibold text-white">
              Create first job
            </Link>
          </div>
        </div>
      ) : null}

      <section className="overflow-x-auto pb-2">
        <ErrorBoundary fallback={<div className="p-8 text-center bg-white rounded-3xl">Kanban board is currently unavailable.</div>}>
          <div className="flex min-w-max gap-5">
          {(asArray(columns)?.map((column) => (
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
                {(column?.jobs?.length || 0) > 0 ? (
                  (asArray(column?.jobs)?.map((job) => <JobCard key={job.job_id} job={job} onOpen={openJob} />) || [])
                ) : (
                  <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50/80 p-6 text-sm text-slate-400">
                    No jobs in this stage.
                  </div>
                )}
              </div>
            </article>
          ))) || []}
          </div>
        </ErrorBoundary>
      </section>

      {loading && <div className="rounded-[24px] border border-white/70 bg-white/85 p-5 text-sm text-slate-500 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">Refreshing WIP board...</div>}
      {resourceLoading && <div className="rounded-[24px] border border-white/70 bg-white/85 p-5 text-sm text-slate-500 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">Loading machines...</div>}

      <JobActionModal
        open={Boolean(selectedJob)}
        auth={auth}
        machines={machines}
        shifts={shifts}
        resourceLoading={resourceLoading}
        jobDetail={jobDetail}
        loading={jobLoading}
        actionLoading={actionLoading}
        auditLoading={auditLoading}
        jobAuditEntries={jobAuditEntries}
        operationAuditEntries={operationAuditEntries}
        costSummary={costSummary}
        recalculating={recalculating}
        onClose={() => {
          setSelectedJob(null)
          setJobDetail(null)
          setActionLoading('')
          setAuditLoading(false)
          setJobAuditEntries([])
          setOperationAuditEntries([])
          setCostSummary(null)
        }}
        onStart={() => updateCurrentOperation('IN_PROGRESS', 'start')}
        onComplete={(form) => updateCurrentOperation('COMPLETED', 'complete', form)}
        onPlan={planCurrentOperation}
        onRecalculate={recalculateCurrentJob}
        downloadingPdf={downloadingPdf}
        quotedPriceInput={quotedPriceInput}
        setQuotedPriceInput={setQuotedPriceInput}
        saveQuotedPrice={saveQuotedPrice}
        onDownloadInvoice={downloadCurrentInvoice}
      />
    </div>
  )
}
