from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.core.audit_service import get_audit_trail
from app.core.job_operations_service import (
    CapacityConflictError,
    add_production_entry_service,
    plan_job_operation_service,
    update_job_operation_status,
)
from app.database import get_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/job-operations", tags=["Job Operations"])


class StatusUpdatePayload(BaseModel):
    status: str
    quantity_completed: int = 0
    quantity_rejected: int = 0
    rework_flag: bool = False
    rework_note: str | None = None
    override_sequence: bool = False
    actual_start_time: str | None = None
    actual_end_time: str | None = None


class PlanPayload(BaseModel):
    machine_id: str
    shift_id: str | None = None
    planned_start_date: str | None = None
    planned_end_date: str | None = None
    force: bool = False
    reason: str | None = None
    ignore_conflicts: bool = False


class ProductionPayload(BaseModel):
    produced_qty: int = 0
    scrap_qty: int = 0
    rework_qty: int = 0
    notes: str | None = None


def _require_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


def _serialize_job_operation(job_operation) -> dict:
    return {
        "job_operation_id": job_operation.job_operation_id,
        "tenant_id": job_operation.tenant_id,
        "job_id": job_operation.job_id,
        "operation_id": job_operation.operation_id,
        "machine_id": job_operation.machine_id,
        "shift_id": job_operation.shift_id,
        "sequence_number": job_operation.sequence_number,
        "status": job_operation.status,
        "actual_start_time": job_operation.actual_start_time,
        "actual_end_time": job_operation.actual_end_time,
        "planned_start_date": job_operation.planned_start_date,
        "planned_end_date": job_operation.planned_end_date,
    }


@router.patch("/{job_operation_id}/status")
def update_operation_status(
    job_operation_id: str,
    payload: StatusUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_user(request)
    role = user.get("role", "OPERATOR")

    if role not in {"OPERATOR", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Operators, Supervisors, or Admins can update execution status.",
        )

    try:
        updated_operation = update_job_operation_status(
            db=db,
            job_operation_id=job_operation_id,
            tenant_id=user["tenant_id"],
            user_id=user.get("user_id", "unknown"),
            new_status=payload.status,
            quantity_completed=payload.quantity_completed,
            quantity_rejected=payload.quantity_rejected,
            rework_flag=payload.rework_flag,
            rework_note=payload.rework_note,
            override_sequence=payload.override_sequence,
            actual_start_time=payload.actual_start_time,
            actual_end_time=payload.actual_end_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return api_success(_serialize_job_operation(updated_operation), message="Status updated successfully")


@router.patch("/{job_operation_id}/plan")
def plan_job_operation(
    job_operation_id: str,
    payload: PlanPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_user(request)
    role = user.get("role", "PLANNER")

    if role not in {"PLANNER", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Planners, Supervisors, or Admins can assign schedules.",
        )

    if (payload.force or payload.ignore_conflicts) and role not in {"SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Planners cannot override rules. Only Supervisors or Admins can force schedules.",
        )

    try:
        updated_operation = plan_job_operation_service(
            db=db,
            job_operation_id=job_operation_id,
            machine_id=payload.machine_id,
            shift_id=payload.shift_id,
            planned_start_date=payload.planned_start_date,
            planned_end_date=payload.planned_end_date,
            force=payload.force,
            reschedule_reason=payload.reason,
            ignore_conflicts=payload.ignore_conflicts,
            tenant_id=user["tenant_id"],
            user_id=user.get("user_id", "unknown"),
        )
    except CapacityConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": exc.message,
                "clashes": exc.clashes,
                "resolution": "Submit request with ignore_conflicts=true and a reason to override.",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return api_success(_serialize_job_operation(updated_operation), message="Plan assigned successfully")


@router.post("/{job_operation_id}/production")
def record_production(
    job_operation_id: str,
    payload: ProductionPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_user(request)
    role = user.get("role", "OPERATOR")

    if role not in {"OPERATOR", "SUPERVISOR", "ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Operators, Supervisors, or Admins can record production.",
        )

    try:
        entry = add_production_entry_service(
            db=db,
            job_operation_id=job_operation_id,
            produced_qty=payload.produced_qty,
            scrap_qty=payload.scrap_qty,
            rework_qty=payload.rework_qty,
            operator_id=user.get("user_id", "unknown"),
            notes=payload.notes,
            tenant_id=user["tenant_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return api_success(jsonable_encoder(entry), message="Production recorded")


@router.get("/{job_operation_id}")
def get_job_operation(job_operation_id: str, request: Request, db: Session = Depends(get_db)):
    tenant_id = _require_user(request)["tenant_id"]

    job_operation = (
        db.query(models.JobOperation)
        .filter(
            models.JobOperation.job_operation_id == job_operation_id,
            models.JobOperation.tenant_id == tenant_id,
        )
        .first()
    )
    if not job_operation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job operation not found")

    return api_success(_serialize_job_operation(job_operation))


@router.get("/{job_operation_id}/audit")
def get_job_operation_audit(job_operation_id: str, request: Request, db: Session = Depends(get_db)):
    tenant_id = _require_user(request)["tenant_id"]
    trail = get_audit_trail(db=db, tenant_id=tenant_id, entity_type="JOB_OPERATION", entity_id=job_operation_id)
    return api_success({"audit_trail": jsonable_encoder(trail)})
