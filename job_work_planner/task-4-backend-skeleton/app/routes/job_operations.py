"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: job_operations.py
 * 
 * 1) Purpose: Defines API endpoints for job_operations.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
job_operations.py
-----------------
Asynchronous API routes for Job Operation execution, planning, and costing.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app import models, schemas
from app.database import get_async_db
from app.core.job_operations_service import (
    update_job_operation_status_async,
    plan_job_operation_service_async,
)
from app.core.auth_middleware import role_required
from app.core.audit_service import get_audit_trail_async
from app.services.costing_service import calculate_job_costs
from app.core.response_models import ApiResponse

router = APIRouter(prefix="/job-operations", tags=["Job Operations"])
logger = logging.getLogger("jobwork-backend")

def _require_user(request: Request):
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized: Missing user context.")
    return user

@router.patch("/{job_op_id}/status", response_model=ApiResponse[schemas.JobOperationResponse])
async def patch_operation_status(
    job_op_id: UUID,
    payload: schemas.JobOperationUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Updates the execution status of an operation. 
    Triggers background costing if COMPLETED.
    """
    user = _require_user(request)
    tenant_id = user["tenant_id"]
    user_id = user.get("user_id", "unknown")
    role = str(user.get("role") or "").upper()
    if role == "OPERATOR":
        assigned_machine_id = user.get("machine_id")
        operation_result = await db.execute(
            select(models.JobOperation).where(
                models.JobOperation.job_op_id == job_op_id,
                models.JobOperation.tenant_id == tenant_id,
            )
        )
        operation = operation_result.scalar_one_or_none()
        if not operation or not assigned_machine_id or str(operation.machine_id or "") != str(assigned_machine_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Operators can only update operations assigned to their machine.",
            )

    try:
        updated_op = await update_job_operation_status_async(
            db=db,
            job_op_id=job_op_id,
            tenant_id=tenant_id,
            user_id=user_id,
            new_status=payload.status,
            worker_id=payload.worker_id,
            actual_start_time=payload.actual_start_time,
            actual_end_time=payload.actual_end_time,
            quantity_completed=payload.quantity_completed,
            quantity_rejected=payload.quantity_rejected
        )

        # Trigger background costing only if COMPLETED
        if updated_op.status == "COMPLETED":
            background_tasks.add_task(calculate_job_costs, db, tenant_id, updated_op.job_id)

        return ApiResponse(
            data=schemas.JobOperationResponse.model_validate(updated_op),
            message=f"Operation {updated_op.status} successfully."
        )

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in status update")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")

@router.patch("/{job_op_id}/plan", response_model=ApiResponse[schemas.JobOperationResponse])
@role_required(["OWNER", "SUPERVISOR"])
async def patch_operation_plan(
    job_op_id: UUID,
    payload: schemas.PlanPayload, # Reuse existing or update to schema.py version
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Assigns a machine and shift to an operation.
    """
    user = _require_user(request)
    tenant_id = user["tenant_id"]

    # Simple model_validate usually works with UUIDs in payload if using Pydantic
    try:
        updated_op = await plan_job_operation_service_async(
            db=db,
            job_op_id=job_op_id,
            machine_id=payload.machine_id,
            tenant_id=tenant_id,
            shift_id=payload.shift_id,
            planned_start_date=payload.planned_start_date,
            planned_end_date=payload.planned_end_date
        )
        return ApiResponse(data=schemas.JobOperationResponse.model_validate(updated_op))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{job_op_id}", response_model=ApiResponse[schemas.JobOperationResponse])
async def get_operation(
    job_op_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    user = _require_user(request)
    tenant_id = user["tenant_id"]

    query = select(models.JobOperation).where(
        models.JobOperation.job_op_id == job_op_id,
        models.JobOperation.tenant_id == tenant_id
    )
    result = await db.execute(query)
    operation = result.scalar_one_or_none()

    if not operation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found.")

    return ApiResponse(data=schemas.JobOperationResponse.model_validate(operation))


@router.get("/{job_op_id}/audit", response_model=ApiResponse[List[dict]])
@role_required(["OWNER", "SUPERVISOR"])
async def get_operation_audit(
    job_op_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Returns the audit history for a specific operation.
    Only accessible by SUPERVISORS and OWNERS.
    """
    user = _require_user(request)
    tenant_id = user["tenant_id"]

    # Retrieve history using the audit service
    history = await get_audit_trail_async(
        db=db,
        tenant_id=tenant_id,
        entity_type="JOB_OPERATION",
        entity_id=str(job_op_id)
    )

    return ApiResponse(
        data=history,
        message=f"Retrieved {len(history)} audit events."
    )
