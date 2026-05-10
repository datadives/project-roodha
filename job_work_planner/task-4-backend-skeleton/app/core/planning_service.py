"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: planning_service.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
# app/core/planning_service.py

from datetime import datetime, timedelta, date
from collections import defaultdict
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app import models

logger = logging.getLogger("jobwork-backend")

async def get_planning_calendar_service(
    db: AsyncSession,
    tenant_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    machine_id: str | None = None,
    shift_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """
    Builds a planner-friendly aggregated schedule using AsyncSession.
    """
    # 1. Base Query for Operations
    stmt = select(models.JobOperation).where(
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.machine_id.isnot(None),
        models.JobOperation.planned_start_date.isnot(None)
    )

    if machine_id:
        stmt = stmt.where(models.JobOperation.machine_id == machine_id)
    if shift_id:
        stmt = stmt.where(models.JobOperation.shift_id == shift_id)
    if status:
        stmt = stmt.where(models.JobOperation.status == status)

    if from_date:
        # planned_end_date >= from_date
        stmt = stmt.where(models.JobOperation.planned_end_date >= datetime.fromisoformat(from_date))
    if to_date:
        # planned_start_date <= to_date
        stmt = stmt.where(models.JobOperation.planned_start_date <= datetime.fromisoformat(to_date))

    # 2. Count Total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_res = await db.execute(count_stmt)
    total_count = count_res.scalar_one()

    # 3. Paginate & Fetch
    stmt = stmt.order_by(
        models.JobOperation.planned_start_date.asc(),
        models.JobOperation.sequence_number.asc()
    ).offset((page - 1) * page_size).limit(page_size)
    
    res = await db.execute(stmt)
    paginated_ops = res.scalars().all()

    if not paginated_ops:
        return {
            "data": {},
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size if page_size else 0
            }
        }

    # 4. Bulk Enrich (Jobs & OpMasters)
    job_ids = list({op.job_id for op in paginated_ops})
    op_m_ids = list({op.op_id for op in paginated_ops})

    jobs_stmt = select(models.Job).where(models.Job.job_id.in_(job_ids))
    jobs_res = await db.execute(jobs_stmt)
    jobs = {j.job_id: j for j in jobs_res.scalars().all()}

    op_m_stmt = select(models.OperationsMaster).where(models.OperationsMaster.operation_id.in_(op_m_ids))
    op_m_res = await db.execute(op_m_stmt)
    op_masters = {om.operation_id: om for om in op_m_res.scalars().all()}


    # 5. Group Data
    calendar = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for op in paginated_ops:
        job = jobs.get(op.job_id)
        op_master = op_masters.get(op.op_id)

        # Date string from DateTime
        op_date = op.planned_start_date.date().isoformat()
        m_id = str(op.machine_id)
        s_id = str(op.shift_id) if op.shift_id else "No Shift"

        enriched_op = {
            "job_op_id": str(op.job_op_id),
            "job_id": str(op.job_id),
            "job_number": job.job_number if job else "UNKNOWN",
            "op_name": op_master.name if op_master else str(op.op_id),
            "status": op.status,
            "planned_qty": job.quantity if job else 0,
            "due_date": job.due_date.isoformat() if job and job.due_date else None,
            "priority": job.priority if job else None,
            "sequence_number": op.sequence_number
        }
        calendar[m_id][s_id][op_date].append(enriched_op)


    # 6. Final Formatting
    grouped_data = {
        m: {
            s: dict(dates) for s, dates in shifts.items()
        } for m, shifts in calendar.items()
    }

    return {
        "data": grouped_data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size if page_size else 0
        }
    }


async def get_machine_load_service(db: AsyncSession, tenant_id: str) -> List[Dict[str, Any]]:
    """
    Business Logic (The Radar): Aggregates Machine load for the next 7 days.
    Calculates hours as (quantity * cycle_time / 60).
    Fallback: 0.1 hours per operation if missing cycle time.
    """
    start_date = date.today() - timedelta(days=1)
    end_date = start_date + timedelta(days=7)

    # Fetch operations in the next 7 days - Joining Job and OperationsMaster for calculation data
    stmt = (
        select(
            models.JobOperation,
            models.Job.quantity,
            models.OperationsMaster.standard_cycle_time_mins,
            models.Machine.name.label("machine_name")
        )
        .join(models.Job, models.JobOperation.job_id == models.Job.job_id)
        .join(models.OperationsMaster, models.JobOperation.op_id == models.OperationsMaster.operation_id)

        .join(models.Machine, models.JobOperation.machine_id == models.Machine.machine_id)
        .where(
            models.JobOperation.tenant_id == tenant_id,
            models.JobOperation.planned_start_date >= datetime.combine(start_date, datetime.min.time()),
            models.JobOperation.planned_start_date < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
            models.JobOperation.status != models.OperationStatus.CANCELLED
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Aggregate by machine and date
    load_map = defaultdict(lambda: defaultdict(float))
    estimation_map = defaultdict(lambda: defaultdict(bool))
    machine_names = {}

    for row in rows:
        op = row.JobOperation
        qty = row.quantity
        cycle_time = row.standard_cycle_time_mins
        m_id = op.machine_id
        m_name = row.machine_name
        
        op_date = op.planned_start_date.date()
        machine_names[m_id] = m_name

        # Calculate Hours
        safe_cycle_time = cycle_time if cycle_time and cycle_time > 0 else 1.0  # fallback to 1 minute
        hours = (qty * safe_cycle_time) / 60.0
        if not cycle_time or cycle_time <= 0:
            logger.warning(f"Missing/Zero cycle time for Op: {op.job_op_id}. Falling back to 1 minute per unit.")
            estimation_map[m_id][op_date] = True
        load_map[m_id][op_date] += hours

    # Format response
    load_data = []
    for m_id, dates in load_map.items():
        for op_date, total_hours in dates.items():
            load_data.append({
                "machine_id": m_id,
                "machine_name": machine_names.get(m_id),
                "date": op_date,
                "total_hours": round(total_hours, 2),
                "is_overloaded": total_hours > 10.0,
                "is_estimated": estimation_map[m_id].get(op_date, False)
            })

    # Sort by date and then machine name
    load_data.sort(key=lambda x: (x["date"], x["machine_name"]))
    
    return load_data
