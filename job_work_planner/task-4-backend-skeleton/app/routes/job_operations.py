"""
job_operations.py
-----------------
Job Operation APIs

SCRUM 28:
- Update Job Operation Status (State Machine)

SCRUM 29:
- Plan Job Operation (Assign Machine / Shift / Dates)

SCRUM 31:
- Execution Controls (Start / Pause / Resume)

RESPONSIBILITIES (API LAYER ONLY):
- Authentication
- RBAC
- Input validation
- Call service layer
- Return response

IMPORTANT:
- NO business logic here
- All rules live in service layer
"""

from fastapi import APIRouter, HTTPException, Request, status

from app.core.job_operations_service import add_production_entry_service

# -------------------------------------------------------
# Import service layer functions
# -------------------------------------------------------
from app.core.job_operations_service import (
    update_job_operation_status,
    plan_job_operation_service,   # SCRUM 29
)

# -------------------------------------------------------
# Router (MUST be defined before decorators)
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
):
    """
    Update job operation status (SCRUM 28 + SCRUM 31 Execution Controls)

    Payload example:
    {
        "status": "IN_PROGRESS",  # or PAUSED, COMPLETED
        "quantity_completed": 5,  # Only if COMPLETED
        "quantity_rejected": 0,
        "rework_flag": false,
        "rework_note": null,
        "override_sequence": false
    }
    """

    # ---------------------------------------------------
    # 1. Authentication
    # ---------------------------------------------------
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )

    user = request.state.user
    role = user.get("role", "OPERATOR")

    # ---------------------------------------------------
    # 2. RBAC
    # ---------------------------------------------------
    if role not in {"OPERATOR", "SUPERVISOR", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden"
        )

    # ---------------------------------------------------
    # 3. Read payload
    # ---------------------------------------------------
    new_status = payload.get("status")
    quantity_completed = payload.get("quantity_completed")
    quantity_rejected = payload.get("quantity_rejected")
    rework_flag = payload.get("rework_flag", False)
    rework_note = payload.get("rework_note")
    override_sequence = payload.get("override_sequence", False)

    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status is required"
        )

    # ---------------------------------------------------
    # 4. Call service layer
    # ---------------------------------------------------
    try:
        updated_operation = update_job_operation_status(
            job_operation_id=job_operation_id,
            user_id=user["user_id"],   # <--- AUDIT: Pass user_id to service
            new_status=new_status,
            quantity_completed=quantity_completed,
            quantity_rejected=quantity_rejected,
            rework_flag=rework_flag,
            rework_note=rework_note,
            override_sequence=override_sequence,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    # ---------------------------------------------------
    # 5. Response
    # ---------------------------------------------------
    return updated_operation


# =======================================================
# SCRUM 29
# PATCH /job-operations/{job_operation_id}/plan
# =======================================================
@router.patch("/{job_operation_id}/plan")
def plan_job_operation(
    job_operation_id: str,
    payload: dict,
    request: Request,
):
    """
    Plan a job operation (SCRUM 29)

    Payload example:
    {
        "machine_id": "machine-1",
        "shift_id": "shift-A",
        "planned_start_date": "2026-02-01",
        "planned_end_date": "2026-02-02"
    }
    """

    # ---------------------------------------------------
    # 1. Authentication
    # ---------------------------------------------------
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )

    user = request.state.user
    role = user.get("role")

    # ---------------------------------------------------
    # 2. RBAC (Supervisor / Owner only)
    # ---------------------------------------------------
    if role not in {"SUPERVISOR", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Supervisor or Owner can plan operations"
        )

    # ---------------------------------------------------
    # 3. Read payload
    # ---------------------------------------------------
    machine_id = payload.get("machine_id")
    shift_id = payload.get("shift_id")
    planned_start_date = payload.get("planned_start_date")
    planned_end_date = payload.get("planned_end_date")

    # ---------------------------------------------------
    # 4. Basic input validation (API level)
    # ---------------------------------------------------
    if not machine_id or not shift_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="machine_id and shift_id are required"
        )

    if not planned_start_date or not planned_end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="planned_start_date and planned_end_date are required"
        )

    # ---------------------------------------------------
    # 5. Call service layer (core logic)
    # ---------------------------------------------------
    try:
        updated_operation = plan_job_operation_service(
            job_operation_id=job_operation_id,
            machine_id=machine_id,
            shift_id=shift_id,
            planned_start_date=planned_start_date,
            planned_end_date=planned_end_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    # ---------------------------------------------------
    # 6. Response
    # ---------------------------------------------------
    return updated_operation 



# -------------------------------------------------------
# SCRUM 32 – Record Production Entry
# POST /job-operations/{job_operation_id}/production
# -------------------------------------------------------

@router.post("/{job_operation_id}/production")
def record_production(
    job_operation_id: str,
    payload: dict,
    request: Request,
):
    """
    Records production quantities for an operation.
    """

    # --------------------------------------------
    # 1. Authentication
    # --------------------------------------------
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = request.state.user
    operator_id = user.get("user_id")

    produced_qty = payload.get("produced_qty", 0)
    scrap_qty = payload.get("scrap_qty", 0)
    rework_qty = payload.get("rework_qty", 0)
    notes = payload.get("notes")

    try:
        result = add_production_entry_service(
            job_operation_id=job_operation_id,
            produced_qty=produced_qty,
            scrap_qty=scrap_qty,
            rework_qty=rework_qty,
            operator_id=operator_id,
            notes=notes,
        )
        return result

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    


# -------------------------------------------------------
# GET Single Job Operation
# GET /job-operations/{job_operation_id}
# -------------------------------------------------------

from app.core.job_operations_service import JOB_OPERATIONS_TABLE


@router.get("/{job_operation_id}")
def get_job_operation(
    job_operation_id: str,
    request: Request,
):
    """
    Fetch a single job operation.
    Useful for debugging and UI stage tracking.
    """

    # Authentication
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    job_op = JOB_OPERATIONS_TABLE.get(job_operation_id)

    if not job_op:
        raise HTTPException(status_code=404, detail="Job operation not found")

    return job_op    