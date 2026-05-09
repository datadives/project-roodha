/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: MachineLoadRadar.jsx
 * 
 * 1) Purpose: React component for rendering MachineLoadRadar UI elements.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { useMemo } from 'react'
import MachineLoadGauge from './MachineLoadGauge'

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function normalizeId(value) {
  return value == null ? '' : String(value)
}

function toDateKey(value) {
  if (!value) return new Date().toISOString().slice(0, 10)
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10)
  return date.toISOString().slice(0, 10)
}

function machineNameFor(machineId, machines = []) {
  const normalizedMachineId = normalizeId(machineId)
  const match = asArray(machines).find((machine) => (
    normalizeId(machine.machineId || machine.machine_id || machine.id) === normalizedMachineId
  ))
  return match?.name || match?.machineName || match?.machine_name || normalizedMachineId || 'Unassigned'
}

function operationHours(operation = {}, fallbackQuantity = 1) {
  const explicitHours =
    operation.totalHours ??
    operation.total_hours ??
    operation.estimatedHours ??
    operation.estimated_hours ??
    operation.plannedHours ??
    operation.planned_hours

  if (explicitHours != null && Number.isFinite(Number(explicitHours))) {
    return Number(explicitHours)
  }

  const minutes =
    operation.durationMins ??
    operation.duration_mins ??
    operation.standardCycleTimeMins ??
    operation.standard_cycle_time_mins ??
    operation.cycleTimeMins ??
    operation.cycle_time_mins

  if (minutes != null && Number.isFinite(Number(minutes))) {
    const quantity = Number(operation.quantity ?? fallbackQuantity ?? 1)
    return (Number(minutes) * Math.max(quantity, 1)) / 60
  }

  return 0
}

function calculateMachineLoads(machines = [], jobs = []) {
  const loadMap = new Map()

  asArray(jobs).forEach((job) => {
    const loadMachineId = job.machineId ?? job.machine_id
    const loadDate = job.date
    const loadHours = job.totalHours ?? job.total_hours

    if (loadMachineId && loadDate && loadHours != null) {
      const totalHours = Number(loadHours) || 0
      const key = `${loadMachineId}-${loadDate}`
      loadMap.set(key, {
        machineId: loadMachineId,
        machineName: job.machineName || job.machine_name || machineNameFor(loadMachineId, machines),
        date: loadDate,
        totalHours,
        isOverloaded: Boolean(job.isOverloaded ?? job.is_overloaded ?? totalHours > 10),
        isEstimated: Boolean(job.isEstimated ?? job.is_estimated),
      })
      return
    }

    asArray(job.operations).forEach((operation) => {
      const machineId = operation.machineId ?? operation.machine_id
      if (!machineId) return

      const date = toDateKey(operation.plannedStartDate ?? operation.planned_start_date ?? operation.date)
      const key = `${machineId}-${date}`
      const current = loadMap.get(key) || {
        machineId,
        machineName: machineNameFor(machineId, machines),
        date,
        totalHours: 0,
        isEstimated: true,
      }

      current.totalHours += operationHours(operation, job.quantity)
      current.isOverloaded = current.totalHours > 10
      loadMap.set(key, current)
    })
  })

  return Array.from(loadMap.values())
    .map((load) => ({
      ...load,
      totalHours: Number(load.totalHours.toFixed(2)),
      isOverloaded: Boolean(load.isOverloaded || load.totalHours > 10),
    }))
    .sort((left, right) => (
      String(left.date).localeCompare(String(right.date)) ||
      String(left.machineName).localeCompare(String(right.machineName))
    ))
}

/**
 * MachineLoadRadar is the Primary Bottleneck Indicator for v1.5.
 * It converts machine/job workload inputs into daily load cards and preserves
 * the overload pulse whenever calculated load crosses the 10 hour capacity cap.
 */
export default function MachineLoadRadar({ machines = [], jobs = [], isLoading = false }) {
  const machineLoads = useMemo(
    () => calculateMachineLoads(machines, jobs),
    [machines, jobs],
  )

  return (
    <section className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {machineLoads.map((load) => (
        <article key={`${load.machineId}-${load.date}`} className="rounded-[24px] border border-slate-800 bg-slate-900/40 p-5 shadow-lg backdrop-blur-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h3 className="machine-id text-sm font-black text-white truncate uppercase tracking-wider" data-machine-id>{load.machineName}</h3>
              <p className="text-[10px] font-bold text-slate-500 font-mono mt-0.5 uppercase">{new Date(load.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</p>
            </div>
            <div className={`h-2.5 w-2.5 rounded-full ${load.isOverloaded ? 'pulse-safety-orange shadow-[0_0_16px_#FF6B00]' : 'bg-slate-700'}`} />
          </div>

          <MachineLoadGauge
            hours={load.totalHours}
            isOverloaded={load.isOverloaded}
            isEstimated={load.isEstimated}
          />
        </article>
      ))}
      {machineLoads.length === 0 && !isLoading && (
        <div className="col-span-full rounded-[24px] border border-dashed border-slate-800 p-8 text-center bg-slate-900/20">
          <p className="text-sm font-bold text-slate-300 uppercase tracking-widest italic">No machine workload data projected for the next 7 days.</p>
        </div>
      )}
    </section>
  )
}
