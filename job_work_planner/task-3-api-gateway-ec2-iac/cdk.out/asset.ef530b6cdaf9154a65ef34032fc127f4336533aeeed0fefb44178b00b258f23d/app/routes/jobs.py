import io
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.core.audit_service import get_audit_trail, log_audit_event
from app.core.costing_engine import calculate_job_cost
from app.core.invoice_generator import generate_invoice
from app.core.job_operations_service import create_job_operations
from app.core.jobs_by_stage_service import get_jobs_by_stage_service
from app.core.metrics_service import calculate_estimated_job_cost_service
from app.database import get_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobCreatePayload(BaseModel):
    job_number: str | None = Field(default=None, min_length=1, max_length=255)
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


def _require_roles(user: dict, allowed_roles: set[str], message: str) -> None:
    role = str(user.get("role") or "").upper()
    if role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def _generate_job_number(db: Session, tenant_id: str) -> str:
    while True:
        candidate = f"JW-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        existing_job = (
            db.query(models.Job)
            .filter(models.Job.tenant_id == tenant_id, models.Job.job_number == candidate)
            .first()
        )
        if not existing_job:
            return candidate


def _canonical_operation_id(raw_operation_id: str | None) -> str | None:
    normalized = (raw_operation_id or "").strip()
    if not normalized:
        return None

    alias_map = {
        "QC": "QUALITY_CHECK",
        "QUALITYCHECK": "QUALITY_CHECK",
        "QUALITY-CHECK": "QUALITY_CHECK",
        "QUALITY CHECK": "QUALITY_CHECK",
    }
    return alias_map.get(normalized.upper(), normalized.upper().replace(" ", "_").replace("-", "_"))


def _validate_part_route_operations(db: Session, tenant_id: str, part: models.Part) -> None:
    route = part.default_operations_route or []
    route_operation_ids = []
    for step in route:
        operation_id = _canonical_operation_id(step.get("operation_id"))
        if not operation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Part route contains a step without operation_id",
            )
        route_operation_ids.append(operation_id)

    existing_operation_ids = {
        operation_id
        for (operation_id,) in db.query(models.OperationsMaster.operation_id)
        .filter(
            models.OperationsMaster.tenant_id == tenant_id,
            models.OperationsMaster.operation_id.in_(route_operation_ids),
        )
        .all()
    }
    missing_operation_ids = [
        operation_id for operation_id in route_operation_ids if operation_id not in existing_operation_ids
    ]
    if missing_operation_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Part route contains unknown operation_id values: {', '.join(missing_operation_ids)}",
        )


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
    try:
        due_date = datetime.fromisoformat(job.due_date).date()
    except ValueError:
        return False
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
        "quoted_price": float(job.quoted_price) if getattr(job, "quoted_price", None) is not None else None,
        "delayed": _is_job_delayed(job),
    }
    if current_stage is not None:
        payload["current_stage"] = current_stage
    return payload


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreatePayload, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request)
    _require_roles(
        user,
        {"SUPERVISOR", "ADMIN", "OWNER"},
        "Forbidden: Only Supervisors, Owners, or Admins can create jobs.",
    )
    tenant_id = user["tenant_id"]

    try:
        datetime.fromisoformat(payload.due_date).date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Due date must be a valid ISO date")

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
    _validate_part_route_operations(db, tenant_id, part)

    job_number = payload.job_number.strip() if payload.job_number else _generate_job_number(db, tenant_id)

    existing_job = (
        db.query(models.Job)
        .filter(models.Job.tenant_id == tenant_id, models.Job.job_number == job_number)
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
        job_number=job_number,
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

    job_operations = create_job_operations(
        db=db,
        job_id=job.job_id,
        part_id=job.part_id,
        tenant_id=tenant_id,
        user_id=user.get("user_id", "unknown"),
    )
    current_stage = _current_stage_from_operations(job_operations)
    costing = calculate_estimated_job_cost_service(db=db, tenant_id=tenant_id, job_id=job.job_id)
    job_payload = _serialize_job(job, current_stage=current_stage)
    job_payload["estimated_cost"] = costing["estimated_cost"]

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        entity_type="JOB",
        entity_id=job.job_id,
        action="CREATED",
        user_id=user.get("user_id", "unknown"),
        after={**job_payload, "costing": costing},
    )

    return api_success(
        {
            "job": job_payload,
            "operations": [_serialize_operation(operation) for operation in job_operations],
            "costing": costing,
        },
        message="Job created",
    )


@router.get("")
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


@router.post("/{job_id}/recalculate-cost")
def recalculate_job_cost(job_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Manual cost recalculation trigger.
    Intended as a local development substitute for the EventBridge Lambda
    until the AWS scheduled job is live in production.
    """
    user = _require_user(request)
    _require_roles(
        user,
        {"OWNER", "ADMIN", "SUPERVISOR"},
        "Forbidden: Only Owners, Admins, or Supervisors can trigger cost recalculation.",
    )

    try:
        result = calculate_job_cost(
            job_id=job_id,
            tenant_id=user["tenant_id"],
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return api_success(result, message="Cost recalculated successfully")


@router.get("/{job_id}/cost-summary")
def get_job_cost_summary(job_id: str, request: Request, db: Session = Depends(get_db)):
    tenant_id = _require_user(request)["tenant_id"]

    job = (
        db.query(models.Job)
        .filter(models.Job.job_id == job_id, models.Job.tenant_id == tenant_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    summary = (
        db.query(models.JobCostSummary)
        .filter(
            models.JobCostSummary.job_id == job_id,
            models.JobCostSummary.tenant_id == tenant_id,
        )
        .first()
    )
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No cost summary available for this job yet")

    return api_success(
        {
            "summary_id": summary.summary_id,
            "tenant_id": summary.tenant_id,
            "job_id": summary.job_id,
            "machine_cost": float(summary.machine_cost) if summary.machine_cost is not None else None,
            "labour_cost": float(summary.labour_cost) if summary.labour_cost is not None else None,
            "material_cost": float(summary.material_cost) if summary.material_cost is not None else None,
            "total_cost": float(summary.total_cost) if summary.total_cost is not None else None,
            "last_calculated_at": summary.last_calculated_at.isoformat() if summary.last_calculated_at else None,
        }
    )


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
    costing = calculate_estimated_job_cost_service(db=db, tenant_id=tenant_id, job_id=job_id)
    job_payload = _serialize_job(job, current_stage=_current_stage_from_operations(operations))
    job_payload["estimated_cost"] = costing["estimated_cost"]

    return api_success(
        {
            "job": job_payload,
            "operations": [_serialize_operation(operation) for operation in operations],
            "costing": costing,
        }
    )


@router.get("/{job_id}/audit")
def get_job_audit(job_id: str, request: Request, db: Session = Depends(get_db)):
    tenant_id = _require_user(request)["tenant_id"]
    trail = get_audit_trail(db=db, tenant_id=tenant_id, entity_type="JOB", entity_id=job_id)
    return api_success({"audit_trail": jsonable_encoder(trail)})


@router.get("/{job_id}/download-invoice")
def download_invoice(job_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Stream a PDF invoice for the given job.
    Combines data from Jobs, Customers, Parts, and JobCostSummary.
    """
    tenant_id = _require_user(request)["tenant_id"]

    job = (
        db.query(models.Job)
        .filter(models.Job.job_id == job_id, models.Job.tenant_id == tenant_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Fetch related records
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.customer_id == job.customer_id, models.Customer.tenant_id == tenant_id)
        .first()
    )
    tenant = (
        db.query(models.Tenant)
        .filter(models.Tenant.tenant_id == tenant_id)
        .first()
    )
    cost_summary = (
        db.query(models.JobCostSummary)
        .filter(models.JobCostSummary.job_id == job_id, models.JobCostSummary.tenant_id == tenant_id)
        .first()
    )

    job_data = {
        "job_id": job.job_id,
        "job_number": job.job_number,
        "customer_name": customer.name if customer else job.customer_id,
        "factory_name": tenant.company_name if tenant else "Factory",
        "due_date": job.due_date,
        "quantity": job.quantity,
        "quoted_price": float(job.quoted_price) if job.quoted_price is not None else None,
        "machine_cost": float(cost_summary.machine_cost) if cost_summary and cost_summary.machine_cost is not None else None,
        "labour_cost": float(cost_summary.labour_cost) if cost_summary and cost_summary.labour_cost is not None else None,
        "material_cost": float(cost_summary.material_cost) if cost_summary and cost_summary.material_cost is not None else None,
        "total_cost": float(cost_summary.total_cost) if cost_summary and cost_summary.total_cost is not None else None,
        "last_calculated_at": cost_summary.last_calculated_at.isoformat() if cost_summary and cost_summary.last_calculated_at else None,
    }

    try:
        pdf_bytes = generate_invoice(job_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    filename = f"Invoice_{job.job_number or job_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class QuotedPricePayload(BaseModel):
    quoted_price: float = Field(..., ge=0, description="Customer-facing quoted price in INR")


@router.patch("/{job_id}/quoted-price")
def update_quoted_price(job_id: str, payload: QuotedPricePayload, request: Request, db: Session = Depends(get_db)):
    """Set or update the quoted price for profitability comparison."""
    user = _require_user(request)
    _require_roles(user, {"OWNER", "ADMIN", "SUPERVISOR"}, "Forbidden: Only Owners, Admins, or Supervisors can set quoted price.")

    job = (
        db.query(models.Job)
        .filter(models.Job.job_id == job_id, models.Job.tenant_id == user["tenant_id"])
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.quoted_price = payload.quoted_price
    db.commit()
    db.refresh(job)
    return api_success({"job_id": job_id, "quoted_price": float(job.quoted_price)}, message="Quoted price updated")
