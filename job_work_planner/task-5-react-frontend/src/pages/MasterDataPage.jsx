import { startTransition, useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { getAuthContext } from '../lib/auth'
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
  { key: 'customers', label: 'Customers', tone: 'from-amber-200 via-orange-100 to-white', detail: 'Active-first registry with safe delete rules.' },
  { key: 'machines', label: 'Machines', tone: 'from-sky-200 via-cyan-100 to-white', detail: 'Shop-floor assets with guarded deactivation.' },
  { key: 'parts', label: 'Parts', tone: 'from-emerald-200 via-lime-100 to-white', detail: 'Part masters with required operation routes.' },
  { key: 'shifts', label: 'Shifts', tone: 'from-rose-200 via-pink-100 to-white', detail: 'Daily capacity windows for planning.' },
  { key: 'workers', label: 'Workers', tone: 'from-violet-200 via-fuchsia-100 to-white', detail: 'Roster management for operators and leads.' },
]

const inputClass =
  'w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100'
const labelClass = 'text-xs font-semibold uppercase tracking-[0.18em] text-slate-500'
const panelClass = 'rounded-[28px] border border-white/70 bg-white/85 p-5 shadow-[0_18px_50px_rgba(15,23,42,0.08)] backdrop-blur'

function emptyCustomerForm() {
  return { name: '', contact: '', is_active: true }
}

function emptyMachineForm() {
  return { name: '', type: '', is_active: true }
}

function emptyPartForm(customerId = '') {
  return { part_number: '', customer_id: customerId, steps: ['Cutting', 'Machining', 'QC'] }
}

function emptyShiftForm() {
  return { name: '', start_time: '08:00', end_time: '16:00' }
}

function emptyWorkerForm() {
  return { name: '', role: 'Operator', is_active: true }
}

function slugifyOperation(label) {
  return label
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function routeLabels(route = []) {
  return route.map((step, index) => step.operation || step.operation_name || step.name || step.operation_id || `Step ${index + 1}`)
}

function SectionButton({ section, activeSection, onSelect, count }) {
  const active = section.key === activeSection
  return (
    <button
      type="button"
      onClick={() => onSelect(section.key)}
      className={`rounded-[24px] border px-4 py-4 text-left transition ${active ? 'border-slate-900 bg-slate-900 text-white shadow-[0_16px_40px_rgba(15,23,42,0.28)]' : 'border-white/70 bg-white/70 text-slate-700 hover:border-slate-300 hover:bg-white'}`}
    >
      <div className={`mb-3 rounded-2xl bg-gradient-to-br ${section.tone} p-3`}>
        <div className="text-sm font-semibold uppercase tracking-[0.18em]">{section.label}</div>
      </div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm leading-6">{section.detail}</p>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${active ? 'bg-white/15 text-white' : 'bg-slate-100 text-slate-600'}`}>{count}</span>
      </div>
    </button>
  )
}

function SectionHeader({ eyebrow, title, detail, action }) {
  return (
    <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">{eyebrow}</p>
        <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
          {title}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{detail}</p>
      </div>
      {action}
    </div>
  )
}

function StatusChip({ active, label }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>
      {label}
    </span>
  )
}

function InlineToggle({ checked, onChange, label }) {
  return (
    <label className="inline-flex items-center gap-3 text-sm text-slate-600">
      <input type="checkbox" checked={checked} onChange={onChange} className="h-4 w-4 rounded border-slate-300 text-amber-500 focus:ring-amber-300" />
      {label}
    </label>
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

  const counts = useMemo(
    () => ({
      customers: customers.length,
      machines: machines.length,
      parts: parts.length,
      shifts: shifts.length,
      workers: workers.length,
    }),
    [customers.length, machines.length, parts.length, shifts.length, workers.length],
  )

  useEffect(() => {
    getAuthContext().then(setAuth).catch(() => setAuth(null))
  }, [])

  async function loadCustomers(includeInactive = includeInactiveCustomers) {
    setLoading((current) => ({ ...current, customers: true }))
    try {
      const [visibleCustomers, allCustomers] = await Promise.all([
        fetchCustomers(includeInactive),
        fetchCustomers(true),
      ])
      setCustomers(visibleCustomers)
      setCustomerCatalog(allCustomers)
      setPartForm((current) => ({
        ...current,
        customer_id: current.customer_id || allCustomers[0]?.customer_id || '',
      }))
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, customers: false }))
    }
  }

  async function loadMachines() {
    setLoading((current) => ({ ...current, machines: true }))
    try {
      setMachines(await fetchMachines())
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, machines: false }))
    }
  }

  async function loadParts() {
    setLoading((current) => ({ ...current, parts: true }))
    try {
      setParts(await fetchParts())
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, parts: false }))
    }
  }

  async function loadShifts() {
    setLoading((current) => ({ ...current, shifts: true }))
    try {
      setShifts(await fetchShifts())
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, shifts: false }))
    }
  }

  async function loadWorkers() {
    setLoading((current) => ({ ...current, workers: true }))
    try {
      setWorkers(await fetchWorkers(true))
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setLoading((current) => ({ ...current, workers: false }))
    }
  }

  useEffect(() => {
    loadCustomers(includeInactiveCustomers)
  }, [includeInactiveCustomers])

  useEffect(() => {
    loadMachines()
    loadParts()
    loadShifts()
    loadWorkers()
  }, [])

  async function handleCustomerSubmit(event) {
    event.preventDefault()
    setSavingKey('customer')
    try {
      if (editingCustomerId) {
        await updateCustomer(editingCustomerId, customerForm)
        toast.success('Customer updated')
      } else {
        await createCustomer(customerForm)
        toast.success('Customer created')
      }
      await loadCustomers(includeInactiveCustomers)
      setCustomerForm(emptyCustomerForm())
      setEditingCustomerId(null)
    } catch {
      // Toasts are already handled by the API helper.
    } finally {
      setSavingKey('')
    }
  }

  async function handleMachineSubmit(event) {
    event.preventDefault()
    setSavingKey('machine')
    try {
      if (editingMachineId) {
        await updateMachine(editingMachineId, machineForm)
        toast.success('Machine updated')
      } else {
        await createMachine(machineForm)
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
    const cleanedSteps = partForm.steps.map((step) => step.trim()).filter(Boolean)
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
      setPartForm(emptyPartForm(customerCatalog[0]?.customer_id || ''))
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
    try {
      if (editingWorkerId) {
        await updateWorker(editingWorkerId, workerForm)
        toast.success('Worker updated')
      } else {
        await createWorker(workerForm)
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
    })
  }

  function selectPart(part) {
    setEditingPartId(part.part_id)
    setPartForm({
      part_number: part.part_number,
      customer_id: part.customer_id,
      steps: routeLabels(part.default_operations_route),
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
    })
  }

  function updatePartStep(index, value) {
    setPartForm((current) => ({
      ...current,
      steps: current.steps.map((step, stepIndex) => (stepIndex === index ? value : step)),
    }))
  }

  function addPartStep() {
    setPartForm((current) => ({ ...current, steps: [...current.steps, ''] }))
  }

  function removePartStep(index) {
    setPartForm((current) => ({
      ...current,
      steps: current.steps.filter((_, stepIndex) => stepIndex !== index),
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
            <table className="min-w-full text-sm">
              <thead className="text-left text-slate-500">
                <tr>
                  <th className="pb-3 font-medium">Customer</th>
                  <th className="pb-3 font-medium">Contact</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {customers.map((customer) => (
                  <tr key={customer.customer_id}>
                    <td className="py-3 pr-4">
                      <div className="font-medium text-slate-800">{customer.name}</div>
                      <div className="text-xs text-slate-400">{customer.customer_id}</div>
                    </td>
                    <td className="py-3 pr-4 text-slate-600">{customer.contact || 'No contact yet'}</td>
                    <td className="py-3 pr-4">
                      <StatusChip active={customer.is_active} label={customer.is_active ? 'Active' : 'Inactive'} />
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button type="button" onClick={() => selectCustomer(customer)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                          Edit
                        </button>
                        <button type="button" onClick={() => handleCustomerDelete(customer)} className="rounded-full border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:border-rose-400">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading.customers && customers.length === 0 && <p className="py-8 text-sm text-slate-500">No customers to show.</p>}
          </div>
        </section>

        <section className={panelClass}>
          <SectionHeader
            eyebrow={editingCustomerId ? 'Edit customer' : 'New customer'}
            title={editingCustomerId ? 'Refine customer details' : 'Add a customer'}
            detail="Deleting a customer will still be blocked server-side if any jobs already reference it."
          />
          <form className="space-y-4" onSubmit={handleCustomerSubmit}>
            <div>
              <label className={labelClass}>Customer name</label>
              <input className={inputClass} value={customerForm.name} onChange={(event) => setCustomerForm((current) => ({ ...current, name: event.target.value }))} placeholder="Apex Components" required />
            </div>
            <div>
              <label className={labelClass}>Contact</label>
              <input className={inputClass} value={customerForm.contact} onChange={(event) => setCustomerForm((current) => ({ ...current, contact: event.target.value }))} placeholder="+91 98765 43210" />
            </div>
            <InlineToggle checked={customerForm.is_active} onChange={(event) => setCustomerForm((current) => ({ ...current, is_active: event.target.checked }))} label="Customer is active" />
            <div className="flex gap-3">
              <button type="submit" className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white">
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
            {machines.map((machine) => (
              <article key={machine.machine_id} className="rounded-[24px] border border-slate-100 bg-slate-50/85 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">{machine.name}</h3>
                    <p className="text-sm text-slate-500">{machine.type}</p>
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
                    className={`rounded-full px-3 py-1.5 text-xs font-semibold ${machine.is_active && machine.has_active_jobs ? 'cursor-not-allowed border border-slate-200 bg-slate-100 text-slate-400' : machine.is_active ? 'border border-amber-200 bg-amber-50 text-amber-700' : 'border border-emerald-200 bg-emerald-50 text-emerald-700'}`}
                  >
                    {savingKey === `machine-toggle-${machine.machine_id}` ? 'Working...' : machine.is_active ? 'Deactivate' : 'Reactivate'}
                  </button>
                </div>
              </article>
            ))}
          </div>
          {!loading.machines && machines.length === 0 && <p className="pt-8 text-sm text-slate-500">No machines added yet.</p>}
        </section>

        <section className={panelClass}>
          <SectionHeader
            eyebrow={editingMachineId ? 'Edit machine' : 'New machine'}
            title={editingMachineId ? 'Tune machine details' : 'Register a machine'}
            detail="Use deactivation instead of deleting live shop-floor assets so operational history stays intact."
          />
          <form className="space-y-4" onSubmit={handleMachineSubmit}>
            <div>
              <label className={labelClass}>Machine name</label>
              <input className={inputClass} value={machineForm.name} onChange={(event) => setMachineForm((current) => ({ ...current, name: event.target.value }))} placeholder="CNC-01" required />
            </div>
            <div>
              <label className={labelClass}>Machine type</label>
              <input className={inputClass} value={machineForm.type} onChange={(event) => setMachineForm((current) => ({ ...current, type: event.target.value }))} placeholder="Turning center" required />
            </div>
            <InlineToggle checked={machineForm.is_active} onChange={(event) => setMachineForm((current) => ({ ...current, is_active: event.target.checked }))} label="Machine is active" />
            <div className="flex gap-3">
              <button type="submit" className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white">
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
            {parts.map((part) => (
              <article key={part.part_id} className="rounded-[24px] border border-slate-100 bg-slate-50/80 p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">{part.part_number}</h3>
                    <p className="text-sm text-slate-500">Customer: {customerCatalog.find((customer) => customer.customer_id === part.customer_id)?.name || part.customer_id}</p>
                  </div>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => selectPart(part)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                      Edit
                    </button>
                    <button type="button" onClick={() => handlePartDelete(part)} className="rounded-full border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:border-rose-400">
                      Delete
                    </button>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {routeLabels(part.default_operations_route).map((label, index) => (
                    <span key={`${part.part_id}-${label}-${index}`} className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                      {index + 1}. {label}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className={panelClass}>
          <SectionHeader
            eyebrow={editingPartId ? 'Edit part' : 'New part'}
            title={editingPartId ? 'Update routing defaults' : 'Create a routable part'}
            detail="Operation steps are captured in order and shipped to the backend as the part's default route."
          />
          <form className="space-y-4" onSubmit={handlePartSubmit}>
            <div>
              <label className={labelClass}>Part number</label>
              <input className={inputClass} value={partForm.part_number} onChange={(event) => setPartForm((current) => ({ ...current, part_number: event.target.value }))} placeholder="PART-AX-204" required />
            </div>
            <div>
              <label className={labelClass}>Customer</label>
              <select className={inputClass} value={partForm.customer_id} onChange={(event) => setPartForm((current) => ({ ...current, customer_id: event.target.value }))} required>
                <option value="">Select customer</option>
                {customerCatalog.map((customer) => (
                  <option key={customer.customer_id} value={customer.customer_id}>
                    {customer.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className={labelClass}>Default operations route</label>
                <button type="button" onClick={addPartStep} className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600">
                  Add step
                </button>
              </div>
              <div className="space-y-3">
                {partForm.steps.map((step, index) => (
                  <div key={`step-${index}`} className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-sm font-semibold text-white">{index + 1}</div>
                    <input className={inputClass} value={step} onChange={(event) => updatePartStep(index, event.target.value)} placeholder="Machining" required />
                    <button type="button" onClick={() => removePartStep(index)} disabled={partForm.steps.length === 1} className="rounded-full border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-500 disabled:cursor-not-allowed disabled:opacity-40">
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex gap-3">
              <button type="submit" className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white">
                {savingKey === 'part' ? 'Saving...' : editingPartId ? 'Update part' : 'Create part'}
              </button>
              <button type="button" onClick={() => { setPartForm(emptyPartForm(customerCatalog[0]?.customer_id || '')); setEditingPartId(null) }} className="rounded-full border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600">
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
            <table className="min-w-full text-sm">
              <thead className="text-left text-slate-500">
                <tr>
                  <th className="pb-3 font-medium">Shift</th>
                  <th className="pb-3 font-medium">Start</th>
                  <th className="pb-3 font-medium">End</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shifts.map((shift) => (
                  <tr key={shift.shift_id}>
                    <td className="py-3 pr-4 font-medium text-slate-800">{shift.name}</td>
                    <td className="py-3 pr-4 text-slate-600">{shift.start_time}</td>
                    <td className="py-3 pr-4 text-slate-600">{shift.end_time}</td>
                    <td className="py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button type="button" onClick={() => selectShift(shift)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                          Edit
                        </button>
                        <button type="button" onClick={() => handleShiftDelete(shift)} className="rounded-full border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:border-rose-400">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className={panelClass}>
          <SectionHeader
            eyebrow={editingShiftId ? 'Edit shift' : 'New shift'}
            title={editingShiftId ? 'Adjust timing window' : 'Add a shift'}
            detail="These timings feed the planning and scheduling view."
          />
          <form className="space-y-4" onSubmit={handleShiftSubmit}>
            <div>
              <label className={labelClass}>Shift name</label>
              <input className={inputClass} value={shiftForm.name} onChange={(event) => setShiftForm((current) => ({ ...current, name: event.target.value }))} placeholder="Morning shift" required />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelClass}>Start time</label>
                <input type="time" className={inputClass} value={shiftForm.start_time} onChange={(event) => setShiftForm((current) => ({ ...current, start_time: event.target.value }))} required />
              </div>
              <div>
                <label className={labelClass}>End time</label>
                <input type="time" className={inputClass} value={shiftForm.end_time} onChange={(event) => setShiftForm((current) => ({ ...current, end_time: event.target.value }))} required />
              </div>
            </div>
            <div className="flex gap-3">
              <button type="submit" className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white">
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
            {workers.map((worker) => (
              <article key={worker.worker_id} className="flex flex-col gap-3 rounded-[24px] border border-slate-100 bg-slate-50/80 p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">{worker.name}</h3>
                  <p className="text-sm text-slate-500">{worker.role}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusChip active={worker.is_active} label={worker.is_active ? 'Active' : 'Inactive'} />
                  <button type="button" onClick={() => selectWorker(worker)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400">
                    Edit
                  </button>
                  <button type="button" onClick={() => handleWorkerDelete(worker)} className="rounded-full border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:border-rose-400">
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className={panelClass}>
          <SectionHeader
            eyebrow={editingWorkerId ? 'Edit worker' : 'New worker'}
            title={editingWorkerId ? 'Update roster entry' : 'Add a worker'}
            detail="Simple roster records keep people searchable and available for production logging."
          />
          <form className="space-y-4" onSubmit={handleWorkerSubmit}>
            <div>
              <label className={labelClass}>Worker name</label>
              <input className={inputClass} value={workerForm.name} onChange={(event) => setWorkerForm((current) => ({ ...current, name: event.target.value }))} placeholder="Ravi Sharma" required />
            </div>
            <div>
              <label className={labelClass}>Role</label>
              <input className={inputClass} value={workerForm.role} onChange={(event) => setWorkerForm((current) => ({ ...current, role: event.target.value }))} placeholder="Operator" required />
            </div>
            <InlineToggle checked={workerForm.is_active} onChange={(event) => setWorkerForm((current) => ({ ...current, is_active: event.target.checked }))} label="Worker is active" />
            <div className="flex gap-3">
              <button type="submit" className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white">
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
      <section className="relative overflow-hidden rounded-[32px] border border-white/80 bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.28),transparent_34%),radial-gradient(circle_at_85%_15%,_rgba(14,165,233,0.18),transparent_28%),linear-gradient(135deg,rgba(255,255,255,0.95),rgba(248,250,252,0.92))] p-6 shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
        <div className="absolute -right-10 top-10 h-36 w-36 rounded-full bg-amber-200/50 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-24 w-48 rounded-tl-[100px] bg-slate-900/5" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500">Master Data Management</p>
            <h1 className="mt-3 text-4xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Shape the production backbone.
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              This workspace keeps your core planning records in sync with the safety logic already enforced in the backend: active-first customer views, guarded machine deactivation, and required operation routes for parts.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-full border border-white/70 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700">Tenant: {auth?.tenant_id || 'Loading'}</div>
            <div className="rounded-full border border-white/70 bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Role: {auth?.user_role || 'Unknown'}</div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 lg:grid-cols-5">
        {sectionCards.map((section) => (
          <SectionButton
            key={section.key}
            section={section}
            activeSection={activeSection}
            count={counts[section.key]}
            onSelect={(key) => startTransition(() => setActiveSection(key))}
          />
        ))}
      </section>

      {sectionContent[activeSection]}
    </div>
  )
}
