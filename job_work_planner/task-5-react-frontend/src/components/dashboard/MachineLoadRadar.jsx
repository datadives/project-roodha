/**
 * PROJECT ROODHA - V1.5 CAPACITY RADAR
 * FILE: MachineLoadRadar.jsx
 * PURPOSE: OWNER/SUPERVISOR machine capacity visualization.
 */

import React, { useEffect, useMemo, useState } from 'react'
import { authenticatedFetch } from '../../lib/authenticatedFetch'

const SHIFT_CAPACITY = 10

function today(offset = 0) {
  const value = new Date()
  value.setDate(value.getDate() + offset)
  return value.toISOString().slice(0, 10)
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function normalizeMachineLoad(payload) {
  const machines = payload?.machines || payload?.loadData || payload?.load_data || payload
  return asArray(machines).map((machine) => {
    const bookedHours = Number(machine.bookedHours ?? machine.booked_hours ?? machine.totalHours ?? machine.total_hours ?? 0)
    return {
      machineId: machine.machineId || machine.machine_id,
      machineName: machine.machineName || machine.machine_name || machine.name || 'Unassigned',
      bookedHours,
      operationCount: Number(machine.operationCount ?? machine.operation_count ?? machine.operationsAssigned ?? machine.operations_assigned ?? 0),
      isOverloaded: Boolean(machine.isOverloaded ?? machine.is_overloaded ?? bookedHours > SHIFT_CAPACITY),
    }
  })
}

export default function MachineLoadRadar() {
  const [loads, setLoads] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [fromDate, setFromDate] = useState(today())
  const [toDate, setToDate] = useState(today())

  useEffect(() => {
    let isMounted = true

    async function loadMachineCapacity() {
      setIsLoading(true)
      setError('')
      try {
        const response = await authenticatedFetch('planning/machine-load', {
          params: { from_date: fromDate, to_date: toDate },
        })
        if (isMounted) {
          setLoads(normalizeMachineLoad(response))
        }
      } catch (loadError) {
        if (isMounted) {
          setLoads([])
          const transientFeedError =
            loadError?.status === 0 ||
            loadError?.isTimeout ||
            loadError?.message?.includes('Connection lost while calling') ||
            loadError?.message?.includes('Machine Link Timeout')
          setError(transientFeedError ? '' : loadError?.message || 'Unable to load machine capacity radar.')
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    loadMachineCapacity()
    return () => {
      isMounted = false
    }
  }, [fromDate, toDate])

  const peakHours = useMemo(
    () => Math.max(SHIFT_CAPACITY, ...loads.map((machine) => machine.bookedHours || 0)),
    [loads],
  )

  return (
    <section className="rounded-[32px] border border-slate-800 bg-slate-900/70 p-6 shadow-2xl">
      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-8 bg-orange-500" />
            <p className="text-[10px] font-black uppercase tracking-[0.35em] text-orange-500">Capacity Radar</p>
          </div>
          <h2 className="text-3xl font-black uppercase tracking-tight text-white">Machine Load - Today / Date Range</h2>
          <p className="mt-2 text-sm font-medium text-slate-400">
            Shift capacity threshold: <span className="font-mono text-orange-300">{SHIFT_CAPACITY}h</span>
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-[150px_150px_auto]">
          <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">
            From
            <input className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
          </label>
          <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">
            To
            <input className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          </label>
          <div className="flex items-center rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-[10px] font-black uppercase tracking-widest text-slate-500">
            {isLoading ? 'Scanning...' : `${loads.length} Machines`}
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-red-500/30 bg-red-950/20 p-4 text-sm font-semibold text-red-300">
          {error}
        </div>
      ) : null}

      {!error && !isLoading && loads.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 p-8 text-center text-sm font-bold uppercase tracking-widest text-slate-500">
          No active machine load found.
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {loads.map((machine) => {
          const percent = Math.min(100, Math.round((machine.bookedHours / peakHours) * 100))
          const overloaded = machine.bookedHours > SHIFT_CAPACITY || machine.isOverloaded

          return (
            <article
                key={machine.machineId || machine.machineName}
                className={`rounded-[24px] border p-5 shadow-inner transition ${
                  overloaded
                    ? 'animate-pulse border-red-500/60 bg-red-950/20 shadow-red-950/20'
                    : 'border-slate-800 bg-slate-950/50'
                }`}
            >
              <div className="mb-4 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-black uppercase tracking-wider text-white">
                    {machine.machineName}
                  </h3>
                  <p className="mt-1 truncate font-mono text-[10px] uppercase tracking-widest text-slate-500">
                    {machine.machineId || 'machine'}
                  </p>
                </div>
                <div className={`rounded-xl px-3 py-2 font-mono text-lg font-black ${overloaded ? 'bg-red-500 text-white' : 'bg-slate-900 text-orange-300'}`}>
                  {machine.bookedHours.toFixed(1)}h
                </div>
              </div>

              <div className="h-4 overflow-hidden rounded-sm border border-slate-800 bg-slate-950 p-0.5">
                <div
                  className={`h-full rounded-sm transition-all duration-700 ${
                    overloaded
                      ? 'bg-gradient-to-r from-orange-500 to-red-600 shadow-[0_0_18px_rgba(239,68,68,0.7)]'
                      : 'bg-gradient-to-r from-slate-600 to-orange-500'
                  }`}
                  style={{ width: `${percent}%` }}
                />
              </div>

              <div className="mt-3 flex items-center justify-between text-[10px] font-black uppercase tracking-widest">
                <span className={overloaded ? 'text-red-300' : 'text-slate-500'}>
                  {overloaded ? 'Bottleneck' : 'Stable'}
                </span>
                <span className="font-mono text-slate-500">{machine.operationCount} ops assigned</span>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
