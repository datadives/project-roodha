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
from sqlalchemy import select, func

from app import models
from app.database import get_async_db
from app.schemas.jobs import JobCreate, JobUpdate, JobResponse, JobOperationResponse, JobWithOperations
from app.core.auth_middleware import role_required
from app.core.tenant_context import tenant_id_context, user_id_context
from app.core.response_models import ApiResponse
from app.core.proactive_delay_guard import calculate_alert_priority

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

    async with db.begin():
        # Fetch Part to get route
        part_query = select(models.Part).where(
            models.Part.part_id == payload.part_id,
            models.Part.tenant_id == tenant_id
        )
        result = await db.execute(part_query)
        part = result.scalar_one_or_none()
        
        if not part:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")

        job = models.Job(
            job_id=uuid4(),
            tenant_id=tenant_id,
            customer_id=payload.customer_id,
            part_id=payload.part_id,
            quantity=payload.quantity,
            due_date=payload.due_date,
            priority=payload.priority,
            status=models.JobStatus.NOT_STARTED,
        )
        db.add(job)

        # --- FIX: Handle None/empty operations route safely ---
        ops_route = part.default_operations_route or []
        job_operations = []
        
        if not ops_route:
            logger.warning(f"Part {part.part_id} has no default operations route. No job operations will be created.")

        for idx, op_data in enumerate(ops_route):
            op_id_raw = op_data.get("id")
            if not op_id_raw:
                continue
                
            job_op = models.JobOperation(
                job_op_id=uuid4(),
                tenant_id=tenant_id,
                job_id=job.job_id,
                op_id=UUID(op_id_raw),
                sequence_number=op_data.get("sequence_number", idx + 1),
                status=models.OperationStatus.NOT_STARTED,
                machine_id=UUID(op_data["machine_id"]) if op_data.get("machine_id") else None,
            )
            db.add(job_op)
            job_operations.append(job_op)

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

    update_data = payload.model_dump(exclude_unset=True)
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
