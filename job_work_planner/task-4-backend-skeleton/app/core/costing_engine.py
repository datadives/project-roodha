from __future__ import annotations

"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: costing_engine.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
costing_engine.py
-----------------
V1.0 Cost Calculation Engine for Project Roodha.

Calculates machine cost, labour cost, and material cost for a job
based on completed operations with actual timestamps and registered rates.
Performs an upsert on the JobCostSummary table.
"""

import logging
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

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


async def calculate_job_cost(job_id: uuid.UUID | str, tenant_id: str, db: AsyncSession) -> dict:
    """
    Core cost calculation function (Async).
    ... breakdown ...
    """
    # ── 1. Load the parent job ──────────────────────────────────────────────
    job_stmt = select(models.Job).where(
        models.Job.job_id == job_id, 
        models.Job.tenant_id == tenant_id
    )
    job_res = await db.execute(job_stmt)
    job = job_res.scalars().one_or_none()
    if not job:
        raise ValueError(f"Job '{job_id}' not found for tenant '{tenant_id}'")

    # ── 2. Load part for material cost ─────────────────────────────────────
    part = None
    if job:
        part_stmt = select(models.Part).where(
            models.Part.part_id == job.part_id, 
            models.Part.tenant_id == tenant_id
        )
        part_res = await db.execute(part_stmt)
        part = part_res.scalars().one_or_none()

    # ── 3. Load COMPLETED operations ────────────────────────────────────────
    ops_stmt = select(models.JobOperation).where(
        models.JobOperation.job_id == job_id,
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.status == "COMPLETED",
    )
    ops_res = await db.execute(ops_stmt)
    completed_ops = ops_res.scalars().all()

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
            m_stmt = select(models.Machine).where(
                models.Machine.machine_id == op.machine_id,
                models.Machine.tenant_id == tenant_id,
            )
            m_res = await db.execute(m_stmt)
            machine = m_res.scalars().one_or_none()
            
            if machine and machine.hourly_rate is not None:
                op_machine_cost = _round2(hours * Decimal(str(machine.hourly_rate)))
                machine_cost += op_machine_cost

        # -- Labour cost (Requirement 3.C) --
        op_labour_cost = Decimal("0.00")
        if op.worker_id:
            w_stmt = select(models.Worker).where(
                models.Worker.worker_id == op.worker_id,
                models.Worker.tenant_id == tenant_id,
            )
            w_res = await db.execute(w_stmt)
            worker = w_res.scalars().one_or_none()
            
            if worker and worker.hourly_rate is not None:
                op_labour_cost = _round2(hours * Decimal(str(worker.hourly_rate)))
                labour_cost += op_labour_cost

        operation_detail.append(
            {
                "job_op_id": op.job_op_id,
                "op_id": op.op_id,
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
    sum_stmt = select(models.JobCostSummary).where(
        models.JobCostSummary.job_id == job_id,
        models.JobCostSummary.tenant_id == tenant_id,
    )
    sum_res = await db.execute(sum_stmt)
    existing_summary = sum_res.scalars().one_or_none()

    if existing_summary:
        existing_summary.machine_cost = machine_cost
        existing_summary.labour_cost = labour_cost
        existing_summary.material_cost = material_cost
        existing_summary.total_cost = total_cost
        existing_summary.last_calculated_at = now
        logger.info("Updated JobCostSummary for job %s", job_id)
    else:
        new_summary = models.JobCostSummary(
            summary_id=uuid.uuid4(),
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

    await db.commit()

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
