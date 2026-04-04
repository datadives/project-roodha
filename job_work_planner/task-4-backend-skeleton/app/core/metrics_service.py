# app/core/metrics_service.py

from datetime import datetime
from collections import defaultdict
import logging
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger("jobwork-backend")

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