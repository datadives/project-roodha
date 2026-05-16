import React, { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { updateJobOperationStatus } from '../lib/jobOperationsApi'
import { fetchWorklist } from '../lib/planningApi'
import { fetchMachines, fetchWorkers } from '../lib/masterDataApi'

function formatDate(value) {
  if (!value) return 'Unplanned'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

export default function WorklistPage() {
  const [items, setItems] = useState([])
  const [machines, setMachines] = useState([])
  const [workers, setWorkers] = useState([])
  const [machineId, setMachineId] = useState('')
  const [workerId, setWorkerId] = useState('')
  const [loading, setLoading] = useState(false)
  const [savingId, setSavingId] = useState('')
  const [completionItem, setCompletionItem] = useState(null)
  const [completionForm, setCompletionForm] = useState({ quantity_completed: 0, quantity_rejected: 0 })
  const [completionError, setCompletionError] = useState('')

  async function loadWorklist(next = {}) {
    setLoading(true)
    try {
      const response = await fetchWorklist({
        machine_id: (next.machineId ?? machineId) || undefined,
        worker_id: (next.workerId ?? workerId) || undefined,
      })
      setItems(response?.items || [])
    } catch {
      setItems([])
      toast.error('Unable to load work list.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    Promise.allSettled([fetchMachines(), fetchWorkers(true)]).then(([machineResult, workerResult]) => {
      setMachines(machineResult.status === 'fulfilled' ? machineResult.value : [])
      setWorkers(workerResult.status === 'fulfilled' ? workerResult.value : [])
    })
    loadWorklist()
  }, [])

  async function startOperation(item) {
    setSavingId(item.job_operation_id)
    try {
      await updateJobOperationStatus(item.job_operation_id, {
        status: 'IN_PROGRESS',
      })
      setItems((current) => current.map((workItem) => (
        workItem.job_operation_id === item.job_operation_id
          ? { ...workItem, status: 'IN_PROGRESS' }
          : workItem
      )))
      toast.success(`${item.job_number} in progress`)
    } catch {
      toast.error('Status update blocked. Check sequence and quantity.')
    } finally {
      setSavingId('')
    }
  }

  function openCompletionModal(item) {
    setCompletionItem(item)
    setCompletionForm({
      quantity_completed: Number(item.quantity || 0),
      quantity_rejected: 0,
    })
    setCompletionError('')
  }

  function closeCompletionModal() {
    setCompletionItem(null)
    setCompletionForm({ quantity_completed: 0, quantity_rejected: 0 })
    setCompletionError('')
  }

  async function submitCompletion(event) {
    event.preventDefault()
    if (!completionItem) return

    const completed = Number(completionForm.quantity_completed)
    const rejected = Number(completionForm.quantity_rejected)
    const totalQuantity = Number(completionItem.quantity || 0)
    if (!Number.isFinite(completed) || !Number.isFinite(rejected) || completed < 0 || rejected < 0) {
      setCompletionError('Quantities must be non-negative numbers.')
      return
    }
    if (completed + rejected > totalQuantity) {
      setCompletionError('Completed plus rejected quantity cannot exceed job quantity.')
      return
    }

    setSavingId(completionItem.job_operation_id)
    try {
      await updateJobOperationStatus(completionItem.job_operation_id, {
        status: 'COMPLETED',
        quantity_completed: completed,
        quantity_rejected: rejected,
      })
      setItems((current) => current.filter((item) => item.job_operation_id !== completionItem.job_operation_id))
      toast.success(`${completionItem.job_number} completed`)
      closeCompletionModal()
    } catch {
      toast.error('Status update blocked. Check sequence and quantity.')
    } finally {
      setSavingId('')
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-slate-800 bg-slate-900 p-6">
        <p className="text-[10px] font-black uppercase tracking-[0.28em] text-orange-400">Work To Do</p>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-black text-white">Shopfloor Queue</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">See assigned operations and update progress from one screen.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-[180px_180px_auto]">
            <select className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" value={machineId} onChange={(event) => { setMachineId(event.target.value); setWorkerId(''); loadWorklist({ machineId: event.target.value, workerId: '' }) }}>
              <option value="">All machines</option>
              {machines.map((machine) => <option key={machine.machine_id} value={machine.machine_id}>{machine.name}</option>)}
            </select>
            <select className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" value={workerId} onChange={(event) => { setWorkerId(event.target.value); setMachineId(''); loadWorklist({ workerId: event.target.value, machineId: '' }) }}>
              <option value="">All workers</option>
              {workers.map((worker) => <option key={worker.worker_id} value={worker.worker_id}>{worker.name}</option>)}
            </select>
            <button type="button" onClick={() => loadWorklist()} disabled={loading} className="rounded-xl bg-orange-500 px-5 py-3 text-sm font-black uppercase tracking-wider text-slate-950 disabled:opacity-60">
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-4">
        {items.map((item) => (
          <article key={item.job_operation_id} className="rounded-[24px] border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <p className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-500">{item.customer_name || 'Factory work'}</p>
                <h2 className="mt-1 truncate text-xl font-black text-white font-mono">{item.job_number}</h2>
                <p className="mt-2 text-sm text-slate-400">{item.operation_name} | {item.part_number} | Qty {item.quantity}</p>
                <p className="mt-1 text-xs text-slate-500">Previous: {item.previous_operation_status} | Planned: {formatDate(item.planned_start_date)}</p>
                <span className="mt-3 inline-flex rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-slate-300">
                  {item.status}
                </span>
                {Array.isArray(item.tags) && item.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.tags.map((tag) => (
                      <span key={`${item.job_operation_id}-${tag}`} className="rounded-full border border-orange-500/30 bg-orange-500/10 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-orange-300">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-3">
                <button type="button" disabled={savingId === item.job_operation_id || item.status === 'IN_PROGRESS'} onClick={() => startOperation(item)} className="rounded-xl border border-orange-500/40 bg-orange-500/10 px-4 py-3 text-xs font-black uppercase tracking-wider text-orange-300 disabled:opacity-50">Start</button>
                <button type="button" disabled={savingId === item.job_operation_id} onClick={() => openCompletionModal(item)} className="rounded-xl bg-orange-500 px-4 py-3 text-xs font-black uppercase tracking-wider text-slate-950 disabled:opacity-50">Complete</button>
              </div>
            </div>
          </article>
        ))}
        {!loading && items.length === 0 && (
          <div className="rounded-[24px] border border-slate-800 bg-slate-900/70 p-8 text-center">
            <p className="text-lg font-black text-white">All caught up</p>
            <p className="mt-2 text-sm text-slate-500">No active work is queued for this filter.</p>
          </div>
        )}
      </div>

      {completionItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4">
          <form onSubmit={submitCompletion} className="w-full max-w-lg rounded-[28px] border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-orange-400">Complete Operation</p>
            <h2 className="mt-3 text-2xl font-black text-white">{completionItem.job_number}</h2>
            <p className="mt-2 text-sm text-slate-400">{completionItem.operation_name} | Qty {completionItem.quantity}</p>

            {completionError ? (
              <div className="mt-4 rounded-xl border border-orange-500/30 bg-orange-500/10 px-4 py-3 text-sm text-orange-200">
                {completionError}
              </div>
            ) : null}

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Quantity Completed
                <input
                  className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white"
                  min="0"
                  required
                  type="number"
                  value={completionForm.quantity_completed}
                  onChange={(event) => setCompletionForm((current) => ({ ...current, quantity_completed: event.target.value }))}
                />
              </label>
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Quantity Rejected
                <input
                  className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white"
                  min="0"
                  required
                  type="number"
                  value={completionForm.quantity_rejected}
                  onChange={(event) => setCompletionForm((current) => ({ ...current, quantity_rejected: event.target.value }))}
                />
              </label>
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button type="button" onClick={closeCompletionModal} className="rounded-xl border border-slate-700 px-4 py-3 text-xs font-black uppercase tracking-wider text-slate-300">
                Cancel
              </button>
              <button type="submit" disabled={savingId === completionItem.job_operation_id} className="rounded-xl bg-orange-500 px-4 py-3 text-xs font-black uppercase tracking-wider text-slate-950 disabled:opacity-50">
                {savingId === completionItem.job_operation_id ? 'Saving...' : 'Confirm Complete'}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  )
}
