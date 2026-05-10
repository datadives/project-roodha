"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: costing_service.py
 * 
 * 1) Purpose: Business logic and service layer for costing_service.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
costing_service.py
------------------
Asynchronous service for financial modeling and job costing.
Calculates Machine, Labour, and Material costs.
"""

import logging
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app import models

logger = logging.getLogger("jobwork-backend")

async def calculate_job_costs(db: AsyncSession, tenant_id: str, job_id: UUID):
    """
    Recalculates total production costs for a specific job.
    Triggered in the background when an operation is COMPLETED.
    """
    try:
        # 1. Fetch Job with Part details (for material cost)
        job_query = select(models.Job).options(
            selectinload(models.Job.part)
        ).where(
            models.Job.job_id == job_id,
            models.Job.tenant_id == tenant_id
        )
        job_result = await db.execute(job_query)
        job = job_result.scalar_one_or_none()
        
        if not job:
            logger.error(f"Costing failed: Job {job_id} not found.")
            return

        # 2. Fetch all COMPLETED operations with Machines and Workers
        ops_query = select(
            models.JobOperation,
            models.Machine.hourly_rate.label("machine_rate"),
            models.Worker.hourly_rate.label("worker_rate")
        ).join(
            models.Machine, models.JobOperation.machine_id == models.Machine.machine_id, isouter=True
        ).join(
            models.Worker, models.JobOperation.worker_id == models.Worker.worker_id, isouter=True
        ).where(
            models.JobOperation.job_id == job_id,
            models.JobOperation.status == models.OperationStatus.COMPLETED
        )
        
        ops_result = await db.execute(ops_query)
        completed_ops = ops_result.all()

        total_machine_cost = Decimal("0.00")
        total_labour_cost = Decimal("0.00")

        # 3. Calculate Operational Costs
        for row in completed_ops:
            op, machine_rate, worker_rate = row
            
            # Machine rate fallback
            m_rate = machine_rate if machine_rate is not None else Decimal("0.00")
            # Worker rate fallback (Fallback logic as requested)
            w_rate = worker_rate if worker_rate is not None else Decimal("0.00")

            if op.actual_start_time and op.actual_end_time:
                duration = op.actual_end_time - op.actual_start_time
                duration_hours = Decimal(str(duration.total_seconds() / 3600.0))
                
                total_machine_cost += duration_hours * m_rate
                total_labour_cost += duration_hours * w_rate

        # 4. Calculate Material Cost
        material_rate = Decimal("0.00")
        if job.part and job.part.default_material_cost_per_unit:
            material_rate = job.part.default_material_cost_per_unit
        
        total_material_cost = Decimal(str(job.quantity)) * material_rate

        # 5. Upsert Cost Summary
        summary_query = select(models.JobCostSummary).where(
            models.JobCostSummary.job_id == job_id,
            models.JobCostSummary.tenant_id == tenant_id
        )
        summary_result = await db.execute(summary_query)
        summary = summary_result.scalar_one_or_none()

        if not summary:
            summary = models.JobCostSummary(
                tenant_id=tenant_id,
                job_id=job_id
            )
            db.add(summary)

        summary.machine_cost = total_machine_cost
        summary.labour_cost = total_labour_cost
        summary.material_cost = total_material_cost
        summary.total_cost = total_machine_cost + total_labour_cost + total_material_cost
        summary.last_calculated_at = datetime.utcnow()

        await db.commit()
        logger.info(f"Costing updated for Job {job_id}: Total {summary.total_cost}")

    except Exception as e:
        logger.exception(f"Critical error during costing for Job {job_id}")
        await db.rollback()
