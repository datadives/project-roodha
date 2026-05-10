"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: metrics_service.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
# app/core/metrics_service.py

from datetime import datetime
from collections import defaultdict
from uuid import UUID
import logging
from typing import List, Dict, Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app import models

logger = logging.getLogger("jobwork-backend")
ESTIMATED_OPERATION_UNIT_COST = 12.5

# -------------------------------------------------------
# 0. Core Business KPI: On-Time Delivery (OTD)
# -------------------------------------------------------
async def get_on_time_delivery_percentage_service(db: AsyncSession, tenant_id: str) -> dict:
    """
    Requirement D: OT% Metric. 
    Calculates (On-Time Completed Jobs / Total Completed Jobs) * 100.
    """
    # 1. Fetch all completed jobs
    stmt = select(models.Job).where(
        models.Job.tenant_id == tenant_id,
        models.Job.status == models.JobStatus.COMPLETED
    )
    result = await db.execute(stmt)
    completed_jobs = result.scalars().all()
    
    if not completed_jobs:
        return {"otd_percentage": 100.0, "total_completed": 0, "on_time_count": 0}

    # 2. Key comparison: actual completion (latest operation end time) vs due_date
    on_time_count = 0
    for job in completed_jobs:
        # Get the latest operation end time for this job
        latest_op_stmt = select(func.max(models.JobOperation.actual_end_time)).where(
            models.JobOperation.job_id == job.job_id,
            models.JobOperation.tenant_id == tenant_id
        )
        res = await db.execute(latest_op_stmt)
        actual_completion_time = res.scalar()
        
        if not job.due_date:
            on_time_count += 1 # No due date = on time by default for metrics
            continue
            
        if actual_completion_time and actual_completion_time.date() <= job.due_date.date():
            on_time_count += 1
            
    percentage = round((on_time_count / len(completed_jobs)) * 100, 2)
    
    return {
        "otd_percentage": percentage,
        "total_completed": len(completed_jobs),
        "on_time_count": on_time_count,
        "late_count": len(completed_jobs) - on_time_count
    }

# -------------------------------------------------------
# 1. WIP by Stage
# -------------------------------------------------------
async def get_wip_metrics_service(db: AsyncSession, tenant_id: str, from_date: str | None = None, to_date: str | None = None) -> list:
    """
    Calculates Work-In-Progress (WIP) counts per operation stage.
    Uses AsyncSession and select() for SA 2.0.
    """
    # Fetch active operations directly from AWS
    stmt = select(models.JobOperation).where(
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.status.in_([
            models.OperationStatus.NOT_STARTED, # READY is NOT_STARTED in models.py enum
            models.OperationStatus.IN_PROGRESS
        ])
    )
    result = await db.execute(stmt)
    active_ops = result.scalars().all()

    wip_counts = defaultdict(int)

    for op in active_ops:
        # Date filtering logic
        if op.planned_start_date:
            start_iso = op.planned_start_date.date().isoformat()
            if from_date and start_iso < from_date: continue
            if to_date and start_iso > to_date: continue

        # Ensure op_id (UUID) is stringified for JSON safety in counts
        stage_key = str(op.op_id)
        wip_counts[stage_key] += 1

    return [{"stage": stage, "count": count} for stage, count in wip_counts.items()]


# -------------------------------------------------------
# 2. Bottleneck Machines
# -------------------------------------------------------
async def get_bottleneck_metrics_service(db: AsyncSession, tenant_id: str, from_date: str | None = None, to_date: str | None = None) -> list:
    """
    Identifies machines with the highest backlog of operations.
    """
    # Fetch pending operations that are assigned to a machine
    stmt = select(models.JobOperation).where(
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.machine_id.isnot(None),
        models.JobOperation.status.notin_([models.OperationStatus.COMPLETED])
    )
    result = await db.execute(stmt)
    pending_ops = result.scalars().all()

    machine_load = defaultdict(int)

    for op in pending_ops:
        if op.planned_start_date:
            start_iso = op.planned_start_date.date().isoformat()
            if from_date and start_iso < from_date: continue
            if to_date and start_iso > to_date: continue

        # machine_id is UUID
        machine_load[op.machine_id] += 1

    if not machine_load:
        return []

    # Fetch machine names
    machine_ids = list(machine_load.keys())
    machines_stmt = select(models.Machine).where(
        models.Machine.tenant_id == tenant_id,
        models.Machine.machine_id.in_(machine_ids)
    )
    machines_result = await db.execute(machines_stmt)
    machines = machines_result.scalars().all()
    
    machine_names = {m.machine_id: m.name for m in machines}

    bottlenecks = [
        {
            "machine_id": str(m_id), 
            "machine_name": machine_names.get(m_id, str(m_id)),
            "pending_operations": count
        } 
        for m_id, count in machine_load.items()
    ]
    bottlenecks.sort(key=lambda x: x["pending_operations"], reverse=True)
    
    return bottlenecks


# -------------------------------------------------------
# 3. Late Jobs
# -------------------------------------------------------
async def get_late_jobs_service(db: AsyncSession, tenant_id: str) -> dict:
    """
    Returns jobs that have passed their due date but are not completed.
    """
    today = datetime.utcnow().date()
    
    stmt = select(models.Job).where(
        models.Job.tenant_id == tenant_id,
        models.Job.status != models.JobStatus.COMPLETED,
        models.Job.due_date < datetime.utcnow() # due_date is DateTime in models
    ).order_by(models.Job.due_date.asc())
    
    result = await db.execute(stmt)
    late_jobs = result.scalars().all()

    formatted_jobs = []
    for job in late_jobs:
        formatted_jobs.append({
            "job_id": str(job.job_id),
            "job_number": job.job_number,
            "customer_id": str(job.customer_id) if job.customer_id else None,
            "due_date": job.due_date.isoformat() if job.due_date else None,
            "priority": job.priority,
            "status": job.status
        })

    return {
        "total_late": len(formatted_jobs),
        "jobs": formatted_jobs
    }


async def get_estimated_cost_summary_service(db: AsyncSession, tenant_id: str) -> dict:
    """
    Recalculates estimated costs for a summary view.
    Refactored for AsyncSession.
    """
    # 1. Operation counts per job
    op_counts_stmt = (
        select(
            models.JobOperation.job_id.label("job_id"),
            func.count(models.JobOperation.job_op_id).label("operation_count"),
        )
        .where(models.JobOperation.tenant_id == tenant_id)
        .group_by(models.JobOperation.job_id)
    )
    op_counts_res = await db.execute(op_counts_stmt)
    operation_counts = {row.job_id: row.operation_count for row in op_counts_res.all()}

    # 2. Latest completion dates
    comp_dates_stmt = (
        select(
            models.JobOperation.job_id.label("job_id"),
            func.max(models.JobOperation.actual_end_time).label("completion_date"),
        )
        .where(
            models.JobOperation.tenant_id == tenant_id,
            models.JobOperation.actual_end_time.isnot(None),
        )
        .group_by(models.JobOperation.job_id)
    )
    comp_dates_res = await db.execute(comp_dates_stmt)
    completion_dates = {row.job_id: row.completion_date for row in comp_dates_res.all()}

    # 3. Customer names
    cust_stmt = select(models.Customer).where(models.Customer.tenant_id == tenant_id)
    cust_res = await db.execute(cust_stmt)
    customers = {c.customer_id: c.name for c in cust_res.scalars().all()}

    # 4. Jobs
    jobs_stmt = select(models.Job).where(models.Job.tenant_id == tenant_id)
    jobs_res = await db.execute(jobs_stmt)
    jobs = jobs_res.scalars().all()

    costing_rows = []
    total_estimated_cost = 0.0
    open_estimated_cost = 0.0
    completed_estimated_cost = 0.0
    late_jobs_count = 0
    today = datetime.utcnow().date()

    for job in jobs:
        operation_count = operation_counts.get(job.job_id, 0)
        # Using Decimal if models use Numeric, but for estimation floats/Decimal works
        estimated_cost = float(job.quantity * operation_count * ESTIMATED_OPERATION_UNIT_COST)
        completion_date = completion_dates.get(job.job_id)
        
        is_late = False
        if job.status != models.JobStatus.COMPLETED and job.due_date:
            is_late = job.due_date.date() < today

        total_estimated_cost += estimated_cost
        if job.status == models.JobStatus.COMPLETED:
            completed_estimated_cost += estimated_cost
        else:
            open_estimated_cost += estimated_cost
        if is_late:
            late_jobs_count += 1

        costing_rows.append(
            {
                "job_id": str(job.job_id),
                "job_number": job.job_number,
                "customer_id": str(job.customer_id) if job.customer_id else None,
                "customer_name": customers.get(job.customer_id, "Unknown"),
                "quantity": job.quantity,
                "status": job.status,
                "priority": job.priority,
                "due_date": job.due_date.isoformat() if job.due_date else None,
                "operation_count": operation_count,
                "unit_operation_cost": ESTIMATED_OPERATION_UNIT_COST,
                "estimated_cost": round(estimated_cost, 2),
                "completion_date": completion_date.isoformat() if completion_date else None,
                "delayed": is_late,
            }
        )

    completed_jobs = [job for job in costing_rows if job["status"] == models.JobStatus.COMPLETED]
    completed_jobs.sort(key=lambda x: (x["completion_date"] or "", x["due_date"] or ""), reverse=True)

    highest_cost_job = max(costing_rows, key=lambda x: x["estimated_cost"], default=None)

    return {
        "overview": {
            "total_jobs": len(costing_rows),
            "active_jobs": sum(1 for job in costing_rows if job["status"] != models.JobStatus.COMPLETED),
            "completed_jobs": len(completed_jobs),
            "late_jobs": late_jobs_count,
            "total_estimated_cost": round(total_estimated_cost, 2),
            "open_estimated_cost": round(open_estimated_cost, 2),
            "completed_estimated_cost": round(completed_estimated_cost, 2),
            "average_estimated_job_cost": round(total_estimated_cost / len(costing_rows), 2) if costing_rows else 0,
            "highest_estimated_job_cost": highest_cost_job["estimated_cost"] if highest_cost_job else 0,
            "highest_estimated_job_number": highest_cost_job["job_number"] if highest_cost_job else None,
        },
        "recent_completed_jobs": completed_jobs[:8],
        "top_estimated_jobs": sorted(costing_rows, key=lambda x: x["estimated_cost"], reverse=True)[:5],
    }
