/**
 * PROJECT ROODHA - USER MANAGEMENT
 * FILE: UserManagement.jsx
 * PURPOSE: OWNER-only employee invite console for Cognito-backed RBAC.
 */

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { authenticatedFetch } from '../lib/authenticatedFetch'
import { fetchMachines } from '../lib/masterDataApi'

const inputClass =
  'w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 shadow-inner outline-none transition focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 font-mono'
const labelClass = 'text-[10px] font-black uppercase tracking-[0.24em] text-slate-500'

const ROLE_OPTIONS = ['SUPERVISOR', 'OPERATOR']

export default function UserManagement() {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('SUPERVISOR')
  const [machineId, setMachineId] = useState('')
  const [machines, setMachines] = useState([])
  const [loadingMachines, setLoadingMachines] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const activeMachines = useMemo(
    () => machines.filter((machine) => machine?.isActive !== false && machine?.is_active !== false),
    [machines],
  )
  const showMachineSelect = role === 'OPERATOR'

  useEffect(() => {
    async function loadMachines() {
      setLoadingMachines(true)
      try {
        const response = await fetchMachines()
        setMachines(Array.isArray(response) ? response : [])
      } catch {
        setMachines([])
      } finally {
        setLoadingMachines(false)
      }
    }

    loadMachines()
  }, [])

  useEffect(() => {
    if (role !== 'OPERATOR') {
      setMachineId('')
    }
  }, [role])

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)

    try {
      await authenticatedFetch('users/invite', {
        method: 'POST',
        body: JSON.stringify({
          email: email.trim(),
          role,
          machine_id: role === 'OPERATOR' ? machineId || null : null,
        }),
      })
      toast.success('Employee invite sent')
      setEmail('')
      setRole('SUPERVISOR')
      setMachineId('')
    } catch (error) {
      toast.error(error?.message || 'Unable to invite employee')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[32px] border border-slate-800 bg-slate-900 px-8 py-10 shadow-2xl">
        <div className="absolute right-0 top-0 h-64 w-64 rounded-full bg-orange-500/5 blur-[120px]" />
        <div className="relative max-w-3xl">
          <div className="mb-4 flex items-center gap-2">
            <div className="h-1 w-8 bg-orange-500" />
            <p className="text-[10px] font-black uppercase tracking-[0.4em] text-orange-500">Owner Console</p>
          </div>
          <h1 className="text-5xl font-black uppercase tracking-tighter text-white sm:text-6xl">
            User Management
          </h1>
          <p className="mt-6 text-sm font-medium leading-relaxed text-slate-400">
            Invite supervisors and operators into the active tenant with Cognito-backed role attributes.
          </p>
        </div>
      </section>

      <section className="rounded-[30px] border border-slate-800 bg-slate-900/60 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Employee Invite</p>
          <h2 className="mt-2 text-3xl font-semibold text-white">Create Cognito User</h2>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className={labelClass} htmlFor="employee-email">Email Address</label>
            <input
              id="employee-email"
              className={inputClass}
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="operator@factory.com"
              required
            />
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor="employee-role">Role</label>
              <select
                id="employee-role"
                className={inputClass}
                value={role}
                onChange={(event) => setRole(event.target.value)}
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>

            {showMachineSelect ? (
              <div>
                <label className={labelClass} htmlFor="assigned-machine">Assigned Machine</label>
                <select
                  id="assigned-machine"
                  className={inputClass}
                  value={machineId}
                  onChange={(event) => setMachineId(event.target.value)}
                  disabled={loadingMachines}
                >
                  <option value="">No machine assigned</option>
                  {activeMachines.map((machine) => {
                    const id = machine.machineId || machine.machine_id
                    return (
                      <option key={id} value={id}>
                        {machine.name || machine.machineName || machine.machine_name || id}
                      </option>
                    )
                  })}
                </select>
              </div>
            ) : null}
          </div>

          <button
            type="submit"
            disabled={submitting || !email.trim()}
            className="h-12 w-full rounded-xl bg-orange-500 px-8 text-sm font-black uppercase tracking-widest text-slate-950 shadow-[0_4px_0_0_#9a3412] transition-all active:translate-y-[2px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Sending Invite...' : 'Invite Employee'}
          </button>
        </form>
      </section>
    </div>
  )
}
