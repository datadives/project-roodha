/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: JobsPage.jsx
 * 
 * 1) Purpose: Top-level page component for JobsPage.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import React, { startTransition, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import AuditTrailPanel from '../components/AuditTrailPanel'
import { getAuthContext } from '../lib/auth'
import { authenticatedFetch } from '../lib/authenticatedFetch'
import { createJob, fetchJobAudit } from '../lib/jobsApi'
import { fetchCustomers, fetchPartById, fetchParts } from '../lib/masterDataApi'
import { hasPermission, normalizeRole } from '../lib/roles'

const inputClass =
  'w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 shadow-inner outline-none transition focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 font-mono'
const labelClass = 'text-[10px] font-black uppercase tracking-[0.24em] text-slate-500'

const priorityOptions = [
  { value: 'HIGH', label: 'High' },
  { value: 'MEDIUM', label: 'Medium' },
  { value: 'LOW', label: 'Low' },
]

function formatEstimatedCost(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'Pending calculation'
  }

  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value)
}

function emptyJobForm(customerId = '', partId = '') {
  const defaultDueDate = new Date()
  defaultDueDate.setDate(defaultDueDate.getDate() + 7)
  return {
    customer_id: customerId,
    part_id: partId,
    quantity: 100,
    due_date: defaultDueDate.toISOString().slice(0, 10),
    priority: 'MEDIUM',
  }
}

function routeLabels(route = []) {
  return route?.map((step, index) => ({
    key: `${step.operation_id || step.operation || step.name || 'step'}-${index}`,
    label: step.operation || step.operation_name || step.name || step.operation_id || `Step ${index + 1}`,
    sequence: step.sequence || index + 1,
  }))
}

function normalizeCreatedJobResponse(response) {
  if (response?.job) {
    return {
      ...response,
      operations: Array.isArray(response.operations) ? response.operations : [],
    }
  }

  return {
    job: response || {},
    operations: Array.isArray(response?.operations) ? response.operations : [],
    costing: response?.costing || null,
  }
}

function operationStatusClass(status) {
  const normalized = String(status || '').toUpperCase()

  if (normalized === 'DELAYED') {
    return 'border border-[#FF6B00]/50 bg-[#FF6B00]/15 text-[#FF6B00] animate-pulse'
  }
  if (normalized === 'COMPLETED') {
    return 'border border-orange-500/40 bg-orange-500/10 text-orange-300'
  }
  if (normalized === 'IN_PROGRESS') {
    return 'border border-orange-500 bg-orange-500 text-[#0F172A]'
  }
  return 'border border-slate-700 bg-slate-900 text-slate-300'
}

export default function JobsPage() {
  const [auth, setAuth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [customers, setCustomers] = useState([])
  const [parts, setParts] = useState([])
  const [selectedPart, setSelectedPart] = useState(null)
  const [createdJob, setCreatedJob] = useState(null)
  const [jobAuditEntries, setJobAuditEntries] = useState([])
  const [jobAuditOpen, setJobAuditOpen] = useState(false)
  const [jobAuditLoading, setJobAuditLoading] = useState(false)
  const [jobForm, setJobForm] = useState(emptyJobForm())
  const navigate = useNavigate()

  const filteredParts = useMemo(() => {
    if (!jobForm.customer_id) return parts
    return parts?.filter((part) => part.customer_id === jobForm.customer_id)
  }, [parts, jobForm.customer_id])

  const routeTimeline = useMemo(
    () => routeLabels(selectedPart?.default_operations_route || []),
    [selectedPart],
  )
  const createdJobEstimatedCost = createdJob?.costing?.estimated_cost ?? createdJob?.job?.estimated_cost ?? null
  const canExportJobs = hasPermission(normalizeRole(auth?.userRole || auth?.user_role || auth?.role), 'exports')

  useEffect(() => {
    getAuthContext().then(setAuth).catch(() => setAuth(null))
  }, [])

  useEffect(() => {
    async function loadDependencies() {
      setLoading(true)
      setLoadError('')
      try {
        const [customerList, partList] = await Promise.all([fetchCustomers(true), fetchParts()])
        setCustomers(customerList)
        setParts(partList)

        const initialCustomerId = customerList[0]?.customer_id || ''
        const initialPart = partList.find((part) => part.customer_id === initialCustomerId) || partList[0] || null

        setJobForm(
          emptyJobForm(
            initialCustomerId || initialPart?.customer_id || '',
            initialPart?.part_id || '',
          ),
        )
        setSelectedPart(initialPart)
        if (customerList.length === 0 || partList.length === 0) {
          setLoadError('Create at least one customer and one part in Master Data before launching new jobs.')
        }
      } catch (error) {
        setCustomers([])
        setParts([])
        setSelectedPart(null)
        setLoadError(error?.response?.data?.detail || 'Unable to load job intake dependencies right now.')
      } finally {
        setLoading(false)
      }
    }

    loadDependencies()
  }, [])

  useEffect(() => {
    async function loadSelectedPart() {
      if (!jobForm.part_id) {
        setSelectedPart(null)
        return
      }

      try {
        const part = await fetchPartById(jobForm.part_id)
        setSelectedPart(part)
      } catch {
        setSelectedPart(null)
      }
    }

    loadSelectedPart()
  }, [jobForm.part_id])

  function updateField(field, value) {
    setJobForm((current) => ({ ...current, [field]: value }))
  }

  function handleCustomerChange(customerId) {
    const nextPart = parts.find((part) => part.customer_id === customerId) || null
    startTransition(() => {
      setJobForm((current) => ({
        ...current,
        customer_id: customerId,
        part_id: nextPart?.part_id || '',
      }))
    })
    setSelectedPart(nextPart)
  }

  async function toggleJobAudit() {
    if (!createdJob?.job?.job_id) return

    if (jobAuditOpen) {
      setJobAuditOpen(false)
      return
    }

    setJobAuditOpen(true)
    setJobAuditLoading(true)

    try {
      const response = await fetchJobAudit(createdJob.job.job_id)
      setJobAuditEntries(response.audit_trail || [])
    } catch {
      setJobAuditEntries([])
    } finally {
      setJobAuditLoading(false)
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)

    try {
      const response = normalizeCreatedJobResponse(await createJob({
        customer_id: jobForm.customer_id, // UUID string
        part_id: jobForm.part_id,         // UUID string
        quantity: Number(jobForm.quantity),
        due_date: jobForm.due_date,
        priority: jobForm.priority,
      }))

      setCreatedJob(response)
      setJobAuditEntries([])
      setJobAuditOpen(false)
      toast.success(`Job ${response.job?.job_number || response.job?.jobNumber || 'created'} created. Opening the dashboard...`)
      setJobForm((current) => emptyJobForm(current.customer_id, current.part_id))
      navigate('/')
    } catch {
      // Toasts are already handled by the shared API layer.
    } finally {
      setSubmitting(false)
    }
  }

  async function handleExportJobs() {
    if (!canExportJobs) {
      toast.error('CSV exports are restricted to owners.')
      return
    }

    setExporting(true)
    try {
      const response = await authenticatedFetch('exports/jobs', { method: 'GET' })
      const downloadUrl = response?.downloadUrl || response?.download_url
      if (!downloadUrl) throw new Error('Export response did not include a download URL.')

      window.open(downloadUrl, '_blank', 'noopener,noreferrer')
      toast.success('Jobs CSV export ready')
    } catch {
      toast.error('Unable to export jobs right now.')
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return <div className="rounded-[28px] border border-white/70 bg-white/80 p-8 text-sm text-slate-600 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">Loading job intake workspace...</div>
  }

  const intakeBlocked = Boolean(loadError) || customers.length === 0 || parts.length === 0
  const canSubmitJob =
    !intakeBlocked &&
    !submitting &&
    Boolean(jobForm.customer_id) &&
    Boolean(jobForm.part_id) &&
    Number(jobForm.quantity) > 0 &&
    Boolean(jobForm.due_date) &&
    Boolean(jobForm.priority)

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-slate-800 bg-slate-900 px-8 py-10 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-orange-500/5 blur-[120px] rounded-full -mr-32 -mt-32" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 mb-4">
              <div className="h-1 w-8 bg-orange-500" />
              <p className="text-[10px] font-black uppercase tracking-[0.4em] text-orange-500">Logistics & Intake</p>
            </div>
            <h1 className="text-5xl font-black tracking-tighter text-white uppercase sm:text-6xl">
              Job Intake
            </h1>
            <p className="mt-6 text-sm leading-relaxed text-slate-400 font-medium">
              Digital job tracker. Create production jobs from customer and part master data, preview routes, and confirm generated identifiers for sequence integrity.
            </p>
          </div>
            <div className="flex flex-wrap gap-4 font-mono">
              {canExportJobs ? (
                <button
                  type="button"
                  onClick={handleExportJobs}
                  disabled={exporting}
                  className="flex min-h-[72px] min-w-[180px] flex-col justify-center rounded-2xl bg-orange-500 px-6 py-4 text-left text-slate-950 shadow-lg transition hover:bg-orange-400 disabled:cursor-wait disabled:opacity-60"
                >
                  <span className="text-[10px] font-black uppercase tracking-widest">Owner Export</span>
                  <span className="mt-1 inline-flex items-center gap-2 text-sm font-black uppercase tracking-wider">
                    {exporting ? (
                      <span className="h-3 w-3 rounded-full border-2 border-slate-950/30 border-t-slate-950 motion-safe:animate-spin" />
                    ) : null}
                    {exporting ? 'Generating...' : 'Export to CSV'}
                  </span>
                </button>
              ) : null}
              <div className="flex flex-col rounded-2xl border border-slate-800 bg-slate-950 px-6 py-4 shadow-inner">
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-600">Tenant</span>
              <span className="text-sm font-bold text-slate-200 mt-1">{auth?.tenant_id || 'ID_ERR'}</span>
            </div>
            <div className="flex flex-col rounded-2xl border border-orange-950/50 bg-orange-950/20 px-6 py-4 shadow-inner">
              <span className="text-[10px] font-black uppercase tracking-widest text-orange-500/80">Mode</span>
              <span className="text-sm font-black text-orange-500 uppercase mt-1">Supervisor</span>
            </div>
          </div>
        </div>
      </section>

      {loadError ? (
        <div className="rounded-[32px] border border-orange-500/20 bg-orange-500/5 p-10 text-center shadow-xl backdrop-blur-sm relative overflow-hidden">
          <div className="absolute top-0 right-0 -mr-16 -mt-16 h-32 w-32 bg-orange-500/10 rounded-full blur-3xl" />
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="h-0.5 w-4 bg-orange-500" />
            <span className="text-[10px] font-black uppercase tracking-[0.4em] text-orange-500">Intake Restrict</span>
            <div className="h-0.5 w-4 bg-orange-500" />
          </div>
          <p className="text-2xl font-black text-white uppercase tracking-tighter">Prerequisites Missing</p>
          <p className="mt-4 mx-auto max-w-md text-sm font-medium leading-relaxed text-slate-400">
            {loadError}
          </p>
          <div className="mt-8">
            <Link to="/master-data" className="rounded-xl bg-orange-500 px-8 py-3 text-sm font-black uppercase tracking-widest text-[#0F172A] shadow-lg transition-all hover:bg-orange-400 active:scale-[0.98]">
              Configure Master Data
            </Link>
          </div>
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-[30px] border border-slate-800 bg-slate-900/60 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
          <div className="mb-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Job Intake Form</p>
            <h2 className="mt-2 text-3xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
              Launch a new job
            </h2>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className={labelClass}>Customer *</label>
                <select
                  className={inputClass}
                  value={jobForm.customer_id}
                  onChange={(event) => handleCustomerChange(event.target.value)}
                  disabled={intakeBlocked}
                  required
                >
                  <option value="">Select customer</option>
                  {customers?.map((customer) => (
                    <option key={customer.customer_id} value={customer.customer_id}>
                      {customer.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className={labelClass}>Part *</label>
                <select
                  className={inputClass}
                  value={jobForm.part_id}
                  onChange={(event) => updateField('part_id', event.target.value)}
                  disabled={intakeBlocked}
                  required
                >
                  <option value="">Select part</option>
                  {filteredParts?.map((part) => (
                    <option key={part.part_id} value={part.part_id}>
                      {part.part_number}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <label className={labelClass}>Quantity *</label>
                <input
                  className={inputClass}
                  type="number"
                  min="1"
                  value={jobForm.quantity}
                  onChange={(event) => updateField('quantity', event.target.value)}
                  disabled={intakeBlocked}
                  required
                />
              </div>

              <div>
                <label className={labelClass}>Due date *</label>
                <input
                  className={inputClass}
                  type="date"
                  value={jobForm.due_date}
                  onChange={(event) => updateField('due_date', event.target.value)}
                  min={new Date().toISOString().slice(0, 10)}
                  disabled={intakeBlocked}
                  required
                />
              </div>

              <div>
                <label className={labelClass}>Priority *</label>
                <select
                  className={inputClass}
                  value={jobForm.priority}
                  onChange={(event) => updateField('priority', event.target.value)}
                  disabled={intakeBlocked}
                  required
                >
                  {priorityOptions?.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="rounded-[26px] border border-slate-800 bg-slate-950 p-5">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Default Operations Route</p>
                  <h3 className="mt-2 text-xl font-semibold text-white">{selectedPart?.part_number || 'Select a part to preview routing'}</h3>
                </div>
                {selectedPart && (
                  <div className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-white">
                    {routeTimeline.length} planned steps
                  </div>
                )}
              </div>

              {routeTimeline.length > 0 ? (
                <div className="mt-6 overflow-x-auto">
                  <div className="flex min-w-max items-center gap-3">
                    {routeTimeline?.map((step, index) => (
                      <div key={step.key} className="flex items-center gap-3">
                        <div className="rounded-[24px] border border-slate-700 bg-slate-900 px-4 py-3 shadow-sm">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-orange-400 font-mono">Step {step.sequence}</div>
                          <div className="mt-1 text-sm font-semibold text-white uppercase tracking-tight">{step.label}</div>
                        </div>
                        {index < routeTimeline.length - 1 && <div className="h-[2px] w-10 bg-gradient-to-r from-orange-500 to-slate-500" />}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="mt-5 text-sm leading-6 text-slate-500">
                  Choose a part to fetch its details and preview the default operations route that will generate sequential job operations.
                </p>
              )}
            </div>

            <div className="rounded-[22px] border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-400">
              Planned start date defaults to today in the planning workflow, and due date defaults to seven days from today so supervisors can move faster.
            </div>

            <div className="flex flex-wrap gap-4 pt-4">
              <button 
                type="submit" 
                disabled={!canSubmitJob} 
                className="h-12 flex-1 rounded-xl bg-orange-600 px-8 text-sm font-black uppercase tracking-widest text-white shadow-[0_4px_0_0_#9a3412] active:translate-y-[2px] active:shadow-none disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {submitting ? 'PROCESSING...' : 'INITIALIZE JOB'}
              </button>
              <button
                type="button"
                onClick={() => {
                  const fallbackPart = filteredParts[0] || parts[0] || null
                  setJobForm(emptyJobForm(jobForm.customer_id || customers[0]?.customer_id || '', fallbackPart?.part_id || ''))
                  setSelectedPart(fallbackPart)
                  setCreatedJob(null)
                }}
                disabled={intakeBlocked}
                className="h-12 rounded-xl border-2 border-slate-800 bg-slate-900 px-6 text-sm font-black uppercase tracking-widest text-slate-400 hover:border-slate-700 transition-all font-mono"
              >
                RESET
              </button>
            </div>
          </form>
        </section>

        <section className="space-y-6">
          <article className="rounded-[30px] border border-slate-800 bg-slate-900/60 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Submission Result</p>
            <h2 className="mt-2 text-3xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
              Creation confirmation
            </h2>

            {createdJob ? (
              <div className="mt-5 space-y-5">
                <div className="rounded-[24px] border border-orange-500/30 bg-slate-900 p-4 text-orange-300">
                  <p className="text-sm font-semibold">Success. The job and sequential job operations were created.</p>
                  <p className="mt-2 text-sm">
                    Job ID: <span className="font-black font-mono text-white">{createdJob.job.job_id}</span>
                  </p>
                  <p className="text-sm">
                    Job Number: <span className="font-black font-mono text-white">{createdJob.job.job_number}</span>
                  </p>
                  <p className="text-sm">
                    Estimated Cost: <span className="font-black font-mono text-white">{formatEstimatedCost(createdJobEstimatedCost)}</span>
                  </p>
                  <div className="mt-4">
                    <button
                      type="button"
                      onClick={toggleJobAudit}
                      className="rounded-full border border-orange-500/40 bg-orange-500/10 px-4 py-2 text-sm font-semibold text-orange-300"
                    >
                      {jobAuditOpen ? 'Hide audit trail' : 'View audit trail'}
                    </button>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-[24px] border border-slate-800 bg-slate-950 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Priority</div>
                    <div className="mt-2 text-lg font-semibold text-white">{createdJob.job.priority}</div>
                  </div>
                  <div className="rounded-[24px] border border-slate-800 bg-slate-950 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Estimated cost</div>
                    <div className="mt-2 text-lg font-semibold text-white font-mono">{formatEstimatedCost(createdJobEstimatedCost)}</div>
                    {createdJob.costing ? (
                      <div className="mt-1 text-xs text-slate-500 font-mono">
                        {createdJob.costing.operation_count} operations x {createdJob.costing.quantity} units
                      </div>
                    ) : null}
                  </div>
                  <div className="rounded-[24px] border border-slate-800 bg-slate-950 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Current stage</div>
                    <div className="mt-2 text-lg font-semibold text-white">{createdJob.job.current_stage || 'Not planned'}</div>
                  </div>
                </div>

                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Generated job operations</p>
                    <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white font-mono">{createdJob.operations.length} steps</span>
                  </div>
                  <div className="space-y-3">
                    {createdJob?.operations?.map((operation, index) => {
                      const operationId =
                        operation.job_operation_id ||
                        operation.job_op_id ||
                        operation.jobOperationId ||
                        `operation-${index}`
                      const operationLabel =
                        operation.operation_id ||
                        operation.op_id ||
                        operation.operationName ||
                        operation.operation_name ||
                        operation.opId ||
                        'Routing step'
                      const sequenceNumber = operation.sequence_number || operation.sequenceNumber || index + 1

                      return (
                      <div key={operationId} className="rounded-[22px] border border-slate-800 bg-slate-950 p-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="text-sm font-semibold text-white">
                              Step <span className="font-mono">{sequenceNumber}</span>: <span className="font-mono">{operationLabel}</span>
                            </p>
                            <p className="text-xs text-slate-500 font-mono">{operationId}</p>
                          </div>
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${operationStatusClass(operation.status)}`}>{operation.status}</span>
                        </div>
                      </div>
                    )})}
                  </div>
                </div>

                {jobAuditOpen ? (
                  <AuditTrailPanel
                    title="Job history"
                    entries={jobAuditEntries}
                    loading={jobAuditLoading}
                    emptyMessage="No audit entries are available for this job yet."
                  />
                ) : null}
              </div>
            ) : (
              <div className="mt-5 rounded-[24px] border border-dashed border-slate-700 bg-slate-950 p-5">
                <p className="text-sm leading-6 text-slate-500">
                  No jobs launched yet. Create your first production job and Project Roodha will generate the route steps automatically.
                </p>
                <div className="mt-4">
                  <Link to="/master-data" className="inline-flex rounded-full border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-300 shadow-sm hover:border-orange-500/40 hover:text-orange-300">
                    Need parts first? Open Master Data
                  </Link>
                </div>
              </div>
            )}
          </article>

          <article className="rounded-[30px] border border-slate-800 bg-slate-900/60 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Supervisor notes</p>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-400">
              <li>The part dropdown narrows to parts that belong to the chosen customer.</li>
              <li>Route preview is fetched from the selected part record before submission.</li>
              <li>The backend now auto-generates a unique job number when the supervisor form omits it.</li>
            </ul>
          </article>
        </section>
      </div>
    </div>
  )
}
