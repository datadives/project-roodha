"""
jobs_by_stage_service.py
------------------------

SCRUM 30 – Jobs by Stage (Kanban View)

Responsibilities:
- Fetch tenant-scoped jobs
- Exclude cancelled jobs
- Determine current stage per job
- Group jobs by stage
- Apply optional date filter
- Sort jobs inside each stage
- Return UI-friendly kanban response
"""

from datetime import datetime
from collections import defaultdict
import logging
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger("jobwork-backend")

# -------------------------------------------------------
# Helper: Determine current stage of a job (In-Memory)
# -------------------------------------------------------
def _get_current_stage(operations: list) -> str:
    """
    Returns:
    - operation_id of first NOT_COMPLETED operation
    - 'COMPLETED' if all operations completed
    """
    if not operations:
        return "NOT_PLANNED"

    # Sort operations by sequence_number
    operations.sort(key=lambda x: x.sequence_number)

    for op in operations:
        if op.status != "COMPLETED":
            return op.operation_id

    return "COMPLETED"


# -------------------------------------------------------
# SCRUM 30: Main Service
# -------------------------------------------------------
def get_jobs_by_stage_service(
    db: Session, # 👈 NEW: Database session parameter
    tenant_id: str,
    date: str | None = None,
):
    """
    SCRUM 30 – Jobs by Stage (Kanban)
    """

    # ---------------------------------------------------
    # STEP 1: Parse date filter (optional)
    # ---------------------------------------------------
    filter_date = None
    if date:
        try:
            filter_date = datetime.fromisoformat(date).date()
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")

    # ---------------------------------------------------
    # STEP 2: Fetch tenant jobs from AWS RDS (exclude CANCELLED)
    # ---------------------------------------------------
    tenant_jobs = db.query(models.Job).filter(
        models.Job.tenant_id == tenant_id,
        models.Job.status != "CANCELLED"
    ).all()

    if not tenant_jobs:
        return {"stages": []}

    # ---------------------------------------------------
    # OPTIMIZATION: Fetch all operations for these jobs at once!
    # This prevents the dreaded "N+1 Query" performance issue.
    # ---------------------------------------------------
    job_ids = [job.job_id for job in tenant_jobs]
    all_operations = db.query(models.JobOperation).filter(
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.job_id.in_(job_ids)
    ).all()

    # Group operations by job_id in memory
    ops_by_job = defaultdict(list)
    for op in all_operations:
        ops_by_job[op.job_id].append(op)

    # ---------------------------------------------------
    # STEP 3: Group jobs by current stage
    # ---------------------------------------------------
    stage_map = defaultdict(list)

    for job in tenant_jobs:
        job_ops = ops_by_job.get(job.job_id, [])
        current_stage = _get_current_stage(job_ops)

        # ------------------------------------------------
        # STEP 4: Date filter (planned or active jobs)
        # ------------------------------------------------
        if filter_date:
            is_active_on_date = False

            for op in job_ops:
                # Check if the model has planned dates, fallback to actual times if needed
                start_date_str = getattr(op, "planned_start_date", op.actual_start_time)
                end_date_str = getattr(op, "planned_end_date", op.actual_end_time)

                if start_date_str and end_date_str:
                    start = datetime.fromisoformat(start_date_str).date()
                    end = datetime.fromisoformat(end_date_str).date()

                    if start <= filter_date <= end:
                        is_active_on_date = True
                        break

            if not is_active_on_date:
                continue

        # ------------------------------------------------
        # STEP 5: Compute delayed flag
        # ------------------------------------------------
        today = datetime.utcnow().date()
        due_date = datetime.fromisoformat(job.due_date).date()

        delayed = today > due_date and job.status != "COMPLETED"

        # ------------------------------------------------
        # STEP 6: Build job card
        # ------------------------------------------------
        job_card = {
            "job_id": job.job_id,
            "job_number": job.job_number,
            "customer_id": job.customer_id,
            "part_id": job.part_id,
            "qty": job.quantity,
            "due_date": job.due_date,
            "priority": job.priority,
            "delayed": delayed,
        }

        stage_map[current_stage].append(job_card)

    # ---------------------------------------------------
    # STEP 7: Sort jobs inside each stage
    # priority DESC → due_date ASC
    # ---------------------------------------------------
    priority_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    stages_response = []

    for stage_id, jobs_list in stage_map.items():
        jobs_list.sort(
            key=lambda j: (
                -priority_rank.get(j["priority"], 0),
                j["due_date"],
            )
        )

        stages_response.append(
            {
                "stage_id": stage_id,
                "stage_name": stage_id,
                "jobs": jobs_list,
                "counts": {
                    "total": len(jobs_list),
                    "delayed": sum(1 for j in jobs_list if j["delayed"]),
                },
            }
        )

    # ---------------------------------------------------
    # STEP 8: Audit log
    # ---------------------------------------------------
    logger.info(
        "JOBS_BY_STAGE_FETCHED",
        extra={
            "tenant_id": tenant_id,
            "date_filter": date,
            "stage_count": len(stages_response),
        },
    )

    # ---------------------------------------------------
    # STEP 9: Response
    # ---------------------------------------------------
    return {
        "stages": stages_response
    }