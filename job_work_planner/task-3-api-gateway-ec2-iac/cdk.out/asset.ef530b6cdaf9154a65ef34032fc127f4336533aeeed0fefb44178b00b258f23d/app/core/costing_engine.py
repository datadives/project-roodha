"""
costing_engine.py
-----------------
V1.0 Cost Calculation Engine for Project Roodha.

Calculates machine cost, labour cost, and material cost for a job
based on completed operations with actual timestamps and registered rates.
Performs an upsert on the JobCostSummary table.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger("jobwork-backend")

_TWO_PLACES = Decimal("0.01")


def _round2(value: float | Decimal | None) -> Decimal:
    """Round a numeric value to exactly 2 decimal places using standard rounding."""
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _duration_hours(start: datetime | None, end: datetime | None) -> Decimal:
    """
    Safely compute the elapsed time in hours between two datetime objects.
    Returns 0.00 if either timestamp is missing or end < start.
    """
    if not start or not end:
        return Decimal("0.00")
    delta_seconds = (end - start).total_seconds()
    if delta_seconds <= 0:
        return Decimal("0.00")
    return Decimal(str(delta_seconds / 3600))


def calculate_job_cost(job_id: str, tenant_id: str, db: Session) -> dict:
    """
    Core cost calculation function.

    Steps:
      1. Fetch all COMPLETED JobOperations for the job.
      2. Calculate machine cost from operation durations × machine hourly_rate.
      3. Calculate labour cost from operation durations × worker hourly_rate
         (using the operator_id from the most recent ProductionEntry per operation).
      4. Calculate material cost from part.default_material_cost_per_unit × job.quantity.
      5. Sum all components; total_cost = machine + labour + material.
      6. Upsert (INSERT or UPDATE) the JobCostSummary row.

    Returns a dict with all cost breakdowns.
    """
    # ── 1. Load the parent job ──────────────────────────────────────────────
    job = (
        db.query(models.Job)
        .filter(models.Job.job_id == job_id, models.Job.tenant_id == tenant_id)
        .first()
    )
    if not job:
        raise ValueError(f"Job '{job_id}' not found for tenant '{tenant_id}'")

    # ── 2. Load part for material cost ─────────────────────────────────────
    part = (
        db.query(models.Part)
        .filter(models.Part.part_id == job.part_id, models.Part.tenant_id == tenant_id)
        .first()
    )

    # ── 3. Load COMPLETED operations ────────────────────────────────────────
    completed_ops = (
        db.query(models.JobOperation)
        .filter(
            models.JobOperation.job_id == job_id,
            models.JobOperation.tenant_id == tenant_id,
            models.JobOperation.status == "COMPLETED",
        )
        .all()
    )

    if not completed_ops:
        logger.info("No COMPLETED operations found for job %s — costs will be zero.", job_id)

    machine_cost = Decimal("0.00")
    labour_cost = Decimal("0.00")
    operation_detail: list[dict] = []

    # ── 4. Per-operation cost accumulation ──────────────────────────────────
    for op in completed_ops:
        hours = _duration_hours(op.actual_start_time, op.actual_end_time)

        # -- Machine cost --
        op_machine_cost = Decimal("0.00")
        if op.machine_id:
            machine = (
                db.query(models.Machine)
                .filter(
                    models.Machine.machine_id == op.machine_id,
                    models.Machine.tenant_id == tenant_id,
                )
                .first()
            )
            if machine and machine.hourly_rate is not None:
                op_machine_cost = _round2(hours * Decimal(str(machine.hourly_rate)))
                machine_cost += op_machine_cost

        # -- Labour cost --
        # Find the most recent ProductionEntry for this operation to get the operator.
        op_labour_cost = Decimal("0.00")
        latest_entry = (
            db.query(models.ProductionEntry)
            .filter(
                models.ProductionEntry.job_operation_id == op.job_operation_id,
                models.ProductionEntry.tenant_id == tenant_id,
            )
            .order_by(models.ProductionEntry.timestamp.desc())
            .first()
        )
        if latest_entry and latest_entry.operator_id:
            worker = (
                db.query(models.Worker)
                .filter(
                    models.Worker.worker_id == latest_entry.operator_id,
                    models.Worker.tenant_id == tenant_id,
                )
                .first()
            )
            if worker and worker.hourly_rate is not None:
                op_labour_cost = _round2(hours * Decimal(str(worker.hourly_rate)))
                labour_cost += op_labour_cost

        operation_detail.append(
            {
                "job_operation_id": op.job_operation_id,
                "operation_id": op.operation_id,
                "duration_hours": float(_round2(hours)),
                "machine_cost": float(op_machine_cost),
                "labour_cost": float(op_labour_cost),
            }
        )

    # ── 5. Material cost ────────────────────────────────────────────────────
    material_cost = Decimal("0.00")
    if part and part.default_material_cost_per_unit is not None and job.quantity:
        material_cost = _round2(
            Decimal(str(part.default_material_cost_per_unit)) * Decimal(str(job.quantity))
        )

    # ── 6. Rollup ───────────────────────────────────────────────────────────
    machine_cost = _round2(machine_cost)
    labour_cost = _round2(labour_cost)
    total_cost = _round2(machine_cost + labour_cost + material_cost)

    now = datetime.utcnow()

    # ── 7. Upsert JobCostSummary ────────────────────────────────────────────
    existing_summary = (
        db.query(models.JobCostSummary)
        .filter(
            models.JobCostSummary.job_id == job_id,
            models.JobCostSummary.tenant_id == tenant_id,
        )
        .first()
    )

    if existing_summary:
        existing_summary.machine_cost = machine_cost
        existing_summary.labour_cost = labour_cost
        existing_summary.material_cost = material_cost
        existing_summary.total_cost = total_cost
        existing_summary.last_calculated_at = now
        logger.info("Updated JobCostSummary for job %s", job_id)
    else:
        new_summary = models.JobCostSummary(
            summary_id=f"COST-{uuid.uuid4().hex[:8].upper()}",
            tenant_id=tenant_id,
            job_id=job_id,
            machine_cost=machine_cost,
            labour_cost=labour_cost,
            material_cost=material_cost,
            total_cost=total_cost,
            last_calculated_at=now,
        )
        db.add(new_summary)
        logger.info("Inserted new JobCostSummary for job %s", job_id)

    db.commit()

    return {
        "job_id": job_id,
        "machine_cost": float(machine_cost),
        "labour_cost": float(labour_cost),
        "material_cost": float(material_cost),
        "total_cost": float(total_cost),
        "last_calculated_at": now.isoformat(),
        "operations_costed": len(completed_ops),
        "operation_detail": operation_detail,
    }
