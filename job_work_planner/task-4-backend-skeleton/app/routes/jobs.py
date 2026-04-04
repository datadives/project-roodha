from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.core.audit_service import get_audit_trail, log_audit_event
from app.core.job_operations_service import create_job_operations
from app.core.jobs_by_stage_service import get_jobs_by_stage_service
from app.database import get_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobCreatePayload(BaseModel):
    job_number: str = Field(..., min_length=1, max_length=255)
    customer_id: str
    part_id: str
    quantity: int = Field(..., gt=0)
    due_date: str = Field(..., min_length=10, max_length=64)
    priority: str = Field(..., min_length=1, max_length=32)
    status: str = Field(default="NOT_STARTED", min_length=1, max_length=32)


def _require_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


def _serialize_operation(operation) -> dict:
    return {
        "job_operation_id": operation.job_operation_id,
        "tenant_id": operation.tenant_id,
        "job_id": operation.job_id,
        "operation_id": operation.operation_id,
        "machine_id": operation.machine_id,
        "shift_id": operation.shift_id,
        "sequence_number": operation.sequence_number,
        "status": operation.status,
        "actual_start_time": operation.actual_start_time,
        "actual_end_time": operation.actual_end_time,
        "planned_start_date": operation.planned_start_date,
        "planned_end_date": operation.planned_end_date,
    }


def _current_stage_from_operations(operations: list[models.JobOperation]) -> str:
    if not operations:
        return "NOT_PLANNED"

    ordered_operations = sorted(operations, key=lambda operation: operation.sequence_number)
    for operation in ordered_operations:
        if operation.status != "COMPLETED":
            return operation.operation_id
    return "COMPLETED"


def _is_job_delayed(job: models.Job) -> bool:
    due_date = datetime.fromisoformat(job.due_date).date()
    return datetime.utcnow().date() > due_date and job.status != "COMPLETED"


def _serialize_job(job: models.Job, current_stage: str | None = None) -> dict:
    payload = {
        "job_id": job.job_id,
        "tenant_id": job.tenant_id,
        "job_number": job.job_number,
        "customer_id": job.customer_id,
        "part_id": job.part_id,
        "quantity": job.quantity,
        "due_date": job.due_date,
        "priority": job.priority,
        "status": job.status,
        "delayed": _is_job_delayed(job),
    }
    if current_stage is not None:
        payload["current_stage"] = current_stage
    return payload


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreatePayload, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request)
    tenant_id = user["tenant_id"]

    customer = (
        db.query(models.Customer)
        .filter(models.Customer.customer_id == payload.customer_id, models.Customer.tenant_id == tenant_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    part = (
        db.query(models.Part)
        .filter(models.Part.part_id == payload.part_id, models.Part.tenant_id == tenant_id)
        .first()
    )
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    if part.customer_id != payload.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Part does not belong to the provided customer",
        )

    existing_job = (
        db.query(models.Job)
        .filter(models.Job.tenant_id == tenant_id, models.Job.job_number == payload.job_number)
        .first()
    )
    if existing_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job number must be unique within tenant",
        )

    job = models.Job(
        job_id=f"JOB-{uuid.uuid4().hex[:8].upper()}",
        tenant_id=tenant_id,
        job_number=payload.job_number.strip(),
        customer_id=payload.customer_id,
        part_id=payload.part_id,
        quantity=payload.quantity,
        due_date=payload.due_date,
        priority=payload.priority.strip().upper(),
        status=payload.status.strip().upper(),
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    job_operations = create_job_operations(db=db, job_id=job.job_id, part_id=job.part_id, tenant_id=tenant_id)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        entity_type="JOB",
        entity_id=job.job_id,
        action="CREATED",
        user_id=user.get("user_id", "unknown"),
        after=_serialize_job(job),
    )

    return api_success(
        {
            "job": _serialize_job(job, current_stage=_current_stage_from_operations(job_operations)),
            "operations": [_serialize_operation(operation) for operation in job_operations],
        },
        message="Job created",
    )


@router.get("/")
def list_jobs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = Query(None),
    customer_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    tenant_id = _require_user(request)["tenant_id"]

    query = db.query(models.Job).filter(models.Job.tenant_id == tenant_id)
    if status_filter:
        query = query.filter(models.Job.status == status_filter)
    if priority:
        query = query.filter(models.Job.priority == priority)
    if customer_id:
        query = query.filter(models.Job.customer_id == customer_id)

    total_count = query.count()
    jobs = (
        query.order_by(models.Job.due_date.asc(), models.Job.job_number.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    job_ids = [job.job_id for job in jobs]
    operations = (
        db.query(models.JobOperation)
        .filter(models.JobOperation.tenant_id == tenant_id, models.JobOperation.job_id.in_(job_ids))
        .all()
        if job_ids
        else []
    )
    operations_by_job: dict[str, list[models.JobOperation]] = {}
    for operation in operations:
        operations_by_job.setdefault(operation.job_id, []).append(operation)

    items = [
        _serialize_job(job, current_stage=_current_stage_from_operations(operations_by_job.get(job.job_id, [])))
        for job in jobs
    ]

    return api_success(
        {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
        }
    )


@router.get("/by-stage")
def list_jobs_by_stage(
    request: Request,
    date: str | None = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    tenant_id = _require_user(request)["tenant_id"]
    response = get_jobs_by_stage_service(db=db, tenant_id=tenant_id, date=date)
    return api_success(response)


@router.get("/{job_id}")
def get_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    tenant_id = _require_user(request)["tenant_id"]

    job = (
        db.query(models.Job)
        .filter(models.Job.job_id == job_id, models.Job.tenant_id == tenant_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    operations = (
        db.query(models.JobOperation)
        .filter(models.JobOperation.job_id == job_id, models.JobOperation.tenant_id == tenant_id)
        .order_by(models.JobOperation.sequence_number.asc())
        .all()
    )

    return api_success(
        {
            "job": _serialize_job(job, current_stage=_current_stage_from_operations(operations)),
            "operations": [_serialize_operation(operation) for operation in operations],
        }
    )


@router.get("/{job_id}/audit")
def get_job_audit(job_id: str, request: Request, db: Session = Depends(get_db)):
    tenant_id = _require_user(request)["tenant_id"]
    trail = get_audit_trail(db=db, tenant_id=tenant_id, entity_type="JOB", entity_id=job_id)
    return api_success({"audit_trail": jsonable_encoder(trail)})
