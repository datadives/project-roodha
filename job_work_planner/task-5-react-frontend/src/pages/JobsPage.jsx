import { startTransition, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import AuditTrailPanel from '../components/AuditTrailPanel'
import { getAuthContext } from '../lib/auth'
import { createJob, fetchJobAudit } from '../lib/jobsApi'
import { fetchCustomers, fetchPartById, fetchParts } from '../lib/masterDataApi'

const inputClass =
  'w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100'
const labelClass = 'text-xs font-semibold uppercase tracking-[0.18em] text-slate-500'

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

export default function JobsPage() {
  const [auth, setAuth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [submitting, setSubmitting] = useState(false)
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
      const response = await createJob({
        customer_id: jobForm.customer_id,
        part_id: jobForm.part_id,
        quantity: Number(jobForm.quantity),
        due_date: jobForm.due_date,
        priority: jobForm.priority,
      })

      setCreatedJob(response)
      setJobAuditEntries([])
      setJobAuditOpen(false)
      toast.success(`Job ${response.job.job_number} created. Opening the dashboard...`)
      setJobForm((current) => emptyJobForm(current.customer_id, current.part_id))
      navigate('/')
    } catch {
      // Toasts are already handled by the shared API layer.
    } finally {
      setSubmitting(false)
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
      <section className="relative overflow-hidden rounded-[32px] border border-white/80 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.22),transparent_28%),radial-gradient(circle_at_80%_18%,_rgba(251,191,36,0.24),transparent_26%),linear-gradient(135deg,rgba(255,255,255,0.95),rgba(239,246,255,0.9))] p-6 shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
        <div className="absolute -left-8 top-8 h-28 w-28 rounded-full bg-sky-200/40 blur-3xl" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500">Digital Job Tracker</p>
            <h1 className="mt-3 text-4xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Supervisor intake console
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              Create a production job from customer and part master data, preview the route that will become sequential job operations, and confirm the generated identifiers immediately after submission.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-full border border-white/70 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700">Tenant: {auth?.tenant_id || 'Loading'}</div>
            <div className="rounded-full border border-white/70 bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Persona: Supervisor</div>
          </div>
        </div>
      </section>

      {loadError ? (
        <div className="rounded-[24px] border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          {loadError}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
          <div className="mb-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Job Intake Form</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
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

            <div className="rounded-[26px] border border-slate-100 bg-slate-50/90 p-5">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Default Operations Route</p>
                  <h3 className="mt-2 text-xl font-semibold text-slate-900">{selectedPart?.part_number || 'Select a part to preview routing'}</h3>
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
                        <div className="rounded-[24px] border border-sky-100 bg-white px-4 py-3 shadow-sm">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-600">Step {step.sequence}</div>
                          <div className="mt-1 text-sm font-semibold text-slate-800">{step.label}</div>
                        </div>
                        {index < routeTimeline.length - 1 && <div className="h-[2px] w-10 bg-gradient-to-r from-sky-300 to-amber-300" />}
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

            <div className="rounded-[22px] border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Planned start date defaults to today in the planning workflow, and due date defaults to seven days from today so supervisors can move faster.
            </div>

            <div className="flex flex-wrap gap-3">
              <button type="submit" disabled={!canSubmitJob} className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60">
                {submitting ? 'Creating job...' : 'Create job'}
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
                className="rounded-full border border-slate-200 px-6 py-3 text-sm font-semibold text-slate-600"
              >
                Reset form
              </button>
            </div>
          </form>
        </section>

        <section className="space-y-6">
          <article className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Submission Result</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Creation confirmation
            </h2>

            {createdJob ? (
              <div className="mt-5 space-y-5">
                <div className="rounded-[24px] bg-emerald-50 p-4 text-emerald-800">
                  <p className="text-sm font-semibold">Success. The job and sequential job operations were created.</p>
                  <p className="mt-2 text-sm">
                    Job ID: <span className="font-semibold">{createdJob.job.job_id}</span>
                  </p>
                  <p className="text-sm">
                    Job Number: <span className="font-semibold">{createdJob.job.job_number}</span>
                  </p>
                  <p className="text-sm">
                    Estimated Cost: <span className="font-semibold">{formatEstimatedCost(createdJobEstimatedCost)}</span>
                  </p>
                  <div className="mt-4">
                    <button
                      type="button"
                      onClick={toggleJobAudit}
                      className="rounded-full border border-emerald-200 bg-white/80 px-4 py-2 text-sm font-semibold text-emerald-700"
                    >
                      {jobAuditOpen ? 'Hide audit trail' : 'View audit trail'}
                    </button>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Priority</div>
                    <div className="mt-2 text-lg font-semibold text-slate-900">{createdJob.job.priority}</div>
                  </div>
                  <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Estimated cost</div>
                    <div className="mt-2 text-lg font-semibold text-slate-900">{formatEstimatedCost(createdJobEstimatedCost)}</div>
                    {createdJob.costing ? (
                      <div className="mt-1 text-xs text-slate-500">
                        {createdJob.costing.operation_count} operations x {createdJob.costing.quantity} units
                      </div>
                    ) : null}
                  </div>
                  <div className="rounded-[24px] border border-slate-100 bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Current stage</div>
                    <div className="mt-2 text-lg font-semibold text-slate-900">{createdJob.job.current_stage || 'Not planned'}</div>
                  </div>
                </div>

                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Generated job operations</p>
                    <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">{createdJob.operations.length} steps</span>
                  </div>
                  <div className="space-y-3">
                    {createdJob?.operations?.map((operation) => (
                      <div key={operation.job_operation_id} className="rounded-[22px] border border-slate-100 bg-slate-50 p-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">
                              Step {operation.sequence_number}: {operation.operation_id}
                            </p>
                            <p className="text-xs text-slate-500">{operation.job_operation_id}</p>
                          </div>
                          <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">{operation.status}</span>
                        </div>
                      </div>
                    ))}
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
              <div className="mt-5 rounded-[24px] border border-dashed border-slate-200 bg-slate-50/85 p-5">
                <p className="text-sm leading-6 text-slate-500">
                  No jobs launched yet. Create your first production job and Project Roodha will generate the route steps automatically.
                </p>
                <div className="mt-4">
                  <Link to="/master-data" className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm">
                    Need parts first? Open Master Data
                  </Link>
                </div>
              </div>
            )}
          </article>

          <article className="rounded-[30px] border border-white/70 bg-[linear-gradient(135deg,rgba(14,165,233,0.08),rgba(250,204,21,0.12))] p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Supervisor notes</p>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
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
