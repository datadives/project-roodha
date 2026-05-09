/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: MasterDataPage.jsx
 * 
 * 1) Purpose: Top-level page component for MasterDataPage.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { startTransition, useEffect, useMemo, useState, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { DEV_TENANT_ID, getAuthContext } from '../lib/auth'
import { normalizeRole } from '../lib/roles'
import { cn } from '../lib/utils'
import {
  createCustomer,
  createMachine,
  createPart,
  createShift,
  createWorker,
  deleteCustomer,
  deletePart,
  deleteShift,
  deleteWorker,
  fetchCustomers,
  fetchMachines,
  fetchParts,
  fetchShifts,
  fetchWorkers,
  updateCustomer,
  updateMachine,
  updatePart,
  updateShift,
  updateWorker,
} from '../lib/masterDataApi'

const sectionCards = [
  { key: 'customers', label: 'Customers', tone: 'bg-slate-800 border-slate-700 text-orange-500', detail: 'Active-first registry with safe delete rules.' },
  { key: 'machines', label: 'Machines', tone: 'bg-slate-800 border-slate-700 text-slate-300', detail: 'Shop-floor assets with guarded deactivation.' },
  { key: 'parts', label: 'Parts', tone: 'bg-slate-800 border-slate-700 text-orange-300', detail: 'Part masters with required operation routes.' },
  { key: 'shifts', label: 'Shifts', tone: 'bg-slate-800 border-slate-700 text-slate-400', detail: 'Daily capacity windows for planning.' },
  { key: 'workers', label: 'Workers', tone: 'bg-slate-800 border-slate-700 text-slate-300', detail: 'Roster management for operators and leads.' },
]

const inputClass =
  'w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-200 shadow-inner outline-none transition focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 font-mono'
const labelClass = 'text-[10px] font-black uppercase tracking-[0.24em] text-slate-300'
const panelClass = 'rounded-[28px] border border-slate-700 bg-slate-800 p-6 shadow-2xl backdrop-blur-md'

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function emptyCustomerForm() {
  return { name: '', contact: '', is_active: true }
}

function emptyMachineForm() {
  return { name: '', type: '', is_active: true, hourly_rate: '' }
}

function emptyPartForm(customerId = '') {
  return { 
    part_number: '', 
    customer_id: customerId, 
    steps: [
      { id: 'step-1', label: 'Cutting' },
      { id: 'step-2', label: 'Machining' },
      { id: 'step-3', label: 'Quality Check' }
    ], 
    default_material_cost_per_unit: '' 
  }
}

function emptyShiftForm() {
  return { name: '', start_time: '08:00', end_time: '16:00' }
}

function emptyWorkerForm() {
  return { name: '', role: 'Operator', is_active: true, hourly_rate: '' }
}

function slugifyOperation(label) {
  const normalized = label
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  if (normalized === 'QC' || normalized === 'QUALITYCHECK') {
    return 'QUALITY_CHECK'
  }
  return normalized
}

function routeLabels(route = []) {
  return asArray(route).map((step, index) => step.operation || step.operation_name || step.name || step.operation_id || `Step ${index + 1}`)
}

function SectionButton({ section, activeSection, onSelect, count }) {
  const active = section.key === activeSection
  return (
    <button
      type="button"
      onClick={() => onSelect(section.key)}
      className={`rounded-[24px] border px-5 py-6 text-left transition-all ${active ? 'border-orange-500 bg-orange-600 text-white shadow-[0_0_30px_-5px_rgba(249,115,22,0.4)] translate-y-[-2px]' : 'border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700 hover:bg-slate-800/60'}`}
    >
      <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl border-2 font-black ${section.tone}`}>
        {section.label[0]}
      </div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className={`text-base font-black uppercase tracking-widest ${active ? 'text-white' : 'text-slate-200'}`}>{section.label}</h3>
          <p className={`mt-2 text-[11px] font-medium leading-relaxed ${active ? 'text-orange-100' : 'text-slate-500'}`}>{section.detail}</p>
        </div>
        <span className={`rounded-lg border px-3 py-1 text-xs font-black font-mono tabular-nums ${active ? 'border-white/20 bg-white/10 text-white' : 'border-slate-800 bg-slate-950 text-slate-500'}`}>{count}</span>
      </div>
    </button>
  )
}

function SectionHeader({ eyebrow, title, detail, action }) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <div className="flex items-center gap-2 mb-2">
          <div className="h-0.5 w-6 bg-orange-500" />
          <p className="text-[10px] font-black uppercase tracking-[0.4em] text-orange-500">{eyebrow}</p>
        </div>
        <h2 className="text-3xl font-black text-white uppercase tracking-tighter">
          {title}
        </h2>
        <p className="mt-2 max-w-2xl text-xs font-bold leading-relaxed text-slate-300 uppercase tracking-wider">{detail}</p>
      </div>
      {action}
    </div>
  )
}

function StatusChip({ active, label }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${active ? 'bg-orange-500/10 text-orange-300 border border-orange-500/30' : 'bg-slate-900 text-slate-400 border border-slate-700'}`}>
      {label}
    </span>
  )
}

function InlineToggle({ checked, onChange, label }) {
  return (
    <label className="inline-flex items-center gap-3 text-sm text-slate-600">
      <input type="checkbox" checked={checked} onChange={onChange} className="h-4 w-4 rounded border-slate-500 bg-slate-900 text-orange-500 focus:ring-orange-500" />
      {label}
    </label>
  )
}

function EmptyStatePanel({ title, detail, ctaLabel, onCta, eyebrow = 'Getting Started' }) {
  return (
    <div className="rounded-[32px] border border-orange-500/20 bg-orange-500/5 p-8 text-center shadow-xl backdrop-blur-sm relative overflow-hidden">
      <div className="absolute top-0 right-0 -mr-16 -mt-16 h-32 w-32 bg-orange-500/10 rounded-full blur-3xl" />
      <div className="flex items-center justify-center gap-2 mb-4">
        <div className="h-0.5 w-4 bg-orange-500" />
        <span className="text-[10px] font-black uppercase tracking-[0.4em] text-orange-500">{eyebrow}</span>
        <div className="h-0.5 w-4 bg-orange-500" />
      </div>
      <p className="text-2xl font-black text-white uppercase tracking-tighter">{title}</p>
      <p className="mt-4 mx-auto max-w-md text-sm font-medium leading-relaxed text-slate-400">{detail}</p>
      {ctaLabel ? (
        <button 
          type="button" 
          onClick={onCta} 
          className="mt-8 rounded-xl bg-orange-500 px-8 py-3 text-sm font-black uppercase tracking-widest text-[#0F172A] shadow-lg transition-all hover:bg-orange-400 active:scale-[0.98]"
        >
          {ctaLabel}
        </button>
      ) : null}
    </div>
  )
}

export default function MasterDataPage() {
  const [auth, setAuth] = useState(null)
  const [activeSection, setActiveSection] = useState('customers')
  const [loading, setLoading] = useState({
    customers: false,
    machines: false,
    parts: false,
    shifts: false,
    workers: false,
  })
  const [savingKey, setSavingKey] = useState('')
  const [customers, setCustomers] = useState([])
  const [customerCatalog, setCustomerCatalog] = useState([])
  const [includeInactiveCustomers, setIncludeInactiveCustomers] = useState(false)
  const [customerForm, setCustomerForm] = useState(emptyCustomerForm())
  const [editingCustomerId, setEditingCustomerId] = useState(null)
  const [machines, setMachines] = useState([])
  const [machineForm, setMachineForm] = useState(emptyMachineForm())
  const [editingMachineId, setEditingMachineId] = useState(null)
  const [parts, setParts] = useState([])
  const [partForm, setPartForm] = useState(emptyPartForm())
  const [editingPartId, setEditingPartId] = useState(null)
  const [shifts, setShifts] = useState([])
  const [shiftForm, setShiftForm] = useState(emptyShiftForm())
  const [editingShiftId, setEditingShiftId] = useState(null)
  const [workers, setWorkers] = useState([])
  const [workerForm, setWorkerForm] = useState(emptyWorkerForm())
  const [editingWorkerId, setEditingWorkerId] = useState(null)
  const normalizedRole = normalizeRole(auth?.user_role)
  const canDeleteMasterData = ['OWNER', 'ADMIN', 'SUPERVISOR'].includes(normalizedRole)
  const canSubmitCustomer = Boolean(customerForm.name.trim()) && savingKey !== 'customer'
  const canSubmitMachine = Boolean(machineForm.name.trim()) && Boolean(machineForm.type.trim()) && savingKey !== 'machine'
  const canSubmitPart =
    Boolean(partForm.part_number?.trim()) &&
    Boolean(partForm.customer_id) &&
    asArray(partForm.steps).every((step) => {
      // Safely handle strings, objects, or undefined
      if (!step) return false;
      if (typeof step === 'string') return Boolean(step.trim());
      if (typeof step === 'object') {
        // If your form uses objects like { value: 'Cutting' }
        const text = step.name || step.value || step.operation_name || '';
        return Boolean(text.trim());
      }
      return true;
    }) &&
    savingKey !== 'part'
  const canSubmitShift = Boolean(shiftForm.name.trim()) && Boolean(shiftForm.start_time) && Boolean(shiftForm.end_time) && savingKey !== 'shift'
  const canSubmitWorker = Boolean(workerForm.name.trim()) && Boolean(workerForm.role.trim()) && savingKey !== 'worker'
  const isAnyFactoryDataLoading = Object.values(loading).some(Boolean)

  const counts = useMemo(
    () => ({
      customers: asArray(customers).length,
      machines: asArray(machines).length,
      parts: asArray(parts).length,
      shifts: asArray(shifts).length,
      workers: asArray(workers).length,
    }),
    [customers, machines, parts, shifts, workers],
  )

  useEffect(() => {
    getAuthContext().then(setAuth).catch(() => setAuth(null))
  }, [])

  const loadCustomers = useCallback(async (includeInactive = includeInactiveCustomers) => {
    setLoading((current) => ({ ...current, customers: true }))
    try {
      const safeAllCustomers = asArray(await fetchCustomers(true))
      const safeVisibleCustomers = includeInactive
        ? safeAllCustomers
        : safeAllCustomers.filter((customer) => customer?.is_active !== false)
      setCustomers(safeVisibleCustomers)
      setCustomerCatalog(safeAllCustomers)
      setPartForm((current) => ({
        ...current,
        customer_id: current.customer_id || safeAllCustomers[0]?.customer_id || '',
      }))
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, customers: false }))
    }
  }, [includeInactiveCustomers])

  const loadMachines = useCallback(async () => {
    setLoading((current) => ({ ...current, machines: true }))
    try {
      setMachines(asArray(await fetchMachines()))
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, machines: false }))
    }
  }, [])

  const loadParts = useCallback(async () => {
    setLoading((current) => ({ ...current, parts: true }))
    try {
      setParts(asArray(await fetchParts()))
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, parts: false }))
    }
  }, [])

  const loadShifts = useCallback(async () => {
    setLoading((current) => ({ ...current, shifts: true }))
    try {
      setShifts(asArray(await fetchShifts()))
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, shifts: false }))
    }
  }, [])

  const loadWorkers = useCallback(async () => {
    setLoading((current) => ({ ...current, workers: true }))
    try {
      setWorkers(asArray(await fetchWorkers(true)))
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, workers: false }))
    }
  }, [])

  useEffect(() => {
    loadCustomers(includeInactiveCustomers)
  }, [includeInactiveCustomers, loadCustomers])

  useEffect(() => {
    loadMachines()
    loadParts()
    loadShifts()
    loadWorkers()
  }, [loadMachines, loadParts, loadShifts, loadWorkers])

  async function handleCustomerSubmit(event) {
    event.preventDefault()
    setSavingKey('customer')
    const customerPayload = {
      ...customerForm,
      tenant_id: auth?.tenant_id || DEV_TENANT_ID,
    }
    try {
      if (editingCustomerId) {
        await updateCustomer(editingCustomerId, customerPayload)
        toast.success('Customer updated')
      } else {
        await createCustomer(customerPayload)
        toast.success('Customer created')
      }
      await loadCustomers(includeInactiveCustomers)
      setCustomerForm(emptyCustomerForm())
      setEditingCustomerId(null)
      startTransition(() => setActiveSection('customers'))
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setSavingKey('')
    }
  }

  async function handleMachineSubmit(event) {
    event.preventDefault()
    setSavingKey('machine')
    const machinePayload = {
      ...machineForm,
      hourly_rate: machineForm.hourly_rate !== '' ? parseFloat(machineForm.hourly_rate) : null,
    }
    try {
      if (editingMachineId) {
        await updateMachine(editingMachineId, machinePayload)
        toast.success('Machine updated')
      } else {
        await createMachine(machinePayload)
        toast.success('Machine created')
      }
      await loadMachines()
      setMachineForm(emptyMachineForm())
      setEditingMachineId(null)
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setSavingKey('')
    }
  }

  async function handlePartSubmit(event) {
    event.preventDefault()
    const cleanedSteps = asArray(partForm.steps).map((step) => step.label.trim()).filter(Boolean)
    if (cleanedSteps.length === 0) {
      toast.error('Add at least one default operation step')
      return
    }

    const payload = {
      part_number: partForm.part_number,
      customer_id: partForm.customer_id,
      default_operations_route: cleanedSteps.map((label, index) => ({
        sequence: index + 1,
        operation: label,
        operation_id: slugifyOperation(label),
      })),
      ...(partForm.default_material_cost_per_unit !== '' && {
        default_material_cost_per_unit: parseFloat(partForm.default_material_cost_per_unit),
      }),
    }

    setSavingKey('part')
    try {
      if (editingPartId) {
        await updatePart(editingPartId, payload)
        toast.success('Part updated')
      } else {
        await createPart(payload)
        toast.success('Part created')
      }
      await loadParts()
      setPartForm(emptyPartForm(asArray(customerCatalog)[0]?.customer_id || ''))
      setEditingPartId(null)
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setSavingKey('')
    }
  }

  async function handleShiftSubmit(event) {
    event.preventDefault()
    setSavingKey('shift')
    try {
      if (editingShiftId) {
        await updateShift(editingShiftId, shiftForm)
        toast.success('Shift updated')
      } else {
        await createShift(shiftForm)
        toast.success('Shift created')
      }
      await loadShifts()
      setShiftForm(emptyShiftForm())
      setEditingShiftId(null)
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setSavingKey('')
    }
  }

  async function handleWorkerSubmit(event) {
    event.preventDefault()
    setSavingKey('worker')
    const workerPayload = {
      ...workerForm,
      hourly_rate: workerForm.hourly_rate !== '' ? parseFloat(workerForm.hourly_rate) : null,
    }
    try {
      if (editingWorkerId) {
        await updateWorker(editingWorkerId, workerPayload)
        toast.success('Worker updated')
      } else {
        await createWorker(workerPayload)
        toast.success('Worker added')
      }
      await loadWorkers()
      setWorkerForm(emptyWorkerForm())
      setEditingWorkerId(null)
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setSavingKey('')
    }
  }

  async function handleCustomerDelete(customer) {
    if (!window.confirm(`Delete customer "${customer.name}"?`)) return
    try {
      await deleteCustomer(customer.customer_id)
      toast.success('Customer deleted')
      await loadCustomers(includeInactiveCustomers)
    } catch {
      // Toasts are already handled by the API helper.
    }
  }

  async function handlePartDelete(part) {
    if (!window.confirm(`Delete part "${part.part_number}"?`)) return
    try {
      await deletePart(part.part_id)
      toast.success('Part deleted')
      await loadParts()
    } catch {
      // Toasts are already handled by the API helper.
    }
  }

  async function handleShiftDelete(shift) {
    if (!window.confirm(`Delete shift "${shift.name}"?`)) return
    try {
      await deleteShift(shift.shift_id)
      toast.success('Shift deleted')
      await loadShifts()
    } catch {
      // Toasts are already handled by the API helper.
    }
  }

  async function handleWorkerDelete(worker) {
    if (!window.confirm(`Delete worker "${worker.name}"?`)) return
    try {
      await deleteWorker(worker.worker_id)
      toast.success('Worker removed')
      await loadWorkers()
    } catch {
      // Toasts are already handled by the API helper.
    }
  }

  async function handleMachineActivation(machine) {
    if (machine.is_active && machine.has_active_jobs) {
      return
    }

    setSavingKey(`machine-toggle-${machine.machine_id}`)
    try {
      await updateMachine(machine.machine_id, { is_active: !machine.is_active })
      toast.success(machine.is_active ? 'Machine deactivated' : 'Machine reactivated')
      await loadMachines()
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setSavingKey('')
    }
  }

  function selectCustomer(customer) {
    setEditingCustomerId(customer.customer_id)
    setCustomerForm({
      name: customer.name,
      contact: customer.contact || '',
      is_active: customer.is_active,
    })
  }

  function selectMachine(machine) {
    setEditingMachineId(machine.machine_id)
    setMachineForm({
      name: machine.name,
      type: machine.type,
      is_active: machine.is_active,
      hourly_rate: machine.hourly_rate != null ? String(machine.hourly_rate) : '',
    })
  }

  function selectPart(part) {
    setEditingPartId(part.part_id)
    setPartForm({
      part_number: part.part_number,
      customer_id: part.customer_id,
      steps: routeLabels(part.default_operations_route).map((label, idx) => ({ id: `step-${idx}-${Date.now()}`, label })),
      default_material_cost_per_unit: part.default_material_cost_per_unit != null ? String(part.default_material_cost_per_unit) : '',
    })
  }

  function selectShift(shift) {
    setEditingShiftId(shift.shift_id)
    setShiftForm({
      name: shift.name,
      start_time: shift.start_time,
      end_time: shift.end_time,
    })
  }

  function selectWorker(worker) {
    setEditingWorkerId(worker.worker_id)
    setWorkerForm({
      name: worker.name,
      role: worker.role,
      is_active: worker.is_active,
      hourly_rate: worker.hourly_rate != null ? String(worker.hourly_rate) : '',
    })
  }

  function updatePartStep(index, value) {
    setPartForm((current) => ({
      ...current,
      steps: asArray(current.steps).map((step, stepIndex) => (stepIndex === index ? { ...step, label: value } : step)),
    }))
  }

  function addPartStep() {
    setPartForm((current) => ({ ...current, steps: [...current.steps, { id: `step-${Date.now()}-${Math.random()}`, label: '' }] }))
  }

  function removePartStep(index) {
    setPartForm((current) => ({
      ...current,
      steps: asArray(current.steps).filter((_, stepIndex) => stepIndex !== index),
    }))
  }

  const sectionContent = {
    customers: (
      <div className="grid gap-5 xl:grid-cols-[1.4fr_0.95fr]">
        <section className={panelClass}>
          <SectionHeader
            eyebrow="Default active view"
            title="Customers"
            detail="The list starts with active customers only. You can include inactive records when you need to review archived relationships or reactivate them."
            action={
              <InlineToggle
                checked={includeInactiveCustomers}
                onChange={(event) => setIncludeInactiveCustomers(event.target.checked)}
                label="Include inactive customers"
              />
            }
          />
          <div className="overflow-x-auto">
            <table className="industrial-table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Contact</th>
                  <th>Status</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {asArray(customers).map((customer) => (
                  <tr key={customer.customer_id}>
                    <td>
                      <div className="font-black text-white uppercase tracking-tight">{customer.name}</div>
                      <div className="text-[10px] text-slate-500 font-mono mt-0.5">{customer.customer_id}</div>
                    </td>
                    <td className="text-slate-300 font-medium">{customer.contact || 'No contact yet'}</td>
                    <td>
                      <StatusChip active={customer.is_active} label={customer.is_active ? 'Active' : 'Inactive'} />
                    </td>
                    <td className="text-right">
                      <div className="flex justify-end gap-2">
                        <button type="button" onClick={() => selectCustomer(customer)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                          Edit
                        </button>
                        {canDeleteMasterData ? (
                          <button type="button" onClick={() => handleCustomerDelete(customer)} className="rounded-full border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-orange-500 hover:text-orange-300">
                            Delete
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading.customers && asArray(customers).length === 0 ? (
              <div className="py-6">
                <EmptyStatePanel
                  eyebrow="Customer Registry"
                  title="No customers yet"
                  detail="Start by adding your first client so parts and jobs have a real customer to connect to."
                  ctaLabel="Register First Client"
                  onCta={() => document.getElementById('customer-form-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                />
              </div>
            ) : null}
          </div>
        </section>

        <section className={panelClass} id="customer-form-card">
          <SectionHeader
            eyebrow={editingCustomerId ? 'Edit customer' : 'New customer'}
            title={editingCustomerId ? 'Refine customer details' : 'Add a customer'}
            detail="Deleting a customer will still be blocked server-side if any jobs already reference it."
          />
          <form className="space-y-4" onSubmit={handleCustomerSubmit}>
            <div>
              <label className={labelClass}>Customer name *</label>
              <input className={inputClass} value={customerForm.name} onChange={(event) => setCustomerForm((current) => ({ ...current, name: event.target.value }))} placeholder="Apex Components" required />
            </div>
            <div>
              <label className={labelClass}>Contact</label>
              <input className={inputClass} value={customerForm.contact} onChange={(event) => setCustomerForm((current) => ({ ...current, contact: event.target.value }))} placeholder="+91 98765 43210" />
            </div>
            <InlineToggle checked={customerForm.is_active} onChange={(event) => setCustomerForm((current) => ({ ...current, is_active: event.target.checked }))} label="Customer is active" />
            <div className="flex gap-3">
              <button type="submit" disabled={!canSubmitCustomer} className="rounded-full bg-orange-500 hover:bg-orange-600 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 transition-colors">
                {savingKey === 'customer' ? 'Saving...' : editingCustomerId ? 'Update customer' : 'Create customer'}
              </button>
              <button type="button" onClick={() => { setCustomerForm(emptyCustomerForm()); setEditingCustomerId(null) }} className="rounded-full border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600">
                Reset
              </button>
            </div>
          </form>
        </section>
      </div>
    ),
    machines: (
      <div className="grid gap-5 xl:grid-cols-[1.25fr_0.95fr]">
        <section className={panelClass}>
          <SectionHeader
            eyebrow="Safety-aware controls"
            title="Machines"
            detail="The UI respects the backend guardrail: if a machine still has active job assignments, its deactivate action stays blocked."
          />
          <div className="grid gap-4 md:grid-cols-2">
            {asArray(machines).map((machine) => (
              <article key={machine.machine_id} className="rounded-[24px] border border-slate-700 bg-slate-800 p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{machine.name}</h3>
                    <p className="text-sm text-slate-300">{machine.type}</p>
                  </div>
                  <StatusChip active={machine.is_active} label={machine.is_active ? 'Active' : 'Inactive'} />
                </div>
                <p className="mt-4 text-xs uppercase tracking-[0.18em] text-slate-400">
                  {machine.has_active_jobs ? 'Active jobs assigned' : 'No active job assignments'}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button type="button" onClick={() => selectMachine(machine)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                    Edit
                  </button>
                  <button
                    type="button"
                    disabled={machine.is_active && machine.has_active_jobs}
                    onClick={() => handleMachineActivation(machine)}
                    className={`rounded-full px-3 py-1.5 text-xs font-semibold ${machine.is_active && machine.has_active_jobs ? 'cursor-not-allowed border border-slate-700 bg-slate-900 text-slate-500' : machine.is_active ? 'border border-slate-600 bg-slate-900 text-slate-300' : 'border border-orange-500/30 bg-orange-500/10 text-orange-300'}`}
                  >
                    {savingKey === `machine-toggle-${machine.machine_id}` ? 'Working...' : machine.is_active ? 'Deactivate' : 'Reactivate'}
                  </button>
                </div>
              </article>
            ))}
          </div>
          {!loading.machines && asArray(machines).length === 0 ? (
            <div className="pt-6">
              <EmptyStatePanel
                eyebrow="Asset Management"
                title="No machines registered"
                detail="Register your first machine to begin production tracking and unlock the Machine Load Radar."
                ctaLabel="Register First Machine"
                onCta={() => document.getElementById('machine-form-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              />
            </div>
          ) : null}
        </section>

        <section className={panelClass} id="machine-form-card">
          <SectionHeader
            eyebrow={editingMachineId ? 'Edit machine' : 'New machine'}
            title={editingMachineId ? 'Tune machine details' : 'Register a machine'}
            detail="Use deactivation instead of deleting live shop-floor assets so operational history stays intact."
          />
          <form className="space-y-4" onSubmit={handleMachineSubmit}>
            <div>
              <label className={labelClass}>Machine name *</label>
              <input className={inputClass} value={machineForm.name} onChange={(event) => setMachineForm((current) => ({ ...current, name: event.target.value }))} placeholder="CNC-01" required />
            </div>
            <div>
              <label className={labelClass}>Machine type *</label>
              <input className={inputClass} value={machineForm.type} onChange={(event) => setMachineForm((current) => ({ ...current, type: event.target.value }))} placeholder="Turning center" required />
            </div>
            <div>
              <label className={labelClass}>Hourly Rate (₹)</label>
              <input
                className={cn(inputClass, "tabular-nums")}
                type="number"
                min="0"
                step="0.01"
                value={machineForm.hourly_rate}
                onChange={(event) => setMachineForm((current) => ({ ...current, hourly_rate: event.target.value }))}
                placeholder="e.g. 350.00"
              />
            </div>
            <InlineToggle checked={machineForm.is_active} onChange={(event) => setMachineForm((current) => ({ ...current, is_active: event.target.checked }))} label="Machine is active" />
            <div className="flex gap-3">
              <button type="submit" disabled={!canSubmitMachine} className="rounded-full bg-orange-500 hover:bg-orange-600 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 transition-colors">
                {savingKey === 'machine' ? 'Saving...' : editingMachineId ? 'Update machine' : 'Create machine'}
              </button>
              <button type="button" onClick={() => { setMachineForm(emptyMachineForm()); setEditingMachineId(null) }} className="rounded-full border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600">
                Reset
              </button>
            </div>
          </form>
        </section>
      </div>
    ),
    parts: (
      <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
        <section className={panelClass}>
          <SectionHeader
            eyebrow="Required route definition"
            title="Parts"
            detail="Each part needs a default operations route before it can be planned into production. The route builder below mirrors that backend rule."
          />
          <div className="space-y-4">
            {asArray(parts).map((part) => (
              <article key={part.part_id} className="rounded-[24px] border border-slate-700 bg-slate-800 p-6">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{part.part_number}</h3>
                    <p className="text-sm text-slate-300">Customer: {asArray(customerCatalog).find((customer) => customer.customer_id === part.customer_id)?.name || part.customer_id}</p>
                  </div>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => selectPart(part)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                      Edit
                    </button>
                    {canDeleteMasterData ? (
                      <button type="button" onClick={() => handlePartDelete(part)} className="rounded-full border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-orange-500 hover:text-orange-300">
                        Delete
                      </button>
                    ) : null}
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {(routeLabels(part.default_operations_route)?.map((label, index) => (
                    <span key={`${part.part_id}-${label}-${index}`} className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                      {index + 1}. {label}
                    </span>
                  ))) || []}
                </div>
              </article>
            ))}
            {!loading.parts && asArray(parts).length === 0 ? (
              <EmptyStatePanel
                title="No parts defined yet"
                detail="Create a part with its default route so jobs can auto-generate the right operation steps."
                ctaLabel="Create first part"
                onCta={() => document.getElementById('part-form-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              />
            ) : null}
          </div>
        </section>

        <section className={panelClass} id="part-form-card">
          <SectionHeader
            eyebrow={editingPartId ? 'Edit part' : 'New part'}
            title={editingPartId ? 'Update routing defaults' : 'Create a routable part'}
            detail="Operation steps are captured in order and shipped to the backend as the part's default route."
          />
          <form className="space-y-4" onSubmit={handlePartSubmit}>
            <div>
              <label className={labelClass}>Part number *</label>
              <input className={inputClass} value={partForm.part_number} onChange={(event) => setPartForm((current) => ({ ...current, part_number: event.target.value }))} placeholder="PART-AX-204" required />
            </div>
            <div>
              <label className={labelClass}>Customer *</label>
              <select className={inputClass} value={partForm.customer_id} onChange={(event) => setPartForm((current) => ({ ...current, customer_id: event.target.value }))} required>
                <option value="">Select customer</option>
                {asArray(customerCatalog).map((customer) => (
                  <option key={customer.customer_id} value={customer.customer_id}>
                    {customer.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className={labelClass}>Default operations route *</label>
                <button type="button" onClick={addPartStep} className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600">
                  Add step
                </button>
              </div>
              <div className="space-y-3">
                {(asArray(partForm.steps)?.map((step, index) => (
                  <div key={step.id} className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-sm font-semibold text-white">{index + 1}</div>
                    <input className={inputClass} value={step.label} onChange={(event) => updatePartStep(index, event.target.value)} placeholder="Machining" required />
                    <button type="button" onClick={() => removePartStep(index)} disabled={partForm.steps.length === 1} className="rounded-full border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-500 disabled:cursor-not-allowed disabled:opacity-40">
                      Remove
                    </button>
                  </div>
                ))) || []}
              </div>
            </div>
            <div>
              <label className={labelClass}>Material Cost / Unit (₹)</label>
              <input
                className={inputClass}
                type="number"
                min="0"
                step="0.01"
                value={partForm.default_material_cost_per_unit}
                onChange={(event) => setPartForm((current) => ({ ...current, default_material_cost_per_unit: event.target.value }))}
                placeholder="e.g. 85.00"
              />
            </div>
            <div className="flex gap-3">
              <button type="submit" disabled={!canSubmitPart} className="rounded-full bg-orange-500 hover:bg-orange-600 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 transition-colors">
                {savingKey === 'part' ? 'Saving...' : editingPartId ? 'Update part' : 'Create part'}
              </button>
              <button type="button" onClick={() => { setPartForm(emptyPartForm(asArray(customerCatalog)[0]?.customer_id || '')); setEditingPartId(null) }} className="rounded-full border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600">
                Reset
              </button>
            </div>
          </form>
        </section>
      </div>
    ),
    shifts: (
      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.95fr]">
        <section className={panelClass}>
          <SectionHeader
            eyebrow="Capacity windows"
            title="Shifts"
            detail="Set the daily time blocks your planners can assign operations into."
          />
          <div className="overflow-x-auto">
            <table className="industrial-table">
              <thead>
                <tr>
                  <th>Shift</th>
                  <th>Start</th>
                  <th>End</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {asArray(shifts).map((shift) => (
                  <tr key={shift.shift_id}>
                    <td className="font-medium text-white">{shift.name}</td>
                    <td className="text-slate-300">{shift.start_time}</td>
                    <td className="text-slate-300">{shift.end_time}</td>
                    <td className="text-right">
                      <div className="flex justify-end gap-2">
                        <button type="button" onClick={() => selectShift(shift)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                          Edit
                        </button>
                        {canDeleteMasterData ? (
                          <button type="button" onClick={() => handleShiftDelete(shift)} className="rounded-full border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-orange-500 hover:text-orange-300">
                            Delete
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading.shifts && asArray(shifts).length === 0 ? (
              <div className="pt-6">
                <EmptyStatePanel
                  title="No shifts available yet"
                  detail="Create a shift so the planning board can place operations into real working windows."
                  ctaLabel="Add first shift"
                  onCta={() => document.getElementById('shift-form-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                />
              </div>
            ) : null}
          </div>
        </section>

        <section className={panelClass} id="shift-form-card">
          <SectionHeader
            eyebrow={editingShiftId ? 'Edit shift' : 'New shift'}
            title={editingShiftId ? 'Adjust timing window' : 'Add a shift'}
            detail="These timings feed the planning and scheduling view."
          />
          <form className="space-y-4" onSubmit={handleShiftSubmit}>
            <div>
              <label className={labelClass}>Shift name *</label>
              <input className={inputClass} value={shiftForm.name} onChange={(event) => setShiftForm((current) => ({ ...current, name: event.target.value }))} placeholder="Morning shift" required />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelClass}>Start time *</label>
                <input type="time" className={inputClass} value={shiftForm.start_time} onChange={(event) => setShiftForm((current) => ({ ...current, start_time: event.target.value }))} required />
              </div>
              <div>
                <label className={labelClass}>End time *</label>
                <input type="time" className={inputClass} value={shiftForm.end_time} onChange={(event) => setShiftForm((current) => ({ ...current, end_time: event.target.value }))} required />
              </div>
            </div>
            <div className="flex gap-3">
              <button type="submit" disabled={!canSubmitShift} className="rounded-full bg-orange-500 hover:bg-orange-600 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 transition-colors">
                {savingKey === 'shift' ? 'Saving...' : editingShiftId ? 'Update shift' : 'Create shift'}
              </button>
              <button type="button" onClick={() => { setShiftForm(emptyShiftForm()); setEditingShiftId(null) }} className="rounded-full border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600">
                Reset
              </button>
            </div>
          </form>
        </section>
      </div>
    ),
    workers: (
      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.95fr]">
        <section className={panelClass}>
          <SectionHeader
            eyebrow="Daily roster"
            title="Workers"
            detail="Keep operator, supervisor, and specialist profiles current so execution and notifications map cleanly."
          />
          <div className="grid gap-3">
            {asArray(workers).map((worker) => (
              <article key={worker.worker_id} className="flex flex-col gap-3 rounded-[24px] border border-slate-700 bg-slate-800 p-6 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-white">{worker.name}</h3>
                  <p className="text-sm text-slate-300">{worker.role}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusChip active={worker.is_active} label={worker.is_active ? 'Active' : 'Inactive'} />
                  <button type="button" onClick={() => selectWorker(worker)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                    Edit
                  </button>
                  {canDeleteMasterData ? (
                    <button type="button" onClick={() => handleWorkerDelete(worker)} className="rounded-full border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-orange-500 hover:text-orange-300">
                      Delete
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
            {!loading.workers && asArray(workers).length === 0 ? (
              <EmptyStatePanel
                title="No workers on the roster yet"
                detail="Add your first operator or supervisor so execution records and notifications can stay tied to real people."
                ctaLabel="Add first worker"
                onCta={() => document.getElementById('worker-form-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              />
            ) : null}
          </div>
        </section>

        <section className={panelClass} id="worker-form-card">
          <SectionHeader
            eyebrow={editingWorkerId ? 'Edit worker' : 'New worker'}
            title={editingWorkerId ? 'Update roster entry' : 'Add a worker'}
            detail="Simple roster records keep people searchable and available for production logging."
          />
          <form className="space-y-4" onSubmit={handleWorkerSubmit}>
            <div>
              <label className={labelClass}>Worker name *</label>
              <input className={inputClass} value={workerForm.name} onChange={(event) => setWorkerForm((current) => ({ ...current, name: event.target.value }))} placeholder="Ravi Sharma" required />
            </div>
            <div>
              <label className={labelClass}>Role *</label>
              <input className={inputClass} value={workerForm.role} onChange={(event) => setWorkerForm((current) => ({ ...current, role: event.target.value }))} placeholder="Operator" required />
            </div>
            <div>
              <label className={labelClass}>Hourly Rate (₹)</label>
              <input
                className={inputClass}
                type="number"
                min="0"
                step="0.01"
                value={workerForm.hourly_rate}
                onChange={(event) => setWorkerForm((current) => ({ ...current, hourly_rate: event.target.value }))}
                placeholder="e.g. 120.00"
              />
            </div>
            <InlineToggle checked={workerForm.is_active} onChange={(event) => setWorkerForm((current) => ({ ...current, is_active: event.target.checked }))} label="Worker is active" />
            <div className="flex gap-3">
              <button type="submit" disabled={!canSubmitWorker} className="rounded-full bg-orange-500 hover:bg-orange-600 px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 transition-colors">
                {savingKey === 'worker' ? 'Saving...' : editingWorkerId ? 'Update worker' : 'Create worker'}
              </button>
              <button type="button" onClick={() => { setWorkerForm(emptyWorkerForm()); setEditingWorkerId(null) }} className="rounded-full border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600">
                Reset
              </button>
            </div>
          </form>
        </section>
      </div>
    ),
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[32px] border border-slate-800 bg-slate-900 p-6 shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
        <div className="absolute -right-10 top-10 h-36 w-36 rounded-full bg-orange-500/10 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-24 w-48 rounded-tl-[100px] bg-slate-900/5" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500">Master Data Management</p>
            <h1 className="mt-3 text-4xl font-semibold text-white" style={{ fontFamily: 'var(--font-display)' }}>
              Shape the production backbone.
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">
              This workspace keeps your core planning records in sync with the safety logic already enforced in the backend: active-first customer views, guarded machine deactivation, and required operation routes for parts.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-full border border-slate-700 bg-slate-950 px-4 py-2 text-sm font-semibold text-slate-300">Tenant: {auth?.tenant_id || 'Loading'}</div>
            <div className="rounded-full border border-white/70 bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Role: {auth?.user_role || 'Unknown'}</div>
          </div>
        </div>
      </section>

      {!canDeleteMasterData ? (
        <section className="rounded-[24px] border border-slate-700 bg-slate-900 p-4 text-sm text-slate-300 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          Master Data is currently in view-only mode for the {normalizedRole || 'current'} role. Destructive actions like delete stay hidden.
        </section>
      ) : null}

      {isAnyFactoryDataLoading ? (
        <section className="rounded-[24px] border border-white/70 bg-white/85 p-4 text-sm text-slate-600 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          Loading factory data...
        </section>
      ) : null}

      <section className="grid gap-3 lg:grid-cols-5">
        {(asArray(sectionCards)?.map((section) => (
          <SectionButton
            key={section.key}
            section={section}
            activeSection={activeSection}
            count={counts[section.key]}
            onSelect={(key) => startTransition(() => setActiveSection(key))}
          />
        ))) || []}
      </section>

      {sectionContent[activeSection]}
    </div>
  )
}
