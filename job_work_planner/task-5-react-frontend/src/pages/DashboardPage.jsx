/**
 * PROJECT ROODHA - INDUSTRIAL COMMAND CENTER
 * FILE: DashboardPage.jsx
 * PURPOSE: Central intelligence hub for real-time shop floor visibility.
 *          Implements Kanban stage management, proactive delay alerts, and financial costing summaries.
 */

import React, { useEffect, useMemo, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import AuditTrailPanel from '../components/AuditTrailPanel'
import { getAuthContext } from '../lib/auth'
import { authenticatedFetch, APIError } from '../lib/authenticatedFetch'
import { hasPermission, normalizeRole } from '../lib/roles'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts'
import useOptimisticUI from '../hooks/useOptimisticUI'
import ErrorBoundary from '../components/common/ErrorBoundary'
import MachineLoadRadar from '../components/dashboard/MachineLoadRadar'

// ---------------------------------------------------------
// --- INDUSTRIAL DATA FORMATTING ---
// ---------------------------------------------------------

function formatINR(value) {
  if (value == null || value === '') return '—'
  const num = Number(value)
  if (Number.isNaN(num)) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num)
}

function formatINRMono(value) {
  return <span className="font-mono tabular-nums">{formatINR(value)}</span>
}

// ---------------------------------------------------------
// --- KANBAN & STAGE UTILITIES ---
// ---------------------------------------------------------

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

function statusBadgeClass(status) {
  const normalized = String(status || '').toUpperCase()

  if (normalized === 'DELAYED') {
    return 'border border-[#FF6B00]/50 bg-[#FF6B00]/15 text-[#FF6B00] animate-pulse'
  }
  if (normalized === 'COMPLETED') {
    return 'border border-orange-500/40 bg-orange-500/15 text-orange-300'
  }
  if (normalized === 'IN_PROGRESS') {
    return 'border border-orange-500 bg-orange-500 text-[#0F172A]'
  }
  return 'border border-slate-700 bg-slate-900 text-slate-300'
}

function getCurrentOperation(operations = []) {
  return [...asArray(operations)]
    .sort((left, right) => left.sequenceNumber - right.sequenceNumber)
    .find((operation) => operation.status !== 'COMPLETED')
}

function buildColumns(stages = []) {
  const safeStages = asArray(stages)
  const stageMap = new Map(safeStages.map((stage) => [stage.stageId, stage]))
  const orderedIds = [
    ...defaultStageOrder.filter((stageId) => stageMap.has(stageId)),
    ...safeStages
      .map((stage) => stage.stageId)
      .filter((stageId) => !defaultStageOrder.includes(stageId)),
  ]

  const baseIds = orderedIds.length > 0 ? orderedIds : defaultStageOrder

  return baseIds.map((stageId) => {
    const stage = stageMap.get(stageId)
    return {
      stageId,
      stageName: stage?.stageName || prettifyStage(stageId),
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
        shiftId,
        plannedDate: date,
      })) || []),
      ),
    )
    .sort((left, right) => {
      if (left.plannedDate === right.plannedDate) {
        return (left.sequenceNumber || 0) - (right.sequenceNumber || 0)
      }
      return (left.plannedDate || '').localeCompare(right.plannedDate || '')
    })
}

function machineNameFor(machineId, machines = []) {
  return asArray(machines)?.find((machine) => machine.machineId === machineId)?.name || machineId || 'Unassigned'
}

function shiftNameFor(shiftId, shifts = []) {
  return asArray(shifts)?.find((shift) => shift.shiftId === shiftId)?.name || shiftId || 'No shift'
}

function describeDashboardError(error, fallbackMessage) {
  if (!error) return fallbackMessage
  if (error?.status === 0 || error?.isTimeout) return ''
  const responseDetail = error?.response?.data?.detail
  if (typeof responseDetail === 'string' && responseDetail.trim()) return responseDetail
  if (typeof error?.message === 'string' && error.message.trim()) {
    if (
      error.message === 'Network Error' ||
      error.message.includes('Connection lost while calling') ||
      error.message.includes('Machine Link Timeout')
    ) {
      return ''
    }
    return error.message
  }
  return fallbackMessage
}

// ---------------------------------------------------------
// --- PROACTIVE DELAY GUARD & ALERTS ---
// ---------------------------------------------------------

/**
 * @module ProactiveDelayGuard v1.5.6 - Section 7.3 Notifications
 * Calculates priority based on due date proximity.
 */
function getAlertPriority(job) {
  const explicitPriority = job?.alertPriority || job?.alert_priority
  if (explicitPriority) return String(explicitPriority).toUpperCase()

  if (!job?.dueDate) return 'NORMAL'
  const dueDate = new Date(job.dueDate)
  if (Number.isNaN(dueDate.getTime())) return 'NORMAL'

  const now = new Date()
  const hoursUntilDue = (dueDate.getTime() - now.getTime()) / (1000 * 60 * 60)
  if (hoursUntilDue < 0) return 'CRITICAL'
  if (hoursUntilDue <= 24) return 'HIGH'
  return 'NORMAL'
}

function alertBadgeFor(priority) {
  if (priority === 'CRITICAL') {
    return {
      label: '⚠️ OVERDUE',
      className: 'bg-[#FF6B00] text-[#0F172A] pulse-safety-orange',
    }
  }
  if (priority === 'HIGH') {
    return {
      label: '⏳ DUE SOON',
      className: 'bg-orange-500 text-[#0F172A]',
    }
  }
  return null
}

// ---------------------------------------------------------
// --- EXECUTION & PLANNING MODALS ---
// ---------------------------------------------------------

function JobCard({ job, onOpen }) {
  const alertBadge = alertBadgeFor(getAlertPriority(job))
  const statusColor = getAlertPriority(job) === 'CRITICAL' ? 'border-l-[#FF6B00] shadow-[0_0_28px_rgba(255,107,0,0.24)]' : job.priority === 'HIGH' ? 'border-l-orange-500' : 'border-l-slate-500'

  return (
    <button
      type="button"
      onClick={() => onOpen(job)}
      className={`w-full rounded-xl border-y border-r border-slate-700 bg-slate-900 px-4 py-5 text-left transition-all hover:bg-slate-800 active:scale-[0.98] border-l-4 ${statusColor}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-500 truncate">{job.customerName}</p>
          <h3 className="mt-1 text-base font-black tracking-tight text-white font-mono truncate">{job.jobNumber}</h3>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {alertBadge ? (
            <span className={`rounded-sm px-2 py-1 text-[10px] font-black uppercase tracking-widest shadow-lg font-mono tabular-nums ${alertBadge.className}`}>
              {alertBadge.label}
            </span>
          ) : null}
          {job.priority === 'HIGH' && (
            <div className="flex h-6 w-6 items-center justify-center rounded-sm bg-orange-500 text-[10px] font-black text-white shadow-lg animate-pulse">
              !
            </div>
          )}
        </div>
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
  const [completeForm, setCompleteForm] = useState({
    quantityCompleted: 0,
    quantityRejected: 0,
    actualStartTime: '',
    actualEndTime: '',
  })
  const [planForm, setPlanForm] = useState({
    machineId: '',
    shiftId: '',
    plannedStartDate: isoDateWithOffset(0),
    plannedEndDate: isoDateWithOffset(7),
    ignoreConflicts: false,
    reason: '',
  })
  const [activeTab, setActiveTab] = useState('details')

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
      machineId: currentOperation?.machineId || '',
      shiftId: currentOperation?.shiftId || '',
      plannedStartDate: currentOperation?.plannedStartDate || isoDateWithOffset(0),
      plannedEndDate: currentOperation?.plannedEndDate || isoDateWithOffset(7),
      ignoreConflicts: false,
      reason: '',
    })
  }, [currentOperation?.jobOperationId, currentOperation?.machineId, currentOperation?.shiftId, currentOperation?.plannedStartDate, currentOperation?.plannedEndDate])

  useEffect(() => {
    async function loadMachineSchedule() {
      if (!open || !planForm.machineId || !planForm.plannedStartDate || !planForm.plannedEndDate) {
        setMachineSchedule([])
        return
      }

      setMachineScheduleLoading(true)
      try {
        const response = await authenticatedFetch('planning/calendar', {
          params: {
            machine_id: planForm.machineId,
            from_date: planForm.plannedStartDate,
            to_date: planForm.plannedEndDate,
          }
        })
        setMachineSchedule(flattenMachineSchedule(response, planForm.machineId))
      } catch {
        setMachineSchedule([])
      } finally {
        setMachineScheduleLoading(false)
      }
    }

    loadMachineSchedule()
  }, [open, planForm.machineId, planForm.plannedStartDate, planForm.plannedEndDate])

  if (!open) return null

  async function handlePlanSubmit(event) {
    event.preventDefault()
    if (!currentOperation || !canPlan) return

    setPlanningLoading(true)
    setPlanningError(null)

    try {
      await onPlan({
        machineId: planForm.machineId,
        shiftId: planForm.shiftId || null,
        plannedStartDate: planForm.plannedStartDate,
        plannedEndDate: planForm.plannedEndDate,
        ignoreConflicts: canOverride ? planForm.ignoreConflicts : false,
        force: canOverride ? planForm.ignoreConflicts : false,
        reason: canOverride ? planForm.reason || null : null,
      })
    } catch (error) {
      const detail = error?.detail
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
      <div className="max-h-[90vh] w-full max-w-5xl overflow-auto rounded-[32px] border border-slate-700 bg-slate-800 p-6 shadow-[0_28px_90px_rgba(15,23,42,0.28)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Execution and planning</p>
            <h2 className="mt-2 text-3xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
              {jobDetail?.job?.jobNumber || 'Loading job'}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300">
            Close
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="mt-6 flex border-b border-slate-100 px-2">
          <button
            onClick={() => setActiveTab('details')}
            className={`pb-4 pt-1 text-sm font-semibold tracking-wide transition-all ${activeTab === 'details' ? 'border-b-2 border-slate-900 text-white' : 'text-slate-400 hover:text-slate-300'
              }`}
          >
            OPERATION & PLANNING
          </button>
          <button
            onClick={() => setActiveTab('costing')}
            className={`ml-8 pb-4 pt-1 text-sm font-semibold tracking-wide transition-all ${activeTab === 'costing' ? 'border-b-2 border-slate-900 text-white' : 'text-slate-400 hover:text-slate-300'
              }`}
          >
            COSTING & MARGIN
          </button>
        </div>

        {loading ? (
          <p className="mt-8 text-sm text-slate-500">Loading job details...</p>
        ) : activeTab === 'details' ? (
          <div className="mt-6 space-y-6">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-[24px] border border-slate-800 bg-slate-900/50 p-5">
                <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Current stage</div>
                <div className="mt-2 text-lg font-black text-white uppercase tracking-tight">{prettifyStage(jobDetail?.job?.currentStage)}</div>
              </div>
              <div className="rounded-[24px] border border-slate-800 bg-slate-900/50 p-5">
                <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Due date</div>
                <div className="mt-2 text-lg font-black text-white font-mono tabular-nums">{jobDetail?.job?.dueDate}</div>
              </div>
              <div className="rounded-[24px] border border-slate-800 bg-slate-900/50 p-5">
                <div className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Priority</div>
                <div className="mt-2 text-lg font-black text-orange-500 uppercase tracking-widest">{jobDetail?.job?.priority}</div>
              </div>
            </div>

            <div className="rounded-[26px] border border-slate-100 bg-slate-800/80 p-5">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Current operation</p>
                  <h3 className="mt-2 text-xl font-semibold text-white">
                    {currentOperation ? `${prettifyStage(currentOperation.operationId)} (${currentOperation.status})` : 'No open operation'}
                  </h3>
                  {currentOperation ? (
                    <p className="mt-2 text-sm text-slate-500">
                      Step {currentOperation.sequenceNumber} | Machine {machineNameFor(currentOperation.machineId, machines)} | Shift{' '}
                      {shiftNameFor(currentOperation.shiftId, shifts)}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={!canStart || actionLoading}
                    onClick={onStart}
                    className="rounded-full border border-orange-500/40 bg-orange-500/10 px-5 py-2.5 text-sm font-semibold text-orange-300 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {actionLoading === 'start' ? 'Starting...' : 'Start'}
                  </button>
                  <button
                    type="button"
                    disabled={!canComplete || actionLoading}
                    onClick={() => setShowCompleteModal(true)}
                    className="rounded-full border border-orange-500 bg-orange-500 px-5 py-2.5 text-sm font-semibold text-[#0F172A] disabled:cursor-not-allowed disabled:opacity-40"
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
              <section className="rounded-[28px] border border-slate-100 bg-slate-800/80 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Planning workflow</p>
                    <h3 className="mt-2 text-2xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
                      Assign machine and shift
                    </h3>
                  </div>
                  <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                    {canPlan ? normalizedRole || 'Planner' : 'View only'}
                  </span>
                </div>

                {planningError ? (
                  <div className="mt-5 rounded-[22px] border border-orange-500/30 bg-slate-900 p-4 text-sm text-orange-300">
                    <p className="font-semibold">{planningError.error || 'Planning conflict detected.'}</p>
                    {planningError.resolution ? <p className="mt-2">{planningError.resolution}</p> : null}
                    {Array.isArray(planningError.clashes) && planningError.clashes.length > 0 ? (
                      <div className="mt-3 space-y-2">
                        {(asArray(planningError.clashes)?.map((clash) => (
                          <div key={clash.jobOperationId} className="rounded-2xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300 shadow-sm">
                            {clash.jobNumber} | Step {clash.sequenceNumber} | {clash.plannedStartDate} to {clash.plannedEndDate} | Shift{' '}
                            {shiftNameFor(clash.shiftId, shifts)}
                          </div>
                        ))) || []}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {resourceLoading ? (
                  <div className="mt-5 rounded-[22px] border border-slate-700 bg-slate-800 p-4 text-sm text-slate-500">
                    Loading machines...
                  </div>
                ) : null}

                {!resourceLoading && canPlan && currentOperation ? (
                  <form className="mt-5 space-y-4" onSubmit={handlePlanSubmit}>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Machine</label>
                        <select
                          className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
                          value={planForm.machineId}
                          onChange={(event) => setPlanForm((current) => ({ ...current, machineId: event.target.value }))}
                          disabled={resourceLoading || planningLoading}
                          required
                        >
                          <option value="">Select machine</option>
                          {(asArray(activeMachines)?.map((machine) => (
                            <option key={machine.machineId} value={machine.machineId}>
                              {machine.name} ({machine.type})
                            </option>
                          ))) || []}
                        </select>
                      </div>

                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Shift</label>
                        <select
                          className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
                          value={planForm.shiftId}
                          onChange={(event) => setPlanForm((current) => ({ ...current, shiftId: event.target.value }))}
                          disabled={resourceLoading || planningLoading}
                        >
                          <option value="">Select shift</option>
                          {(asArray(shifts)?.map((shift) => (
                            <option key={shift.shiftId} value={shift.shiftId}>
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
                          className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
                          value={planForm.plannedStartDate}
                          onChange={(event) => setPlanForm((current) => ({ ...current, plannedStartDate: event.target.value }))}
                          disabled={planningLoading}
                          required
                        />
                      </div>
                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Planned end date</label>
                        <input
                          type="date"
                          className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
                          value={planForm.plannedEndDate}
                          onChange={(event) => setPlanForm((current) => ({ ...current, plannedEndDate: event.target.value }))}
                          disabled={planningLoading}
                          required
                        />
                      </div>
                    </div>

                    {canOverride ? (
                      <div className="rounded-[22px] border border-slate-700 bg-slate-900 p-4">
                        <label className="flex items-start gap-3 text-sm text-slate-300">
                          <input
                            type="checkbox"
                            checked={planForm.ignoreConflicts}
                            onChange={(event) =>
                              setPlanForm((current) => ({
                                ...current,
                                ignoreConflicts: event.target.checked,
                                reason: event.target.checked ? current.reason : '',
                              }))
                            }
                            className="mt-1 h-4 w-4 rounded border-slate-500 bg-slate-900 text-orange-500 focus:ring-orange-500"
                          />
                          <span>
                            Override capacity conflicts if needed
                            <span className="mt-1 block text-xs uppercase tracking-[0.16em] text-slate-500">
                              Supervisor/Admin/Owner only
                            </span>
                          </span>
                        </label>
                        {planForm.ignoreConflicts ? (
                          <textarea
                            className="mt-3 min-h-[96px] w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
                            placeholder="Reason for overriding the detected conflict"
                            value={planForm.reason}
                            onChange={(event) => setPlanForm((current) => ({ ...current, reason: event.target.value }))}
                            required
                          />
                        ) : null}
                      </div>
                    ) : (
                      <div className="rounded-[22px] border border-slate-700 bg-slate-800 p-4 text-sm text-slate-500">
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
                      <div className="rounded-full border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm text-slate-500">
                        Step {currentOperation.sequenceNumber} currently {currentOperation.status}
                      </div>
                    </div>
                  </form>
                ) : !resourceLoading ? (
                  <div className="mt-5 rounded-[22px] border border-slate-700 bg-slate-800 p-4 text-sm text-slate-500">
                    {currentOperation
                      ? 'Only Planners, Supervisors, Admins, or Owners can assign schedules.'
                      : 'There is no open operation available to plan.'}
                  </div>
                ) : null}
              </section>

              <section className="rounded-[28px] border border-slate-100 bg-slate-800/80 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Selected machine schedule</p>
                <h3 className="mt-2 text-2xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
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
                      <div key={scheduledOperation.jobOperationId} className="rounded-[22px] border border-slate-100 bg-slate-800 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-white">{scheduledOperation.jobNumber}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {scheduledOperation.plannedDate} | Shift {shiftNameFor(scheduledOperation.shiftId, shifts)}
                            </p>
                            <p className="mt-2 text-sm text-slate-300">
                              {scheduledOperation.opName} | Step {scheduledOperation.sequenceNumber}
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
                  <div className="mt-5 rounded-[22px] border border-dashed border-slate-700 bg-slate-800 p-4 text-sm text-slate-500">
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
                  .sort((left, right) => left.sequenceNumber - right.sequenceNumber)
                  .map((operation) => (
                    <div key={operation.jobOperationId} className={`rounded-[22px] border p-4 ${currentOperation?.jobOperationId === operation.jobOperationId ? 'border-orange-500/40 bg-slate-900' : 'border-slate-700 bg-slate-800'}`}>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-white">
                            Step {operation.sequenceNumber}: {prettifyStage(operation.operationId)}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {operation.jobOperationId} | Machine {machineNameFor(operation.machineId, machines)} | Shift {shiftNameFor(operation.shiftId, shifts)}
                          </p>
                          {(operation.plannedStartDate || operation.plannedEndDate) ? (
                            <p className="mt-1 text-xs text-slate-500">
                              Planned {operation.plannedStartDate || 'TBD'} to {operation.plannedEndDate || 'TBD'}
                            </p>
                          ) : null}
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusBadgeClass(operation.status)}`}>{operation.status}</span>
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
          </div>
        ) : (
          /* COSTING TAB */
          <div className="mt-6 space-y-6">
            <ErrorBoundary>
              <div className="rounded-[28px] border border-slate-100 bg-slate-800/80 p-6">
                <div className="flex items-center justify-between gap-4 mb-8">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Financial overview</p>
                    <h3 className="mt-2 text-2xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
                      Routed job cost analysis
                    </h3>
                  </div>
                  <div className="flex gap-3">
                    <button
                      type="button"
                      disabled={recalculating || jobLoading}
                      onClick={onRecalculate}
                      className="rounded-full border border-orange-500/40 bg-orange-500/10 px-5 py-2.5 text-sm font-bold text-orange-300 transition hover:bg-orange-500/20 disabled:opacity-50"
                    >
                      {recalculating ? 'Recalculating...' : 'Refresh calculations'}
                    </button>
                    <button
                      type="button"
                      disabled={downloadingPdf || jobLoading}
                      onClick={onDownloadInvoice}
                      className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800 disabled:opacity-50"
                    >
                      {downloadingPdf ? 'Generating PDF...' : 'Download Invoice'}
                    </button>
                  </div>
                </div>

                {costSummary ? (
                  <div className="grid gap-6">
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="rounded-[24px] bg-slate-900/50 p-6 border border-slate-800">
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2">Total estimated cost</p>
                        <p className="text-2xl font-black text-white font-mono">{formatINR(costSummary.totalCost || costSummary.total_cost)}</p>
                      </div>
                      <div className="rounded-[24px] bg-slate-900/50 p-6 border border-slate-800">
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2">Labor and Machine</p>
                        <p className="text-2xl font-black text-white font-mono">{formatINR(costSummary.totalProcessCost || costSummary.total_process_cost)}</p>
                      </div>
                      <div className="rounded-[24px] bg-slate-900/50 p-6 border border-slate-800">
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2">Material cost</p>
                        <p className="text-2xl font-black text-white font-mono">{formatINR(costSummary.materialCost || costSummary.material_cost)}</p>
                      </div>
                    </div>

                    {(() => {
                      const actual = costSummary.totalCost || costSummary.total_cost || 0
                      const quoted = parseFloat(quotedPriceInput) || jobDetail?.job?.quotedPrice || 0
                      const margin = quoted > 0 ? ((quoted - actual) / quoted) * 100 : 0
                      const isPositive = margin >= 0

                      return (
                        <>
                          <div className={`rounded-[24px] p-6 border ${isPositive ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-rose-500/30 bg-rose-500/5'}`}>
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2">Estimated Gross Margin</p>
                                <p className={`text-4xl font-black font-mono ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                                  {isPositive ? '+' : ''}{margin.toFixed(2)}%
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2">Projected Profit</p>
                                <p className={`text-2xl font-black font-mono ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                                  {formatINR(quoted - actual)}
                                </p>
                              </div>
                            </div>
                          </div>

                          {quoted > 0 && (
                            <div className="mt-6">
                              <p className="mb-4 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 text-center">Cost vs Revenue</p>
                              <div className="h-[200px] w-full">
                                <ResponsiveContainer>
                                  <BarChart data={[
                                    { name: 'Total Cost', value: Number(actual), fill: '#0f172a' },
                                    { name: 'Quoted Price', value: quoted, fill: '#10b981' },
                                  ]} barSize={50}>
                                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fontWeight: 600 }} />
                                    <YAxis hide domain={[0, 'auto']} />
                                    <Tooltip formatter={(v) => formatINR(v)} cursor={{ fill: 'transparent' }} />
                                    <Bar dataKey="value" radius={[12, 12, 0, 0]} />
                                  </BarChart>
                                </ResponsiveContainer>
                              </div>
                            </div>
                          )}
                        </>
                      )
                    })()}
                  </div>
                ) : (
                  <div className="mt-8 rounded-[24px] border border-dashed border-slate-700 p-8 text-center text-slate-500">
                    Calculated cost data is not yet available for this job.
                  </div>
                )}

                <div className="mt-8 border-t border-slate-100 pt-6">
                  <div className="max-w-md">
                    <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Adjust Quoted Price (Customer Billing)</label>
                    <div className="mt-3 flex gap-3">
                      <div className="relative flex-1">
                        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 font-semibold">₹</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          className="w-full rounded-2xl border border-slate-700 bg-slate-800 pl-8 pr-4 py-3 text-sm font-semibold text-slate-300 outline-none focus:border-orange-500 focus:ring-4 focus:ring-orange-500/20"
                          placeholder="0.00"
                          value={quotedPriceInput}
                          onChange={(e) => setQuotedPriceInput(e.target.value)}
                        />
                      </div>
                      <button
                        type="button"
                        disabled={saveQuotedPrice === true || quotedPriceInput === ''}
                        onClick={saveQuotedPrice}
                        className="rounded-2xl bg-slate-900 px-6 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:opacity-50"
                      >
                        Update Price
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </ErrorBoundary>

            <AuditTrailPanel
              compact
              title="Financial History"
              entries={jobAuditEntries}
              loading={auditLoading}
              emptyMessage="No financial trail detected for this job."
            />
          </div>
        )}
      </div>

      {/* Complete with Quantities Modal */}
      {showCompleteModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[28px] border border-slate-700 bg-slate-800 p-6 shadow-[0_28px_80px_rgba(15,23,42,0.28)]">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Mark as Complete</p>
            <h3 className="mt-2 text-2xl font-semibold text-white">Record production quantities</h3>
            <div className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 font-mono">Qty Completed *</label>
                  <input
                    type="number"
                    min="0"
                    className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20 font-mono"
                    value={completeForm.quantityCompleted}
                    onChange={(e) => setCompleteForm((c) => ({ ...c, quantityCompleted: parseInt(e.target.value, 10) || 0 }))}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 font-mono">Qty Rejected</label>
                  <input
                    type="number"
                    min="0"
                    className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20 font-mono"
                    value={completeForm.quantityRejected}
                    onChange={(e) => setCompleteForm((c) => ({ ...c, quantityRejected: parseInt(e.target.value, 10) || 0 }))}
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Actual Start</label>
                  <input
                    type="datetime-local"
                    className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
                    value={completeForm.actualStartTime}
                    onChange={(e) => setCompleteForm((c) => ({ ...c, actualStartTime: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Actual End</label>
                  <input
                    type="datetime-local"
                    className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-300 shadow-sm outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
                    value={completeForm.actualEndTime}
                    onChange={(e) => setCompleteForm((c) => ({ ...c, actualEndTime: e.target.value }))}
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
                  setCompleteForm({ quantityCompleted: 0, quantityRejected: 0, actualStartTime: '', actualEndTime: '' })
                }}
                className="rounded-full bg-orange-500 px-5 py-2.5 text-sm font-semibold text-[#0F172A] disabled:opacity-60"
              >
                {actionLoading === 'complete' ? 'Saving...' : 'Confirm Complete'}
              </button>
              <button type="button" onClick={() => setShowCompleteModal(false)} className="rounded-full border border-slate-700 px-5 py-2.5 text-sm font-semibold text-slate-300">
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
  const [dashboardMetrics, setDashboardMetrics] = useState({
    onTimePercentage: null,
  })

  const { data: jobDetail, mutate: mutateJobDetail, setData: setJobDetail } = useOptimisticUI(null)

  const isSyncing = loading || resourceLoading
  const isAuthenticated = Boolean(auth?.isAuthenticated || auth?.token)
  const tenantId = auth?.tenantId || auth?.tenant_id || null
  const userRole = auth?.userRole || auth?.user_role || null
  const normalizedUserRole = normalizeRole(userRole)
  const canViewMachineLoad = hasPermission(normalizedUserRole, 'machineLoad')
  const canExportJobs = hasPermission(normalizedUserRole, 'exports')
  const canPlan = hasPermission(normalizedUserRole, 'plan')
  const dashboardErrors = useMemo(
    () => Array.from(new Set([boardError, resourceError].filter(Boolean))),
    [boardError, resourceError],
  )
  const visibleDashboardErrors = useMemo(() => dashboardErrors.slice(0, 1), [dashboardErrors])
  const hasDashboardErrors = dashboardErrors.length > 0

  const columns = useMemo(() => buildColumns(board?.stages), [board?.stages])
  const totalWip = useMemo(
    () => (asArray(board?.stages)).reduce((sum, stage) => sum + (stage.counts?.total || 0), 0),
    [board?.stages],
  )
  const delayedJobs = useMemo(
    () => (asArray(board?.stages)).reduce((sum, stage) => sum + (stage.counts?.delayed || 0), 0),
    [board?.stages],
  )

  const loadBoard = useCallback(async () => {
    setLoading(true)
    setBoardError('')
    try {
      const data = await authenticatedFetch('kanban')
      setBoard({
        stages: Array.isArray(data?.stages) ? data.stages : [],
      })
    } catch (error) {
      setBoard({ stages: [] })
      setBoardError(describeDashboardError(error, 'Unable to load the WIP dashboard right now.'))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadAuditTrails = useCallback(async (detail) => {
    const currentOperation = getCurrentOperation(detail?.operations || [])
    if (!detail?.job?.jobId) {
      setJobAuditEntries([])
      setOperationAuditEntries([])
      return
    }

    setAuditLoading(true)
    try {
      const [jobAuditResponse, operationAuditResponse] = await Promise.all([
        authenticatedFetch(`jobs/${detail.job.jobId}/audit`),
        currentOperation
          ? authenticatedFetch(`job-operations/${currentOperation.jobOperationId}/audit`)
          : Promise.resolve({ auditTrail: [] }),
      ])

      setJobAuditEntries(jobAuditResponse.auditTrail || [])
      setOperationAuditEntries(operationAuditResponse.auditTrail || [])
    } catch {
      setJobAuditEntries([])
      setOperationAuditEntries([])
    } finally {
      setAuditLoading(false)
    }
  }, [])

  const openJob = useCallback(async (job) => {
    setSelectedJob(job)
    setJobLoading(true)
    setJobDetail(null)
    setJobAuditEntries([])
    setOperationAuditEntries([])
    setCostSummary(null)
    setQuotedPriceInput('')
    try {
      const data = await authenticatedFetch(`jobs/${job.jobId}`)
      setJobDetail(data)
      if (data?.job?.quotedPrice != null) {
        setQuotedPriceInput(String(data.job.quotedPrice))
      }
      await loadAuditTrails(data)
      try {
        const summary = await authenticatedFetch(`jobs/${job.jobId}/cost-summary`)
        setCostSummary(summary)
      } catch {
        setCostSummary(null)
      }
    } catch {
      setSelectedJob(null)
    } finally {
      setJobLoading(false)
    }
  }, [loadAuditTrails, setJobDetail])

  const downloadCurrentInvoice = useCallback(async () => {
    if (!selectedJob?.jobId) return
    setDownloadingPdf(true)
    try {
      const blob = await authenticatedFetch(`jobs/${selectedJob.jobId}/invoice`, {
        transformResponse: false
      }).then(res => res.blob())
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `Invoice_${selectedJob.jobNumber || selectedJob.jobId}.pdf`
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
  }, [selectedJob])

  const saveQuotedPrice = useCallback(async () => {
    if (!selectedJob?.jobId || quotedPriceInput === '') return
    const parsed = parseFloat(quotedPriceInput)
    if (Number.isNaN(parsed) || parsed < 0) {
      toast.error('Enter a valid positive price')
      return
    }
    setSavingQuotedPrice(true)
    try {
      await authenticatedFetch(`jobs/${selectedJob.jobId}/quoted-price`, {
        method: 'POST',
        body: JSON.stringify({ quoted_price: parsed })
      })
      toast.success(`Quoted price updated`)
      // Refresh job detail to show new margin
      const data = await authenticatedFetch(`jobs/${selectedJob.jobId}`)
      setJobDetail(data)
    } catch {
      toast.error('Could not save quoted price')
    } finally {
      setSavingQuotedPrice(false)
    }
  }, [selectedJob, quotedPriceInput, setJobDetail])

  const handleExport = useCallback(async () => {
    if (!canExportJobs) {
      toast.error('CSV exports are restricted to owners.')
      return
    }
    setActionLoading('export')
    try {
      const result = await authenticatedFetch('exports/jobs', { method: 'POST' })
      if (result?.downloadUrl) {
        const anchor = document.createElement('a')
        anchor.href = result.downloadUrl
        anchor.setAttribute('download', result.filename || 'active_jobs.csv')
        document.body.appendChild(anchor)
        anchor.click()
        document.body.removeChild(anchor)
        toast.success(`Export successful`)
      } else {
        throw new Error('No download URL returned')
      }
    } catch {
      toast.error('Export failed')
    } finally {
      setTimeout(() => setActionLoading(''), 2000)
    }
  }, [canExportJobs])


  const updateCurrentOperation = useCallback(async (status, actionKey, extraPayload = {}) => {
    const currentOp = getCurrentOperation(jobDetail?.operations || [])
    if (!currentOp) return

    setActionLoading(actionKey)

    const optimisticUpdater = (prev) => {
      if (!prev) return prev
      return {
        ...prev,
        operations: prev.operations.map(op =>
          op.jobOperationId === currentOp.jobOperationId
            ? { ...op, status }
            : op
        )
      }
    }

    try {
      await mutateJobDetail(optimisticUpdater, async () => {
        const payload = {
          status,
          quantityCompleted: extraPayload.quantityCompleted ?? 0,
          quantityRejected: extraPayload.quantityRejected ?? 0,
          ...(extraPayload.actualStartTime && { actualStartTime: extraPayload.actualStartTime }),
          ...(extraPayload.actualEndTime && { actualEndTime: extraPayload.actualEndTime }),
        }
        await authenticatedFetch(`job-operations/${currentOp.jobOperationId}/status`, {
          method: 'PATCH',
          body: JSON.stringify(payload)
        })

        const refreshedJob = await authenticatedFetch(`jobs/${selectedJob.jobId}`)
        setJobDetail(refreshedJob)
        await loadAuditTrails(refreshedJob)
        await loadBoard()
      })
      toast.success(`${prettifyStage(currentOp.operationId)} marked ${status}`)
    } catch {
      // Error handled by hook
    } finally {
      setActionLoading('')
    }
  }, [jobDetail, selectedJob, mutateJobDetail, setJobDetail, loadAuditTrails, loadBoard])

  const planCurrentOperation = useCallback(async (payload) => {
    const currentOperation = getCurrentOperation(jobDetail?.operations || [])
    if (!currentOperation) return

    const updatedOperation = await authenticatedFetch(`job-operations/${currentOperation.jobOperationId}/plan`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
    toast.success(`Schedule assigned`)
    const refreshedJob = await authenticatedFetch(`jobs/${selectedJob.jobId}`)
    setJobDetail(refreshedJob)
    await loadAuditTrails(refreshedJob)
    await loadBoard()
  }, [jobDetail, selectedJob, setJobDetail, loadAuditTrails, loadBoard])

  const recalculateCurrentJob = useCallback(async () => {
    if (!selectedJob?.jobId) return
    setRecalculating(true)
    try {
      const result = await authenticatedFetch(`jobs/${selectedJob.jobId}/recalculate-cost`, { method: 'POST' })
      setCostSummary(result)
      toast.success(`Costs recalculated`)
    } catch {
      toast.error('Cost recalculation failed')
    } finally {
      setRecalculating(false)
    }
  }, [selectedJob])

  useEffect(() => {
    if (!isAuthenticated || !tenantId) {
      setLoading(false)
      return
    }

    loadBoard()
  }, [isAuthenticated, tenantId, loadBoard])

  useEffect(() => {
    if (!isAuthenticated || !tenantId || !hasPermission(normalizedUserRole, 'dashboard')) {
      setDashboardMetrics({ onTimePercentage: null })
      return
    }

    let isMounted = true
    async function loadDashboardMetrics() {
      try {
        const onTime = await authenticatedFetch('metrics/on-time-delivery')
        if (isMounted) {
          setDashboardMetrics({
            onTimePercentage: Number(onTime?.otd_percentage ?? onTime?.onTimePercentage ?? 0),
          })
        }
      } catch {
        if (isMounted) {
          setDashboardMetrics({ onTimePercentage: null })
        }
      }
    }

    loadDashboardMetrics()
    return () => {
      isMounted = false
    }
  }, [isAuthenticated, tenantId, normalizedUserRole])

  useEffect(() => {
    async function loadPlanningResources() {
      setResourceLoading(true)
      setResourceError('')
      try {
        const authContext = initialAuth?.isAuthenticated ? initialAuth : await getAuthContext().catch(() => null)
        setAuth(authContext)

        if (!authContext?.isAuthenticated || !(authContext?.tenantId || authContext?.tenant_id)) {
          setMachines([])
          setShifts([])
          return
        }

        if (!canViewMachineLoad && !canPlan) {
          setMachines([])
          setShifts([])
          return
        }

        const [machineList, shiftList] = await Promise.all([
          authenticatedFetch('master-data/machines'),
          authenticatedFetch('master-data/shifts'),
        ])
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
  }, [initialAuth, canPlan, canViewMachineLoad])

  if (!isAuthenticated) {
    return (
      <div className="rounded-[24px] border border-slate-700 bg-slate-800 p-6 text-sm text-slate-300 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
        Loading your dashboard session...
      </div>
    )
  }

  if (!tenantId || !userRole) {
    return (
      <div className="rounded-[24px] border border-orange-500/30 bg-slate-900 p-6 text-sm text-orange-300 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
        Dashboard session is incomplete. Please sign in again.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div
        role="status"
        aria-live="polite"
        className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/80 px-5 py-3 text-xs shadow-inner"
      >
        <div className="flex items-center gap-3">
          <span className={`h-2.5 w-2.5 rounded-full ${hasDashboardErrors ? 'bg-orange-500' : 'live-dot bg-green-500'}`} />
          <span className={`font-black uppercase tracking-[0.28em] ${hasDashboardErrors ? 'text-orange-400' : 'text-green-400'}`}>
            {hasDashboardErrors ? 'API Attention' : 'Live Connection'}
          </span>
          <span className="text-slate-500">
            {hasDashboardErrors ? 'Some dashboard feeds need backend attention' : 'Backend telemetry active'}
          </span>
        </div>
        <span className="machine-id max-w-full truncate text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">
          Tenant {tenantId}
        </span>
      </div>

      {isSyncing && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-3 rounded-2xl border border-slate-700 bg-slate-800/80 px-5 py-3 text-sm text-slate-300 shadow-inner backdrop-blur-sm animate-pulse-once"
        >
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-orange-400 opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-orange-500" />
          </span>
          <span className="font-semibold tracking-wide">
            Synchronizing Data
            <span className="ml-0.5 animate-pulse">...</span>
          </span>
          <span className="ml-auto text-[10px] font-black uppercase tracking-[0.3em] text-slate-500">
            Live Feed
          </span>
        </div>
      )}

      <ErrorBoundary>
        <section className="rounded-[32px] border border-slate-800 bg-slate-900 px-8 py-10 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-orange-500/5 blur-[120px] rounded-full -mr-32 -mt-32" />
          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 mb-4">
                <div className="h-1 w-8 bg-orange-500" />
                <p className="text-[10px] font-black uppercase tracking-[0.4em] text-orange-500">Global Production State</p>
              </div>
              <h1 className="text-5xl font-black tracking-tighter text-white uppercase sm:text-6xl">
                WIP Dashboard
              </h1>
              <p className="mt-6 text-sm leading-relaxed text-slate-400 font-medium">
                High-contrast operational monitoring. Track factory throughput, identify machine bottlenecks, and maintain sequence integrity.
              </p>
            </div>
            <div className="flex flex-wrap gap-4">
              {canExportJobs ? (
                <button
                  onClick={handleExport}
                  disabled={actionLoading === 'export'}
                  className="flex h-[48px] min-w-[200px] items-center justify-center rounded-2xl bg-orange-500 px-6 font-black uppercase tracking-widest text-[#0F172A] shadow-lg transition-all hover:bg-orange-400 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'export' ? 'GENERATING CSV...' : 'Export Active Jobs (CSV)'}
                </button>
              ) : null}
              <div className="flex flex-col rounded-2xl border border-slate-800 bg-slate-950 px-6 py-4 shadow-inner">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">Total Active Jobs</span>
                <span className="text-3xl font-black text-white font-mono tabular-nums mt-1">{totalWip}</span>
              </div>
              <div className="flex flex-col rounded-2xl border border-orange-900/50 bg-orange-950/20 px-6 py-4 shadow-inner">
                <span className="text-[10px] font-black uppercase tracking-widest text-orange-500/80">Delayed Jobs</span>
                <span className="text-3xl font-black text-orange-500 uppercase mt-1">{delayedJobs}</span>
              </div>
              <div className="flex flex-col rounded-2xl border border-slate-800 bg-slate-950 px-6 py-4 shadow-inner">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">On-time % This Month</span>
                <span className="text-3xl font-black text-white font-mono tabular-nums mt-1">
                  {dashboardMetrics.onTimePercentage == null ? '--' : `${dashboardMetrics.onTimePercentage.toFixed(1)}%`}
                </span>
              </div>
            </div>
          </div>
        </section>
      </ErrorBoundary>

      {canViewMachineLoad ? (
        <MachineLoadRadar />
      ) : null}

      {visibleDashboardErrors.map((message) => (
        <div key={message} className="rounded-[24px] border border-orange-500/30 bg-slate-900 p-5 text-sm text-orange-300 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          {message}
          {dashboardErrors.length > 1 ? (
            <span className="ml-2 text-xs text-slate-500">
              {dashboardErrors.length - 1} additional feed issue{dashboardErrors.length - 1 === 1 ? '' : 's'} hidden.
            </span>
          ) : null}
        </div>
      ))}

      {!loading && !boardError && columns.every((column) => asArray(column?.jobs).length === 0) ? (
        <div className="rounded-[24px] border border-dashed border-slate-700 bg-slate-800 p-6 text-sm text-slate-300 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          <p className="font-semibold text-white">No jobs are moving through the factory yet.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link to="/master-data" className="rounded-full border border-slate-700 bg-slate-800 px-4 py-2 font-semibold text-slate-300 shadow-sm">
              Add master data
            </Link>
            <Link to="/jobs" className="rounded-full bg-slate-900 px-4 py-2 font-semibold text-white">
              Create first job
            </Link>
          </div>
        </div>
      ) : null}

      <section className="overflow-x-auto pb-2">
        <ErrorBoundary fallback={<div className="p-8 text-center bg-slate-800 rounded-3xl">Kanban board is currently unavailable.</div>}>
          <div className="flex min-w-max gap-6">
            {asArray(columns).map((column) => (
              <article key={column.stageId} className="w-[340px] flex-shrink-0 rounded-[28px] border border-slate-800 bg-slate-900/60 p-6 shadow-2xl backdrop-blur-md">
                <div className="mb-6 flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <div className="h-2 w-2 bg-orange-500 rounded-sm" />
                      <p className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 font-mono">Stage</p>
                    </div>
                    <h2 className="text-2xl font-black text-white tracking-tighter uppercase leading-none">
                      {prettifyStage(column.stageName || column.stageId)}
                    </h2>
                  </div>
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-950 border border-slate-800 text-sm font-black text-orange-500 font-mono tabular-nums shadow-inner">
                    {column.counts.total}
                  </div>
                </div>

                {column.counts.delayed > 0 ? (
                  <div className="mb-6 rounded-xl bg-[#FF6B00]/15 border border-[#FF6B00]/40 px-4 py-3 text-[10px] font-black uppercase tracking-widest text-[#FF6B00] flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#FF6B00] animate-pulse" />
                    {column.counts.delayed} DELAYED
                  </div>
                ) : (
                  <div className="mb-6 rounded-xl bg-slate-950/30 border border-slate-800/50 px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-300 font-mono">
                    STABLE
                  </div>
                )}

                <div className="space-y-4">
                  {asArray(column.jobs).length > 0 ? (
                    asArray(column.jobs).map((job) => <JobCard key={job.jobId} job={job} onOpen={openJob} />)
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/20 p-8 text-center">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-300 italic">Empty</p>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        </ErrorBoundary>
      </section>

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
        downloadingPdf={downloadingPdf}
        quotedPriceInput={quotedPriceInput}
        setQuotedPriceInput={setQuotedPriceInput}
        saveQuotedPrice={saveQuotedPrice}
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
        onDownloadInvoice={downloadCurrentInvoice}
      />
    </div>
  )
}

