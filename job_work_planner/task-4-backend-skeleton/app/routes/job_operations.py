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
from app.database import get_db
from app import models

# -------------------------------------------------------
# Import service layer functions
# Notice: We removed the fake JOB_OPERATIONS_TABLE import!
# -------------------------------------------------------
from app.core.job_operations_service import (
    update_job_operation_status,
    plan_job_operation_service,
    add_production_entry_service,
    CapacityConflictError  
)

# If you implemented the audit service, keep this import!
from app.core.audit_service import get_audit_trail
from app.routes.response_utils import api_success

# -------------------------------------------------------
# Router
# -------------------------------------------------------
router = APIRouter(
    prefix="/job-operations",
    tags=["Job Operations"]
)

# =======================================================
# SCRUM 28 + SCRUM 31
# PATCH /job-operations/{job_operation_id}/status
# =======================================================
@router.patch("/{job_operation_id}/status")
def update_operation_status(
    job_operation_id: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
    """
    Update job operation status (Execution Controls).
    Allowed Roles: OPERATOR, SUPERVISOR, ADMIN
    """

    # 1. Authentication
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    user = request.state.user
    role = user.get("role", "OPERATOR")

    # 2. RBAC - Operators execute, Supervisors/Admins can step in. Planners CANNOT execute.
    if role not in {"OPERATOR", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Operators, Supervisors, or Admins can update execution status."
        )

    # 3. Read payload
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status is required"
        )

    # 4. Call service layer
    try:
        updated_operation = update_job_operation_status(
            db=db, # 👈 NEW: Pass database session to service layer
            job_operation_id=job_operation_id,
            tenant_id=user["tenant_id"],
            user_id=user["user_id"], 
            new_status=new_status,
            quantity_completed=payload.get("quantity_completed"),
            quantity_rejected=payload.get("quantity_rejected"),
            rework_flag=payload.get("rework_flag", False),
            rework_note=payload.get("rework_note"),
            override_sequence=payload.get("override_sequence", False),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    return api_success(updated_operation)


# =======================================================
# SCRUM 29 + SCRUM 34 + Conflict Validation
# PATCH /job-operations/{job_operation_id}/plan
# =======================================================
@router.patch("/{job_operation_id}/plan")
def plan_job_operation(
    job_operation_id: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
    """
    Assigns or updates the plan.
    Allowed to Plan: PLANNER, SUPERVISOR, ADMIN
    Allowed to Override (force/ignore_conflicts): SUPERVISOR, ADMIN
    """
    # 1. Authentication
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    user = request.state.user
    role = user.get("role")
    
    # 2. RBAC Phase 1: Can they access the planning feature at all?
    if role not in {"PLANNER", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Forbidden: Only Planners, Supervisors, or Admins can assign schedules."
        )

    # Read payload
    force = payload.get("force", False)
    reason = payload.get("reason")
    ignore_conflicts = payload.get("ignore_conflicts", False)

    # 3. RBAC Phase 2: SUPERVISOR OVERRIDE RESTRICTION
    if force or ignore_conflicts:
        if role not in {"SUPERVISOR", "ADMIN", "OWNER"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Planners cannot override rules. Only Supervisors or Admins can force schedules."
            )

    # 4. Call Service Layer
    try:
        updated_operation = plan_job_operation_service(
            db=db, # 👈 NEW: Pass database session to service layer
            job_operation_id=job_operation_id,
            machine_id=payload.get("machine_id"),
            shift_id=payload.get("shift_id"),
            planned_start_date=payload.get("planned_start_date"),
            planned_end_date=payload.get("planned_end_date"),
            force=force,
            reschedule_reason=reason,
            ignore_conflicts=ignore_conflicts, 
            tenant_id=user["tenant_id"]
        )
    except CapacityConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": exc.message,
                "clashes": exc.clashes,
                "resolution": "Submit request with ignore_conflicts=true and a reason to override."
            }
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    return api_success(updated_operation)


# =======================================================
# SCRUM 32 – Record Production Entry
# POST /job-operations/{job_operation_id}/production
# =======================================================
@router.post("/{job_operation_id}/production")
def record_production(
    job_operation_id: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
    """
    Records production quantities for an operation.
    Allowed Roles: OPERATOR, SUPERVISOR, ADMIN
    """
    # 1. Authentication
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = request.state.user
    role = user.get("role")
    operator_id = user.get("user_id")

    # 2. RBAC
    if role not in {"OPERATOR", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Operators, Supervisors, or Admins can record production."
        )

    try:
        result = add_production_entry_service(
            db=db, # 👈 NEW: Pass database session to service layer
            job_operation_id=job_operation_id,
            produced_qty=payload.get("produced_qty", 0),
            scrap_qty=payload.get("scrap_qty", 0),
            rework_qty=payload.get("rework_qty", 0),
            operator_id=operator_id,
            notes=payload.get("notes"),
            tenant_id=user["tenant_id"],
        )
        return api_success(result, message="Production recorded")

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# =======================================================
# GET Single Job Operation
# GET /job-operations/{job_operation_id}
# =======================================================
@router.get("/{job_operation_id}")
def get_job_operation(
    job_operation_id: str,
    request: Request,
    db: Session = Depends(get_db) # 👈 NEW: Get AWS Database session
):
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 👈 NEW: Fetch directly from AWS RDS instead of fake dictionary
    job_op = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == request.state.user["tenant_id"]
    ).first()

    if not job_op:
        raise HTTPException(status_code=404, detail="Job operation not found")

<<<<<<< ours
    return job_op
=======
    # 👇 NEW: STRICT TENANT CHECK
    if job_op.get("tenant_id") != request.state.user["tenant_id"]:
        raise HTTPException(status_code=404, detail="Job operation not found")

    return api_success(job_op)
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs

# =======================================================
# AUDIT TRAIL
# GET /job-operations/{job_operation_id}/audit
# =======================================================
@router.get("/{job_operation_id}/audit")
def get_job_operation_audit(
    job_operation_id: str,
    request: Request,
    db: Session = Depends(get_db) # 👈 NEW: Get AWS Database session
):
    """
    Fetch the immutable audit trail for a specific Job Operation.
    """
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    tenant_id = request.state.user["tenant_id"]

    trail = get_audit_trail(
        db=db, # 👈 NEW: Pass database session to audit service
        tenant_id=tenant_id,
        entity_type="JOB_OPERATION",
        entity_id=job_operation_id
    )

    return api_success({"audit_trail": trail})