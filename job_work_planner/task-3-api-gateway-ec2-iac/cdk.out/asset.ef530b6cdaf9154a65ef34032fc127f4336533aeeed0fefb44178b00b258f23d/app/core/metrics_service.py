# app/core/metrics_service.py

from datetime import datetime
from collections import defaultdict
import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger("jobwork-backend")
ESTIMATED_OPERATION_UNIT_COST = 12.5

# -------------------------------------------------------
# 1. WIP by Stage
# -------------------------------------------------------
def get_wip_metrics_service(db: Session, tenant_id: str, from_date: str | None = None, to_date: str | None = None) -> list:
    """
    Calculates Work-In-Progress (WIP) counts per operation stage.
    WIP = Operations that are currently active (READY, IN_PROGRESS, PAUSED).
    """
    # Fetch active operations directly from AWS
    active_ops = db.query(models.JobOperation).filter(
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.status.in_(["READY", "IN_PROGRESS", "PAUSED"])
    ).all()

    wip_counts = defaultdict(int)

    for op in active_ops:
        # Safely handle date filtering (in case you add planned_start_date later)
        start_date = getattr(op, "planned_start_date", None)
        if start_date:
            start = start_date[:10]
            if from_date and start < from_date: continue
            if to_date and start > to_date: continue

        wip_counts[op.operation_id] += 1

    # Format for charts (e.g., Recharts or Chart.js)
    return [{"stage": stage, "count": count} for stage, count in wip_counts.items()]


# -------------------------------------------------------
# 2. Bottleneck Machines
# -------------------------------------------------------
def get_bottleneck_metrics_service(db: Session, tenant_id: str, from_date: str | None = None, to_date: str | None = None) -> list:
    """
    Identifies machines with the highest backlog of operations.
    """
    # Fetch pending operations that are assigned to a machine
    pending_ops = db.query(models.JobOperation).filter(
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.machine_id.isnot(None),
        models.JobOperation.status.notin_(["COMPLETED", "CANCELLED"])
    ).all()

    machine_load = defaultdict(int)

    for op in pending_ops:
        start_date = getattr(op, "planned_start_date", None)
        if start_date:
            start = start_date[:10]
            if from_date and start < from_date: continue
            if to_date and start > to_date: continue

        machine_load[op.machine_id] += 1

    if not machine_load:
        return []

    # Fetch machine names from AWS so the dashboard looks nice!
    machines = db.query(models.Machine).filter(
        models.Machine.tenant_id == tenant_id,
        models.Machine.machine_id.in_(machine_load.keys())
    ).all()
    
    # Create a quick dictionary to map machine_id -> machine_name
    machine_names = {m.machine_id: m.name for m in machines}

    # Format and sort (highest load first)
    bottlenecks = [
        {
            "machine_id": m_id, 
            "machine_name": machine_names.get(m_id, m_id), # Fallback to ID if name missing
            "pending_operations": count
        } 
        for m_id, count in machine_load.items()
    ]
    bottlenecks.sort(key=lambda x: x["pending_operations"], reverse=True)
    
    return bottlenecks


# -------------------------------------------------------
# 3. Late Jobs
# -------------------------------------------------------
def get_late_jobs_service(db: Session, tenant_id: str) -> dict:
    """
    Returns jobs that have passed their due date but are not completed.
    """
    today = datetime.utcnow().date().isoformat()
    
    # Query AWS directly for late jobs! (This is much faster than the python loop)
    late_jobs = db.query(models.Job).filter(
        models.Job.tenant_id == tenant_id,
        models.Job.status != "COMPLETED",
        models.Job.due_date < today
    ).order_by(models.Job.due_date.asc()).all()

    formatted_jobs = []
    for job in late_jobs:
        formatted_jobs.append({
            "job_id": job.job_id,
            "job_number": job.job_number,
            "customer_id": job.customer_id,
            "due_date": job.due_date,
            "priority": job.priority,
            "status": job.status
        })

    return {
        "total_late": len(formatted_jobs),
        "jobs": formatted_jobs
    }


def calculate_estimated_job_cost_service(db: Session, tenant_id: str, job_id: str) -> dict:
    """
    V1.0 costing model:
    estimated_cost = quantity * number_of_route_operations * fixed_unit_rate
    """
    job = (
        db.query(models.Job)
        .filter(models.Job.job_id == job_id, models.Job.tenant_id == tenant_id)
        .first()
    )
    if not job:
        raise ValueError("Job not found")

    operation_count = (
        db.query(models.JobOperation)
        .filter(
            models.JobOperation.job_id == job_id,
            models.JobOperation.tenant_id == tenant_id,
        )
        .count()
    )

    estimated_cost = round(job.quantity * operation_count * ESTIMATED_OPERATION_UNIT_COST, 2)

    return {
        "job_id": job.job_id,
        "quantity": job.quantity,
        "operation_count": operation_count,
        "unit_operation_cost": ESTIMATED_OPERATION_UNIT_COST,
        "estimated_cost": estimated_cost,
    }


def get_estimated_cost_summary_service(db: Session, tenant_id: str) -> dict:
    operation_counts = {
        row.job_id: row.operation_count
        for row in (
            db.query(
                models.JobOperation.job_id.label("job_id"),
                func.count(models.JobOperation.job_operation_id).label("operation_count"),
            )
            .filter(models.JobOperation.tenant_id == tenant_id)
            .group_by(models.JobOperation.job_id)
            .all()
        )
    }

    completion_dates = {
        row.job_id: row.completion_date
        for row in (
            db.query(
                models.JobOperation.job_id.label("job_id"),
                func.max(models.JobOperation.actual_end_time).label("completion_date"),
            )
            .filter(
                models.JobOperation.tenant_id == tenant_id,
                models.JobOperation.actual_end_time.isnot(None),
            )
            .group_by(models.JobOperation.job_id)
            .all()
        )
    }

    customers = {
        customer.customer_id: customer.name
        for customer in db.query(models.Customer).filter(models.Customer.tenant_id == tenant_id).all()
    }

    jobs = db.query(models.Job).filter(models.Job.tenant_id == tenant_id).all()

    costing_rows = []
    total_estimated_cost = 0.0
    open_estimated_cost = 0.0
    completed_estimated_cost = 0.0
    late_jobs = 0
    today = datetime.utcnow().date().isoformat()

    for job in jobs:
        operation_count = operation_counts.get(job.job_id, 0)
        estimated_cost = round(job.quantity * operation_count * ESTIMATED_OPERATION_UNIT_COST, 2)
        completion_date = completion_dates.get(job.job_id)
        is_late = job.status != "COMPLETED" and job.due_date < today

        total_estimated_cost += estimated_cost
        if job.status == "COMPLETED":
            completed_estimated_cost += estimated_cost
        else:
            open_estimated_cost += estimated_cost
        if is_late:
            late_jobs += 1

        costing_rows.append(
            {
                "job_id": job.job_id,
                "job_number": job.job_number,
                "customer_id": job.customer_id,
                "customer_name": customers.get(job.customer_id, job.customer_id),
                "quantity": job.quantity,
                "status": job.status,
                "priority": job.priority,
                "due_date": job.due_date,
                "operation_count": operation_count,
                "unit_operation_cost": ESTIMATED_OPERATION_UNIT_COST,
                "estimated_cost": estimated_cost,
                "completion_date": completion_date,
                "delayed": is_late,
            }
        )

    completed_jobs = [job for job in costing_rows if job["status"] == "COMPLETED"]
    completed_jobs.sort(
        key=lambda job: (
            job["completion_date"] or "",
            job["due_date"] or "",
        ),
        reverse=True,
    )

    highest_cost_job = max(costing_rows, key=lambda job: job["estimated_cost"], default=None)

    return {
        "overview": {
            "total_jobs": len(costing_rows),
            "active_jobs": sum(1 for job in costing_rows if job["status"] != "COMPLETED"),
            "completed_jobs": len(completed_jobs),
            "late_jobs": late_jobs,
            "total_estimated_cost": round(total_estimated_cost, 2),
            "open_estimated_cost": round(open_estimated_cost, 2),
            "completed_estimated_cost": round(completed_estimated_cost, 2),
            "average_estimated_job_cost": round(total_estimated_cost / len(costing_rows), 2) if costing_rows else 0,
            "highest_estimated_job_cost": highest_cost_job["estimated_cost"] if highest_cost_job else 0,
            "highest_estimated_job_number": highest_cost_job["job_number"] if highest_cost_job else None,
        },
        "recent_completed_jobs": completed_jobs[:8],
        "top_estimated_jobs": sorted(costing_rows, key=lambda job: job["estimated_cost"], reverse=True)[:5],
    }
