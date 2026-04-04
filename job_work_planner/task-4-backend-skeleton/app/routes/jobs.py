"""
job_operations.py
-----------------
Job Operation APIs

SCRUM 28: Update Job Operation Status
SCRUM 29/34: Plan Job Operation & Rescheduling
SCRUM 31: Execution Controls (Start / Pause / Resume)
SCRUM 32: Production Entry
RBAC: Strict Role Enforcement
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
<<<<<<< ours
from datetime import datetime
=======
import logging

# ---------------------------------------------------------------
# Import Scrum 25 service (business logic, NOT API)
# ---------------------------------------------------------------
from app.core.job_operations_service import create_job_operations
from app.routes.response_utils import api_success

>>>>>>> theirs

from app.database import get_db
from app import models

# -------------------------------------------------------
# Router
# -------------------------------------------------------
router = APIRouter(
    prefix="/job-operations",
    tags=["Job Operations"]
)

# -------------------------------------------------------
# Pydantic Schemas (Input Validation)
# -------------------------------------------------------
class StatusUpdatePayload(BaseModel):
    status: str
    quantity_completed: int = 0
    quantity_rejected: int = 0
    rework_flag: bool = False
    rework_note: Optional[str] = None
    override_sequence: bool = False

class PlanPayload(BaseModel):
    machine_id: str
    shift_id: Optional[str] = None
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    force: bool = False
    reason: Optional[str] = None
    ignore_conflicts: bool = False

class ProductionPayload(BaseModel):
    produced_qty: int = 0
    scrap_qty: int = 0
    rework_qty: int = 0
    notes: Optional[str] = None

# =======================================================
# SCRUM 28 + SCRUM 31
# PATCH /job-operations/{job_operation_id}/status
# =======================================================
@router.patch("/{job_operation_id}/status")
def update_operation_status(
    job_operation_id: str,
    payload: StatusUpdatePayload,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Update job operation status (Execution Controls).
    Allowed Roles: OPERATOR, SUPERVISOR, ADMIN
    """
    # 1. Authentication
    tenant_id = "tenant-123"
    role = "OPERATOR"
    if hasattr(request.state, "user"):
        tenant_id = request.state.user.get("tenant_id", "tenant-123")
        role = request.state.user.get("role", "OPERATOR")

    # 2. RBAC - Operators execute, Supervisors/Admins can step in. Planners CANNOT execute.
    if role not in {"OPERATOR", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Operators, Supervisors, or Admins can update execution status."
        )

    # 3. Find Operation in AWS RDS
    operation = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == tenant_id
    ).first()

    if not operation:
        raise HTTPException(status_code=404, detail="Job operation not found")

    # 4. Update Status and Timestamps
    operation.status = payload.status
    
    if payload.status == "IN_PROGRESS" and not operation.actual_start_time:
        operation.actual_start_time = datetime.utcnow().isoformat()
    elif payload.status == "COMPLETED":
        operation.actual_end_time = datetime.utcnow().isoformat()

    # 5. Save to AWS Database
    db.commit()
    db.refresh(operation)

    return {"message": "Status updated successfully", "operation": operation}


<<<<<<< ours
# =======================================================
# SCRUM 29 + SCRUM 34 + Conflict Validation
# PATCH /job-operations/{job_operation_id}/plan
# =======================================================
@router.patch("/{job_operation_id}/plan")
def plan_job_operation(
    job_operation_id: str,
    payload: PlanPayload,
=======
    # -----------------------------------------------------------
    # 9. Response
    # -----------------------------------------------------------
    return api_success({"job": job, "operations": job_operations}, message="Job created")

# -------------------------------------------------------------------
# GET /jobs  (Scrum 26)
# -------------------------------------------------------------------
@router.get("/")
def list_jobs(
>>>>>>> theirs
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Assigns or updates the plan.
    Allowed to Plan: PLANNER, SUPERVISOR, ADMIN
    Allowed to Override (force/ignore_conflicts): SUPERVISOR, ADMIN
    """
    # 1. Authentication
    tenant_id = "tenant-123"
    role = "PLANNER"
    if hasattr(request.state, "user"):
        tenant_id = request.state.user.get("tenant_id", "tenant-123")
        role = request.state.user.get("role", "PLANNER")
    
    # 2. RBAC Phase 1: Can they access the planning feature at all?
    if role not in {"PLANNER", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Forbidden: Only Planners, Supervisors, or Admins can assign schedules."
        )

<<<<<<< ours
    # 3. RBAC Phase 2: SUPERVISOR OVERRIDE RESTRICTION
    if payload.force or payload.ignore_conflicts:
        if role not in {"SUPERVISOR", "ADMIN", "OWNER"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Planners cannot override rules. Only Supervisors or Admins can force schedules."
            )

    # 4. Find Operation in AWS RDS
    operation = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == tenant_id
    ).first()

    if not operation:
        raise HTTPException(status_code=404, detail="Job operation not found")

    # 5. Apply the Plan
    operation.machine_id = payload.machine_id
    operation.shift_id = payload.shift_id
    
    # Save to AWS
    db.commit()
    db.refresh(operation)

    return {"message": "Plan assigned successfully", "operation": operation}
=======
    # ---------------------------------------------------------------
    # 6. Pagination slice
    # ---------------------------------------------------------------
    total_count = len(jobs)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_jobs = jobs[start:end]

    # ---------------------------------------------------------------
    # 7. Response
    # ---------------------------------------------------------------
    today = datetime.utcnow().date()
    enriched_items = []
    for job in paginated_jobs:
        due_date = datetime.fromisoformat(job["due_date"]).date()
        enriched_items.append({
            **job,
            "delayed": today > due_date and job["status"] != "COMPLETED",
        })

    return api_success({
        "items": enriched_items,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
    })
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs


# =======================================================
# SCRUM 32 – Record Production Entry
# POST /job-operations/{job_operation_id}/production
# =======================================================
@router.post("/{job_operation_id}/production")
def record_production(
    job_operation_id: str,
    payload: ProductionPayload,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Records production quantities for an operation.
    Allowed Roles: OPERATOR, SUPERVISOR, ADMIN
    """
    # 1. Authentication
    tenant_id = "tenant-123"
    operator_id = "user-001"
    role = "OPERATOR"
    if hasattr(request.state, "user"):
        tenant_id = request.state.user.get("tenant_id", "tenant-123")
        role = request.state.user.get("role", "OPERATOR")
        operator_id = request.state.user.get("user_id", "user-001")

    # 2. RBAC
    if role not in {"OPERATOR", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Operators, Supervisors, or Admins can record production."
        )

<<<<<<< ours
    # 3. Ensure Operation exists
    operation = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == tenant_id
    ).first()
=======
    # ---------------------------------------------------
    # 3. Response
    # ---------------------------------------------------
    return api_success(response)
<<<<<<< ours
=======


>>>>>>> theirs












>>>>>>> theirs

    if not operation:
        raise HTTPException(status_code=404, detail="Job operation not found")

    # 4. Create Production Entry in AWS RDS
    new_entry = models.ProductionEntry(
        entry_id=f"PRD-{str(uuid.uuid4())[:8]}",
        tenant_id=tenant_id,
        job_operation_id=job_operation_id,
        operator_id=operator_id,
        produced_qty=payload.produced_qty,
        scrap_qty=payload.scrap_qty,
        rework_qty=payload.rework_qty,
        timestamp=datetime.utcnow().isoformat()
    )

    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return {"message": "Production recorded", "entry": new_entry}


<<<<<<< ours
# =======================================================
# GET Single Job Operation
# GET /job-operations/{job_operation_id}
# =======================================================
@router.get("/{job_operation_id}")
def get_job_operation(
    job_operation_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    tenant_id = "tenant-123"
    if hasattr(request.state, "user"):
        tenant_id = request.state.user.get("tenant_id", "tenant-123")
=======
    # ---------------------------------------------------------------
    # 6. Response
    # ---------------------------------------------------------------
    return api_success({
        "job": {
            **job,
            "current_stage": current_stage,
            "delayed": delayed
        },
        "operations": operations
    })
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs

    # Fetch from AWS RDS
    job_op = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == tenant_id
    ).first()

    if not job_op:
        raise HTTPException(status_code=404, detail="Job operation not found")

    return job_op

# =======================================================
# AUDIT TRAIL
# GET /job-operations/{job_operation_id}/audit
# =======================================================
@router.get("/{job_operation_id}/audit")
def get_job_operation_audit(
    job_operation_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Fetch the immutable audit trail for a specific Job Operation.
    """
<<<<<<< ours
    tenant_id = "tenant-123"
    if hasattr(request.state, "user"):
        tenant_id = request.state.user.get("tenant_id", "tenant-123")

    # Fetch Audit Logs directly from AWS RDS
    audit_logs = db.query(models.AuditLog).filter(
        models.AuditLog.entity_type == "JOB_OPERATION",
        models.AuditLog.entity_id == job_operation_id,
        models.AuditLog.tenant_id == tenant_id
    ).all()

    return {"audit_trail": audit_logs}
=======
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    tenant_id = request.state.user["tenant_id"]

    # Optional: Verify Job exists and belongs to tenant here
    # job = JOBS_TABLE.get(job_id)
    # if not job or job["tenant_id"] != tenant_id: raise 404

    trail = get_audit_trail(
        tenant_id=tenant_id,
        entity_type="JOB",
        entity_id=job_id
    )

    return api_success({"audit_trail": trail})
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
