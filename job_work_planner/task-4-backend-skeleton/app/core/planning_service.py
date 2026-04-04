# app/core/planning_service.py

from datetime import datetime
from collections import defaultdict
import logging
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger("jobwork-backend")

def get_planning_calendar_service(
    db: Session,  # 👈 NEW: Database session parameter
    tenant_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    machine_id: str | None = None,
    shift_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """
    Builds a planner-friendly aggregated schedule directly from AWS RDS.
    """
    # ---------------------------------------------------
    # 1. Fetch & Filter Operations (Using SQL Database)
    # ---------------------------------------------------
    query = db.query(models.JobOperation).filter(
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.machine_id.isnot(None),
        models.JobOperation.planned_start_date.isnot(None)
    )

    if machine_id:
        query = query.filter(models.JobOperation.machine_id == machine_id)
    if shift_id:
        query = query.filter(models.JobOperation.shift_id == shift_id)
    if status:
        query = query.filter(models.JobOperation.status == status)

    # Date range filtering
    if from_date:
        query = query.filter(models.JobOperation.planned_end_date >= from_date)
    if to_date:
        query = query.filter(models.JobOperation.planned_start_date <= to_date)

    # ---------------------------------------------------
    # 2. Count, Sort & Paginate (Lightning fast via SQL)
    # ---------------------------------------------------
    total_count = query.count()

    paginated_ops = query.order_by(
        models.JobOperation.planned_start_date.asc(),
        models.JobOperation.sequence_number.asc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    # ---------------------------------------------------
    # 3. Enrich Data (Preventing N+1 Queries)
    # ---------------------------------------------------
    # Gather all unique Job IDs and Operation Master IDs from the 50 results
    job_ids = list({op.job_id for op in paginated_ops})
    op_master_ids = list({op.operation_id for op in paginated_ops})

    # Fetch them all at once
    jobs = {j.job_id: j for j in db.query(models.Job).filter(models.Job.job_id.in_(job_ids)).all()} if job_ids else {}
    op_masters = {om.operation_id: om for om in db.query(models.OperationsMaster).filter(models.OperationsMaster.operation_id.in_(op_master_ids)).all()} if op_master_ids else {}

    # ---------------------------------------------------
    # 4. Group (Machine -> Shift -> Date -> Ops)
    # ---------------------------------------------------
    calendar = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for op in paginated_ops:
        job = jobs.get(op.job_id)
        op_master = op_masters.get(op.operation_id)

        # Handle date extraction safely
        op_date = op.planned_start_date[:10]
        m_id = op.machine_id
        s_id = op.shift_id

        # Build the enriched DTO required by the Acceptance Criteria
        enriched_op = {
            "job_operation_id": op.job_operation_id,
            "job_id": op.job_id,
            "job_number": job.job_number if job else "UNKNOWN",
            "op_name": op_master.name if op_master else op.operation_id,
            "status": op.status,
            "planned_qty": job.quantity if job else 0,
            "due_date": job.due_date if job else None,
            "priority": job.priority if job else None,
            "sequence_number": op.sequence_number
        }

        calendar[m_id][s_id][op_date].append(enriched_op)

    # Convert defaultdict to standard dict for clean JSON serialization
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