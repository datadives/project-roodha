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

NOTE:
- MVP implementation uses in-memory stores
- DynamoDB / GSI to be added later
"""

from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger("jobwork-backend")

# -------------------------------------------------------
# TEMP MOCK IMPORTS (replace with DB later)
# -------------------------------------------------------
from app.routes.jobs import JOBS_TABLE
from app.core.job_operations_service import JOB_OPERATIONS_TABLE


# -------------------------------------------------------
# Helper: Determine current stage of a job
# -------------------------------------------------------
def _get_current_stage(job_id: str) -> str:
    """
    Returns:
    - operation_id of first NOT_COMPLETED operation
    - 'COMPLETED' if all operations completed
    """

    operations = [
        op for op in JOB_OPERATIONS_TABLE.values()
        if op["job_id"] == job_id
    ]

    if not operations:
        return "NOT_PLANNED"

    operations.sort(key=lambda x: x["sequence_number"])

    for op in operations:
        if op["status"] != "COMPLETED":
            return op["operation_id"]

    return "COMPLETED"


# -------------------------------------------------------
# SCRUM 30: Main Service
# -------------------------------------------------------
def get_jobs_by_stage_service(
    *,
    tenant_id: str,
    date: str | None = None,
):
    """
    SCRUM 30 – Jobs by Stage (Kanban)

    Args:
        tenant_id: Tenant from JWT
        date: Optional YYYY-MM-DD filter

    Returns:
        {
          "stages": [
            {
              "stage_id": "op-cut",
              "stage_name": "op-cut",
              "jobs": [...],
              "counts": {...}
            }
          ]
        }
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
    # STEP 2: Fetch tenant jobs (exclude CANCELLED)
    # ---------------------------------------------------
    tenant_jobs = [
        job for job in JOBS_TABLE.values()
        if job["tenant_id"] == tenant_id
        and job["status"] != "CANCELLED"
    ]

    # ---------------------------------------------------
    # STEP 3: Group jobs by current stage
    # ---------------------------------------------------
    stage_map = defaultdict(list)

    for job in tenant_jobs:
        job_id = job["job_id"]

        current_stage = _get_current_stage(job_id)

        # ------------------------------------------------
        # STEP 4: Date filter (planned or active jobs)
        # Rule (documented):
        # Include job if ANY operation planned on that date
        # ------------------------------------------------
        if filter_date:
            planned_ops = [
                op for op in JOB_OPERATIONS_TABLE.values()
                if op["job_id"] == job_id
                and op.get("planned_start_date")
                and op.get("planned_end_date")
            ]

            is_active_on_date = False

            for op in planned_ops:
                start = datetime.fromisoformat(op["planned_start_date"]).date()
                end = datetime.fromisoformat(op["planned_end_date"]).date()

                if start <= filter_date <= end:
                    is_active_on_date = True
                    break

            if not is_active_on_date:
                continue

        # ------------------------------------------------
        # STEP 5: Compute delayed flag
        # ------------------------------------------------
        today = datetime.utcnow().date()
        due_date = datetime.fromisoformat(job["due_date"]).date()

        delayed = today > due_date and job["status"] != "COMPLETED"

        # ------------------------------------------------
        # STEP 6: Build job card
        # ------------------------------------------------
        job_card = {
            "job_id": job["job_id"],
            "job_number": job["job_number"],
            "customer_id": job["customer_id"],
            "part_id": job["part_id"],
            "qty": job["quantity"],
            "due_date": job["due_date"],
            "priority": job["priority"],
            "delayed": delayed,
        }

        stage_map[current_stage].append(job_card)

    # ---------------------------------------------------
    # STEP 7: Sort jobs inside each stage
    # priority DESC → due_date ASC
    # ---------------------------------------------------
    priority_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    stages_response = []

    for stage_id, jobs in stage_map.items():
        jobs.sort(
            key=lambda j: (
                -priority_rank.get(j["priority"], 0),
                j["due_date"],
            )
        )

        stages_response.append(
            {
                "stage_id": stage_id,
                "stage_name": stage_id,
                "jobs": jobs,
                "counts": {
                    "total": len(jobs),
                    "delayed": sum(1 for j in jobs if j["delayed"]),
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