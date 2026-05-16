"""
PROJECT ROODHA - JOBS MANAGEMENT
FILE: jobs.py
PURPOSE: Implements RESTful endpoints for Job creation, lifecycle tracking, and operation routing.
         Includes transactional job initialization and role-based access control (RBAC).
"""

import logging
from datetime import datetime
from uuid import UUID, uuid4
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app import models
from app.database import get_async_db
from app.schemas.jobs import JobCreate, JobUpdate, JobResponse, JobOperationResponse, JobWithOperations
from app.core.auth_middleware import role_required
from app.core.tenant_context import tenant_id_context, user_id_context
from app.core.response_models import ApiResponse
from app.core.proactive_delay_guard import calculate_alert_priority
from app.core.event_service import record_event
from app.core.notification_service import create_notification

router = APIRouter(prefix="/jobs", tags=["Jobs"])
logger = logging.getLogger("jobwork-backend")

# ---------------------------------------------------------
# --- UTILITIES & SERIALIZATION ---
# ---------------------------------------------------------

def serialize_job_response(job: models.Job) -> JobResponse:
    """Injects dynamic alert priority based on real-time due date assessment."""
    response = JobResponse.model_validate(job)
    response.alert_priority = calculate_alert_priority(job.due_date)
    return response

def _get_context(request: Request):
    """
    Extract and validate tenant/user context from JWT middleware state.
    Essential for ensuring data isolation at the route level.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User context missing")

    tenant_id = user["tenant_id"]
    user_id = user["user_id"]
    role = str(user.get("role") or "").upper()

    # Enforce tenant isolation in contextvars for Audit Mixin
    tenant_id_context.set(tenant_id)
    user_id_context.set(user_id)

    return tenant_id, user_id, role


async def _get_or_create_default_operation(db: AsyncSession, tenant_id: str) -> models.OperationsMaster:
    """Ensure V1 jobs always have one routable operation for kanban and analytics."""
    result = await db.execute(
        select(models.OperationsMaster)
        .where(models.OperationsMaster.tenant_id == tenant_id)
        .order_by(
            models.OperationsMaster.sequence_number.asc().nulls_last(),
            models.OperationsMaster.name.asc(),
        )
        .limit(1)
    )
    operation = result.scalar_one_or_none()
    if operation:
        return operation

    operation = models.OperationsMaster(
        tenant_id=tenant_id,
        name="General Operation",
        description="Default V1 route created automatically so new jobs appear in planning and analytics.",
        standard_cycle_time_mins=30,
        sequence_number=1,
    )
    db.add(operation)
    await db.flush()
    return operation


async def _get_default_machine_id(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(models.Machine.machine_id)
        .where(models.Machine.tenant_id == tenant_id, models.Machine.is_active.is_(True))
        .order_by(models.Machine.name.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _route_operation_id(op_data: dict) -> str | None:
    return op_data.get("operation_id") or op_data.get("op_id") or op_data.get("id")


def _parse_uuid_or_none(value) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _extract_route_operation_ids(payload: JobUpdate) -> list[UUID] | None:
    explicit_ids = payload.operation_ids or payload.route_operation_ids
    if explicit_ids is not None:
        return [UUID(str(item)) for item in explicit_ids]

    if payload.operations is None:
        return None

    operation_ids: list[UUID] = []
    for item in payload.operations:
        if isinstance(item, dict):
            raw_id = item.get("job_operation_id") or item.get("job_op_id") or item.get("id")
        else:
            raw_id = item
        parsed = _parse_uuid_or_none(raw_id)
        if not parsed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Route operations must reference existing job operation ids.",
            )
        operation_ids.append(parsed)
    return operation_ids


async def _apply_job_route_operation_update(
    db: AsyncSession,
    tenant_id: str,
    job_id: UUID,
    requested_operation_ids: list[UUID],
) -> None:
    result = await db.execute(
        select(models.JobOperation)
        .where(
            models.JobOperation.tenant_id == tenant_id,
            models.JobOperation.job_id == job_id,
        )
        .with_for_update()
    )
    existing_operations = result.scalars().all()
    existing_by_id = {operation.job_op_id: operation for operation in existing_operations}
    requested_ids = set(requested_operation_ids)

    unknown_ids = requested_ids - set(existing_by_id)
    if unknown_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route update contains operations that do not belong to this job.",
        )

    removed_operations = [
        operation for operation in existing_operations
        if operation.job_op_id not in requested_ids
    ]
    locked_statuses = {models.OperationStatus.IN_PROGRESS, models.OperationStatus.COMPLETED}
    locked_removed = [
        operation for operation in removed_operations
        if operation.status in locked_statuses
    ]
    if locked_removed:
        locked_steps = ", ".join(str(operation.sequence_number) for operation in locked_removed)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot remove operation(s) already started or completed: step {locked_steps}.",
        )

    for operation in removed_operations:
        await db.delete(operation)
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _normalize_operation_key(value: str | None) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _normalize_custom_field_key(value: str | UUID) -> str:
    return str(value or "").strip().lower()


async def _resolve_job_custom_field_values(
    db: AsyncSession,
    tenant_id: str,
    values: dict[str, str] | None,
) -> list[tuple[models.CustomField, str]]:
    provided = {
        _normalize_custom_field_key(key): str(value).strip()
        for key, value in (values or {}).items()
        if value is not None
    }
    result = await db.execute(
        select(models.CustomField).where(
            models.CustomField.tenant_id == tenant_id,
            models.CustomField.entity_type == "JOB",
        )
    )
    fields = result.scalars().all()
    resolved: list[tuple[models.CustomField, str]] = []
    for field in fields:
        field_value = provided.get(_normalize_custom_field_key(field.field_id))
        if field_value is None:
            field_value = provided.get(_normalize_custom_field_key(field.field_name))

        if field.is_required and not field_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Custom field '{field.field_name}' is required",
            )

        if field_value is None:
            continue

        if str(field.field_type or "").upper() == "DROPDOWN":
            allowed_options = {str(option).strip() for option in (field.options_json or [])}
            if field_value not in allowed_options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid value for '{field.field_name}'. Allowed values: {', '.join(sorted(allowed_options))}",
                )
        resolved.append((field, field_value))
    return resolved


async def _resolve_route_operation(
    db: AsyncSession,
    tenant_id: str,
    op_data: dict,
    sequence_number: int,
) -> models.OperationsMaster:
    raw_id = _route_operation_id(op_data)
    operation_uuid = _parse_uuid_or_none(raw_id)
    if operation_uuid:
        result = await db.execute(
            select(models.OperationsMaster).where(
                models.OperationsMaster.tenant_id == tenant_id,
                models.OperationsMaster.operation_id == operation_uuid,
            )
        )
        operation = result.scalar_one_or_none()
        if operation:
            return operation

    operation_name = (
        op_data.get("operation")
        or op_data.get("operation_name")
        or op_data.get("name")
        or raw_id
        or f"Operation {sequence_number}"
    )
    wanted_key = _normalize_operation_key(operation_name)
    result = await db.execute(
        select(models.OperationsMaster).where(models.OperationsMaster.tenant_id == tenant_id)
    )
    for operation in result.scalars().all():
        if _normalize_operation_key(operation.name) == wanted_key:
            return operation

    operation = models.OperationsMaster(
        tenant_id=tenant_id,
        name=str(operation_name).strip() or f"Operation {sequence_number}",
        description="Created from part route during job launch.",
        standard_cycle_time_mins=30,
        default_machine_type=op_data.get("default_machine_type") or op_data.get("machine_type"),
        sequence_number=sequence_number,
    )
    db.add(operation)
    await db.flush()
    return operation

# ---------------------------------------------------------
# --- JOB LIFECYCLE ENDPOINTS ---
# ---------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[JobWithOperations])
@role_required(["OWNER", "SUPERVISOR"])
async def create_job(
    payload: JobCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Creates a new industrial job and automatically expands the manufacturing routing
    based on the saved Part Master template.
    """
    # 1. Context Injection from JWT
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User context missing")
    
    tenant_id = user["tenant_id"]
    user_id = user["user_id"]
    
    tenant_id_context.set(tenant_id)
    user_id_context.set(user_id)

    try:
        # Fetch Part to get route
        part_query = select(models.Part).where(
            models.Part.part_id == payload.part_id,
            models.Part.tenant_id == tenant_id
        )
        result = await db.execute(part_query)
        part = result.scalar_one_or_none()
        
        if not part:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")

        custom_field_values = await _resolve_job_custom_field_values(db, tenant_id, payload.custom_fields)

        job = models.Job(
            job_id=uuid4(),
            tenant_id=tenant_id,
            customer_id=payload.customer_id,
            part_id=payload.part_id,
            job_number=payload.job_number,
            quantity=payload.quantity,
            due_date=payload.due_date,
            priority=payload.priority,
            status=models.JobStatus.NOT_STARTED,
            tags_json=payload.tags or [],
        )
        db.add(job)
        await db.flush()
        for field, field_value in custom_field_values:
            db.add(
                models.CustomFieldValue(
                    value_id=uuid4(),
                    tenant_id=tenant_id,
                    field_id=field.field_id,
                    entity_id=job.job_id,
                    field_value=field_value,
                    value_text=field_value,
                )
            )
        await record_event(
            db,
            tenant_id=tenant_id,
            event_type="JOB_CREATED",
            entity_type="JOB",
            entity_id=str(job.job_id),
            payload={"job_number": job.job_number, "priority": payload.priority},
        )

        ops_route = part.default_operations_route or []
        job_operations = []
        
        if not ops_route:
            logger.warning(
                "Part %s has no default operations route. Creating a V1 fallback operation for tenant %s.",
                part.part_id,
                tenant_id,
            )
            operation = await _get_or_create_default_operation(db, tenant_id)
            machine_id = await _get_default_machine_id(db, tenant_id)
            ops_route = [
                {
                    "operation_id": str(operation.operation_id),
                    "sequence_number": 1,
                    "machine_id": str(machine_id) if machine_id else None,
                }
            ]

        for idx, op_data in enumerate(ops_route):
            sequence_number = op_data.get("sequence_number") or op_data.get("sequence") or idx + 1
            operation = await _resolve_route_operation(db, tenant_id, op_data, sequence_number)
                  
            job_op = models.JobOperation(
                job_op_id=uuid4(),
                tenant_id=tenant_id,
                job_id=job.job_id,
                op_id=operation.operation_id,
                sequence_number=sequence_number,
                status=models.OperationStatus.NOT_STARTED,
                machine_id=_parse_uuid_or_none(op_data.get("machine_id")),
            )
            db.add(job_op)
            job_operations.append(job_op)
        await db.commit()
        if str(payload.priority or "").upper() == "HIGH":
            await create_notification(
                db=db,
                tenant_id=tenant_id,
                user_id=None,
                notif_type="HIGH_PRIORITY_JOB",
                title="High priority job created",
                message=f"Job {job.job_number} was created with high priority.",
                entity_ref=job.job_number,
                entity_type="JOB",
                entity_id=str(job.job_id),
            )
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        logger.exception("Job creation failed for tenant %s", tenant_id)
        raise

    await db.refresh(job)
    for op in job_operations:
        await db.refresh(op)

    return ApiResponse(
        data=JobWithOperations(
            **job.__dict__,
            operations=[op for op in job_operations]
        ),
        message="Job created successfully with expanded operations route"
    )

@router.get("", response_model=ApiResponse[List[JobResponse]])
async def list_jobs(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    status_filter: str = None,
    priority: str = None,
):
    """Return all jobs for the authenticated tenant, with optional status/priority filters."""
    tenant_id, _uid, role = _get_context(request)
    assigned_machine_id = getattr(request.state, "user", {}).get("machine_id")

    query = (
        select(models.Job)
        .where(models.Job.tenant_id == tenant_id)
        .order_by(models.Job.created_at.desc())
    )

    if role == "OPERATOR":
        if not assigned_machine_id:
            return ApiResponse(data=[], message="No machine assignment found for operator")
        assigned_job_ids = select(models.JobOperation.job_id).where(
            models.JobOperation.tenant_id == tenant_id,
            models.JobOperation.machine_id == UUID(str(assigned_machine_id)),
        )
        query = query.where(models.Job.job_id.in_(assigned_job_ids))

    if status_filter:
        try:
            query = query.where(models.Job.status == models.JobStatus(status_filter.upper()))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status value: '{status_filter}'"
            )

    if priority:
        query = query.where(models.Job.priority == priority.upper())

    result = await db.execute(query)
    jobs = result.scalars().all()

    return ApiResponse(
        data=[serialize_job_response(j) for j in jobs],
        message=f"{len(jobs)} job(s) found"
    )

@router.get("/{job_id}", response_model=ApiResponse[JobResponse])
async def get_job(
    job_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Return a single job by ID, scoped to the authenticated tenant."""
    tenant_id, _uid, role = _get_context(request)

    result = await db.execute(
        select(models.Job).where(
            models.Job.job_id == job_id,
            models.Job.tenant_id == tenant_id
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if role == "OPERATOR":
        assigned_machine_id = getattr(request.state, "user", {}).get("machine_id")
        if not assigned_machine_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator machine assignment missing")
        op_result = await db.execute(
            select(models.JobOperation.job_op_id).where(
                models.JobOperation.job_id == job_id,
                models.JobOperation.tenant_id == tenant_id,
                models.JobOperation.machine_id == UUID(str(assigned_machine_id)),
            )
        )
        if not op_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Job is not assigned to this operator machine")

    return ApiResponse(data=serialize_job_response(job))

@router.patch("/{job_id}", response_model=ApiResponse[JobResponse])
@role_required(["OWNER", "SUPERVISOR"])
async def update_job(
    job_id: UUID,
    payload: JobUpdate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update mutable job metadata (due_date, priority, quantity).
    Restricted to privileged roles (OWNER/SUPERVISOR).
    """
    tenant_id, _uid, _role = _get_context(request)

    result = await db.execute(
        select(models.Job)
        .where(
            models.Job.job_id == job_id,
            models.Job.tenant_id == tenant_id
        )
        .with_for_update()
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    requested_route_operation_ids = _extract_route_operation_ids(payload)
    if requested_route_operation_ids is not None:
        await _apply_job_route_operation_update(
            db=db,
            tenant_id=tenant_id,
            job_id=job_id,
            requested_operation_ids=requested_route_operation_ids,
        )

    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("operation_ids", None)
    update_data.pop("route_operation_ids", None)
    update_data.pop("operations", None)
    update_data.pop("remarks", None)

    for field, value in update_data.items():
        if hasattr(job, field):
            setattr(job, field, value)

    await db.commit()
    await db.refresh(job)

    logger.info("Job %s updated by user %s", job_id, _uid)
    return ApiResponse(data=serialize_job_response(job), message="Job updated successfully")

@router.get("/{job_id}/operations", response_model=ApiResponse[List[JobOperationResponse]])
async def list_job_operations(
    job_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Return the full manufacturing route for a given job.
    Provides visibility into completed, active, and pending stages.
    """
    tenant_id, _uid, _role = _get_context(request)

    job_check = await db.execute(
        select(models.Job.job_id).where(
            models.Job.job_id == job_id,
            models.Job.tenant_id == tenant_id
        )
    )
    if not job_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    ops_result = await db.execute(
        select(models.JobOperation)
        .where(
            models.JobOperation.job_id == job_id,
            models.JobOperation.tenant_id == tenant_id
        )
        .order_by(models.JobOperation.sequence_number)
    )
    operations = ops_result.scalars().all()

    return ApiResponse(
        data=[JobOperationResponse.model_validate(op) for op in operations],
        message=f"{len(operations)} operation(s) in routing"
    )
