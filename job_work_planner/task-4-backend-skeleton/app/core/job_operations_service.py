"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: job_operations_service.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
job_operations_service.py
-------------------------
Asynchronous Business Logic for Job Operations.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import models
from app.core.audit_service import log_audit_event_async

logger = logging.getLogger("jobwork-backend")

class CapacityConflictError(Exception):
    def __init__(self, message, clashes=None):
        super().__init__(message)
        self.clashes = clashes or []
        self.message = message

ALLOWED_OPERATION_STATUSES = {
    "NOT_STARTED",
    "PLANNED",
    "READY",
    "IN_PROGRESS",
    "PAUSED",
    "COMPLETED",
    "CANCELLED",
}

def _serialize_job_operation(operation: models.JobOperation) -> dict:
    return {
        "job_op_id": str(operation.job_op_id),
        "tenant_id": operation.tenant_id,
        "job_id": str(operation.job_id),
        "op_id": str(operation.op_id),
        "machine_id": str(operation.machine_id) if operation.machine_id else None,
        "worker_id": str(operation.worker_id) if hasattr(operation, 'worker_id') and operation.worker_id else None,
        "shift_id": str(operation.shift_id) if operation.shift_id else None,
        "sequence_number": operation.sequence_number,
        "status": operation.status,
        "actual_start_time": operation.actual_start_time.isoformat() if operation.actual_start_time else None,
        "actual_end_time": operation.actual_end_time.isoformat() if operation.actual_end_time else None,
        "planned_start_date": operation.planned_start_date.isoformat() if operation.planned_start_date else None,
        "planned_end_date": operation.planned_end_date.isoformat() if operation.planned_end_date else None,
    }

async def _sync_parent_job_status(db: AsyncSession, tenant_id: str, job_id: UUID):
    # Fetch job
    job_query = select(models.Job).where(models.Job.job_id == job_id, models.Job.tenant_id == tenant_id)
    result = await db.execute(job_query)
    job = result.scalar_one_or_none()
    if not job:
        return

    # Fetch all operations
    ops_query = select(models.JobOperation.status).where(
        models.JobOperation.job_id == job_id,
        models.JobOperation.tenant_id == tenant_id
    )
    res = await db.execute(ops_query)
    op_statuses = {str(s).split('.')[-1].upper() for (s,) in res.all()}

    if not op_statuses:
        return

    if op_statuses == {"COMPLETED"}:
        job.status = models.JobStatus.COMPLETED
    elif any(s in {"IN_PROGRESS", "PAUSED", "COMPLETED"} for s in op_statuses):
        job.status = models.JobStatus.IN_PROGRESS
    else:
        job.status = models.JobStatus.NOT_STARTED

async def update_job_operation_status_async(
    db: AsyncSession,
    job_op_id: UUID,
    tenant_id: str,
    user_id: str,
    new_status: str,
    **kwargs
):
    # 0. Concurrency Protection: Lock the row for update
    query = select(models.JobOperation).where(
        models.JobOperation.job_op_id == job_op_id,
        models.JobOperation.tenant_id == tenant_id
    ).with_for_update() # Requirement C: Race condition prevention
    
    result = await db.execute(query)
    operation = result.scalar_one_or_none()

    if not operation:
        raise ValueError("Operation not found")

    before_state = _serialize_job_operation(operation)
    if not new_status:
        raise ValueError("Operation status is required")
    normalized_status = new_status.strip().upper()
    if normalized_status not in ALLOWED_OPERATION_STATUSES:
        raise ValueError(f"Invalid operation status: {normalized_status}")
    
    # 1. Update Basic Fields
    operation.status = normalized_status
    if "worker_id" in kwargs and kwargs["worker_id"]:
        operation.worker_id = kwargs["worker_id"]

    # 2. Hard Business Logic Validations (Requirement 3.B & 3.C)
    
    # 2.1 Sequence Integrity (Requirement 3.C)
    # Prevent COMPLETING an operation if previous operations are not COMPLETED
    if normalized_status in {"IN_PROGRESS", "COMPLETED"}:
        sequence_query = select(models.JobOperation).where(
            models.JobOperation.job_id == operation.job_id,
            models.JobOperation.tenant_id == tenant_id,
            models.JobOperation.sequence_number < operation.sequence_number,
            models.JobOperation.status != "COMPLETED"
        ).with_for_update()
        sequence_result = await db.execute(sequence_query)
        uncompleted_previous = sequence_result.scalars().all()
        if uncompleted_previous:
            prev_seqs = [op.sequence_number for op in uncompleted_previous]
            raise ValueError(f"Sequence Integrity Violation: Cannot move operation #{operation.sequence_number} to {normalized_status} while previous operations ({prev_seqs}) are incomplete.")

    # 2.2 Exclusivity (Requirement 3.C)
    if normalized_status == "IN_PROGRESS":
        # Check if any OTHER operation for this job is already IN_PROGRESS
        exclusivity_query = select(models.JobOperation).where(
            models.JobOperation.job_id == operation.job_id,
            models.JobOperation.tenant_id == tenant_id,
            models.JobOperation.status == "IN_PROGRESS",
            models.JobOperation.job_op_id != job_op_id
        )
        exclusivity_result = await db.execute(exclusivity_query)
        if exclusivity_result.scalar_one_or_none():
            raise ValueError("Another operation for this job is already IN_PROGRESS. Only one active operation allowed.")
        
        if not operation.actual_start_time:
            operation.actual_start_time = kwargs.get("actual_start_time", datetime.utcnow())

    elif normalized_status == "COMPLETED":
        # Validate quantity (Requirement 3.B)
        q_completed = kwargs.get("quantity_completed", operation.quantity_completed or 0)
        q_rejected = kwargs.get("quantity_rejected", operation.quantity_rejected or 0)
        
        job_query = select(models.Job.quantity).where(models.Job.job_id == operation.job_id)
        job_res = await db.execute(job_query)
        job_qty = job_res.scalar() or 0
        
        if (q_completed + q_rejected) > job_qty:
            raise ValueError(f"Quantity reported ({q_completed + q_rejected}) exceeds total job quantity ({job_qty}).")

        operation.actual_end_time = kwargs.get("actual_end_time", datetime.utcnow())
        if not operation.actual_start_time:
            operation.actual_start_time = operation.actual_end_time # Fallback

    # 3. Handle Quantities
    if "quantity_completed" in kwargs:
        operation.quantity_completed = kwargs["quantity_completed"]
    if "quantity_rejected" in kwargs:
        operation.quantity_rejected = kwargs["quantity_rejected"]

    # 4. Sync Job Status
    await _sync_parent_job_status(db, tenant_id, operation.job_id)

    await db.commit()
    await db.refresh(operation)

    # 5. Audit
    await log_audit_event_async(
        db=db,
        tenant_id=tenant_id,
        entity_type="JOB_OPERATION",
        entity_id=str(job_op_id),
        action="STATUS_CHANGED",
        user_id=user_id,
        before=before_state,
        after=_serialize_job_operation(operation),
    )

    return operation

async def plan_job_operation_service_async(
    db: AsyncSession,
    job_op_id: UUID,
    machine_id: UUID,
    tenant_id: str,
    shift_id: Optional[UUID] = None,
    planned_start_date: Optional[datetime] = None,
    planned_end_date: Optional[datetime] = None,
    **kwargs
):
    # Fetch operation
    query = select(models.JobOperation).where(
        models.JobOperation.job_op_id == job_op_id,
        models.JobOperation.tenant_id == tenant_id
    )
    result = await db.execute(query)
    operation = result.scalar_one_or_none()
    if not operation:
        raise ValueError("Operation not found")

    # Update Planning fields
    operation.machine_id = machine_id
    operation.shift_id = shift_id
    operation.planned_start_date = planned_start_date
    operation.planned_end_date = planned_end_date

    await db.commit()
    await db.refresh(operation)

    # Audit
    await log_audit_event_async(
        db=db,
        tenant_id=tenant_id,
        entity_type="JOB_OPERATION",
        entity_id=str(job_op_id),
        action="PLANNED",
        user_id=kwargs.get("user_id", "system"),
        after=_serialize_job_operation(operation),
    )

    return operation
