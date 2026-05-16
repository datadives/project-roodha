import React, { useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { applyAutoSchedule, previewAutoSchedule } from '../lib/planningApi'

function today(offset = 0) {
  const value = new Date()
  value.setDate(value.getDate() + offset)
  return value.toISOString().slice(0, 10)
}

function formatDateTime(value) {
  if (!value) return 'Manual'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

function toDateTimeLocal(value) {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

function fromDateTimeLocal(value) {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toISOString()
}

export default function PlanningPage() {
  const [fromDate, setFromDate] = useState(today())
  const [toDate, setToDate] = useState(today(7))
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [selected, setSelected] = useState({})

  const selectedSuggestions = useMemo(
    () => suggestions.filter((item) => selected[item.job_operation_id] && item.machine_id),
    [suggestions, selected],
  )
  const machineBackedSuggestions = useMemo(
    () => suggestions.filter((item) => item.machine_id),
    [suggestions],
  )
  const allMachineBackedSelected = machineBackedSuggestions.length > 0
    && selectedSuggestions.length === machineBackedSuggestions.length

  async function runPreview() {
    setLoading(true)
    try {
      const response = await previewAutoSchedule({ from_date: fromDate, to_date: toDate, limit: 75 })
      const nextSuggestions = response?.suggestions || []
      setSuggestions(nextSuggestions)
      setSelected(Object.fromEntries(nextSuggestions.map((item) => [item.job_operation_id, Boolean(item.machine_id)])))
      toast.success('Auto-plan preview ready')
    } catch {
      toast.error('Unable to preview plan right now.')
    } finally {
      setLoading(false)
    }
  }

  async function applySelected() {
    setApplying(true)
    try {
      const payload = selectedSuggestions.map((item) => ({
        job_operation_id: item.job_operation_id,
        machine_id: item.machine_id,
        planned_start_date: item.planned_start_date,
        planned_end_date: item.planned_end_date,
      }))
      const response = await applyAutoSchedule(payload)
      toast.success(`Applied ${response?.applied_count || payload.length} planned operations`)
      setSuggestions([])
      setSelected({})
    } catch {
      toast.error('Unable to apply selected plan.')
    } finally {
      setApplying(false)
    }
  }

  function updateSuggestionDate(jobOperationId, field, value) {
    setSuggestions((current) => current.map((item) => (
      item.job_operation_id === jobOperationId
        ? { ...item, [field]: fromDateTimeLocal(value) }
        : item
    )))
  }

  function updateSuggestionMachine(jobOperationId, value) {
    setSuggestions((current) => current.map((item) => (
      item.job_operation_id === jobOperationId
        ? { ...item, machine_id: value.trim() }
        : item
    )))
  }

  function cancelPreview() {
    setSuggestions([])
    setSelected({})
    toast('Preview cancelled')
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-slate-800 bg-slate-900 p-6 shadow-xl">
        <p className="text-[10px] font-black uppercase tracking-[0.28em] text-orange-400">V1.5 Planning</p>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-black text-white">Auto Plan</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Preview machine assignments, then apply only the rows you trust.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-[150px_150px_auto]">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
              From
              <input className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
            </label>
            <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
              To
              <input className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
            </label>
            <button type="button" onClick={runPreview} disabled={loading} className="rounded-xl bg-orange-500 px-5 py-3 text-sm font-black uppercase tracking-wider text-slate-950 disabled:opacity-60">
              {loading ? 'Planning...' : 'Auto Plan'}
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-[28px] border border-slate-800 bg-slate-900/70 p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-black text-white">Preview Table</h2>
            <p className="mt-1 text-sm text-slate-500">{suggestions.length} operations evaluated</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            {suggestions.length > 0 && (
              <button type="button" onClick={cancelPreview} className="rounded-xl border border-slate-700 px-4 py-3 text-xs font-black uppercase tracking-wider text-slate-300 hover:bg-slate-800">
                Cancel
              </button>
            )}
            <button type="button" onClick={applySelected} disabled={applying || selectedSuggestions.length === 0} className="rounded-xl border border-orange-500/40 bg-orange-500/10 px-4 py-3 text-xs font-black uppercase tracking-wider text-orange-300 disabled:opacity-50">
              {applying ? 'Applying...' : allMachineBackedSelected ? 'Accept All' : `Accept Selected (${selectedSuggestions.length})`}
            </button>
          </div>
        </div>

        {suggestions.length > 0 ? (
        <div className="overflow-x-auto" data-testid="auto-plan-preview-table">
          <table className="min-w-full text-left text-sm">
            <thead className="text-[10px] uppercase tracking-widest text-slate-500">
              <tr>
                <th className="p-3">Accept per job</th>
                <th className="p-3">Job</th>
                <th className="p-3">Operation</th>
                <th className="p-3">Machine</th>
                <th className="p-3">Start</th>
                <th className="p-3">End</th>
                <th className="p-3">Hours</th>
                <th className="p-3">Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {suggestions.map((item) => (
                <tr key={item.job_operation_id} className="text-slate-300">
                  <td className="p-3">
                    <input
                      type="checkbox"
                      checked={Boolean(selected[item.job_operation_id])}
                      disabled={!item.machine_id}
                      onChange={(event) => setSelected((current) => ({ ...current, [item.job_operation_id]: event.target.checked }))}
                      className="h-5 w-5 rounded border-slate-600 bg-slate-950 text-orange-500"
                    />
                  </td>
                  <td className="p-3 font-mono font-bold text-white">{item.job_number}</td>
                  <td className="p-3">{item.operation_name}</td>
                  <td className="p-3">
                    {item.machine_id ? (
                      <div className="space-y-1">
                        <input
                          aria-label={`Machine assignment for ${item.job_number}`}
                          type="text"
                          value={item.machine_id}
                          onChange={(event) => updateSuggestionMachine(item.job_operation_id, event.target.value)}
                          className="min-w-[180px] rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-white"
                        />
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                          {item.machine_name || 'Assigned machine'}
                        </div>
                      </div>
                    ) : (
                      item.conflict_reason || 'Manual plan needed'
                    )}
                  </td>
                  <td className="p-3">
                    {item.machine_id ? (
                      <input
                        aria-label={`Planned start for ${item.job_number}`}
                        type="datetime-local"
                        value={toDateTimeLocal(item.planned_start_date)}
                        onChange={(event) => updateSuggestionDate(item.job_operation_id, 'planned_start_date', event.target.value)}
                        className="min-w-[180px] rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-white"
                      />
                    ) : (
                      formatDateTime(item.planned_start_date)
                    )}
                  </td>
                  <td className="p-3">
                    {item.machine_id ? (
                      <input
                        aria-label={`Planned end for ${item.job_number}`}
                        type="datetime-local"
                        value={toDateTimeLocal(item.planned_end_date)}
                        onChange={(event) => updateSuggestionDate(item.job_operation_id, 'planned_end_date', event.target.value)}
                        className="min-w-[180px] rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-white"
                      />
                    ) : (
                      formatDateTime(item.planned_end_date)
                    )}
                  </td>
                  <td className="p-3 font-mono">{Number(item.estimated_hours || 0).toFixed(2)}</td>
                  <td className="p-3">
                    <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-wider ${item.due_date_risk || item.conflict_reason ? 'bg-orange-500/15 text-orange-300' : 'bg-slate-800 text-slate-400'}`}>
                      {item.conflict_reason || (item.due_date_risk ? 'Due risk' : 'OK')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-sm text-slate-500">
            Run Auto Plan to generate a preview.
          </div>
        )}
      </section>
    </div>
  )
}
