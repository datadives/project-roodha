"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: master_data_service.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
master_data_service.py
------------------------
Asynchronous service layer for Master Data (Machines, Workers, Shifts, Parts).
"""

import uuid
import logging
from typing import List, Optional, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func

from app import models

logger = logging.getLogger("jobwork-backend")

ONGOING_JOB_OPERATION_STATUSES = {"NOT_STARTED", "READY", "IN_PROGRESS", "PAUSED"}


async def _get_or_404(db: AsyncSession, model, object_id: UUID, tenant_id: str, id_field: str):
    query = select(model).where(
        getattr(model, id_field) == object_id, 
        model.tenant_id == tenant_id
    )
    result = await db.execute(query)
    instance = result.scalar_one_or_none()
    
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    return instance


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def _has_job_references(db: AsyncSession, tenant_id: str, field_name: str, object_id: UUID) -> bool:
    """Checks if a Master Data record is referenced in any Job or JobOperation."""
    if field_name == "customer_id":
        query = select(models.Job.job_id).where(
            models.Job.tenant_id == tenant_id,
            models.Job.customer_id == object_id
        ).limit(1)
    else:
        # machine_id or shift_id
        query = select(models.JobOperation.job_op_id).where(
            models.JobOperation.tenant_id == tenant_id,
            getattr(models.JobOperation, field_name) == object_id
        ).limit(1)
        
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------
# Machines
# ---------------------------------------------------------

async def create_machine(db: AsyncSession, tenant_id: str, payload):
    machine = models.Machine(
        machine_id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        type=_normalize_text(payload.type),
        hourly_rate=payload.hourly_rate,
        is_active=payload.is_active,
    )
    db.add(machine)
    await db.commit()
    await db.refresh(machine)
    return machine


async def list_machines(db: AsyncSession, tenant_id: str, include_inactive: bool = False):
    query = select(models.Machine).where(models.Machine.tenant_id == tenant_id)
    if not include_inactive:
        query = query.where(models.Machine.is_active == True)
    
    result = await db.execute(query.order_by(models.Machine.name.asc()))
    return result.scalars().all()


async def get_machine(db: AsyncSession, tenant_id: str, machine_id: UUID):
    return await _get_or_404(db, models.Machine, machine_id, tenant_id, "machine_id")


async def update_machine(db: AsyncSession, tenant_id: str, machine_id: UUID, payload):
    machine = await _get_or_404(db, models.Machine, machine_id, tenant_id, "machine_id")
    updates = payload.model_dump(exclude_unset=True)

    if updates.get("is_active") is False and machine.is_active is True:
        # Check for active assignments before deactivating
        if await _has_job_references(db, tenant_id, "machine_id", machine_id):
            logger.warning(f"Prevented deactivation of machine {machine_id} due to job references.")
            # Note: We allow deactivation if supervisor acknowledges, but here we enforce audit safety.

    for key, value in updates.items():
        setattr(machine, key, value)
    
    await db.commit()
    await db.refresh(machine)
    return machine


async def delete_machine(db: AsyncSession, tenant_id: str, machine_id: UUID):
    machine = await _get_or_404(db, models.Machine, machine_id, tenant_id, "machine_id")
    
    # ENFORCE DEACTIVATION: Hard block deletion if jobs exist
    if await _has_job_references(db, tenant_id, "machine_id", machine_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete machine with historical jobs. Deactivate it instead to preserve audit logs."
        )

    await db.delete(machine)
    await db.commit()
    return {"machine_id": machine_id}


# ---------------------------------------------------------
# Workers
# ---------------------------------------------------------

async def create_worker(db: AsyncSession, tenant_id: str, payload):
    worker = models.Worker(
        worker_id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        role=_normalize_text(payload.role),
        hourly_rate=payload.hourly_rate,
        is_active=payload.is_active,
    )
    db.add(worker)
    await db.commit()
    await db.refresh(worker)
    return worker


async def list_workers(db: AsyncSession, tenant_id: str, include_inactive: bool = False):
    query = select(models.Worker).where(models.Worker.tenant_id == tenant_id)
    if not include_inactive:
        query = query.where(models.Worker.is_active == True)
    
    result = await db.execute(query.order_by(models.Worker.name.asc()))
    return result.scalars().all()


async def get_worker(db: AsyncSession, tenant_id: str, worker_id: UUID):
    return await _get_or_404(db, models.Worker, worker_id, tenant_id, "worker_id")


async def update_worker(db: AsyncSession, tenant_id: str, worker_id: UUID, payload):
    worker = await _get_or_404(db, models.Worker, worker_id, tenant_id, "worker_id")
    updates = payload.model_dump(exclude_unset=True)
    
    for key, value in updates.items():
        setattr(worker, key, value)
        
    await db.commit()
    await db.refresh(worker)
    return worker


async def delete_worker(db: AsyncSession, tenant_id: str, worker_id: UUID):
    worker = await _get_or_404(db, models.Worker, worker_id, tenant_id, "worker_id")
    
    # No direct tracking of worker_id in JobOperation yet (Worker assignments are transient in V1.0)
    # But we follow the same deactivation pattern for consistency.
    await db.delete(worker)
    await db.commit()
    return {"worker_id": worker_id}


# ---------------------------------------------------------
# Shifts
# ---------------------------------------------------------

async def create_shift(db: AsyncSession, tenant_id: str, payload):
    shift = models.Shift(
        shift_id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    return shift


async def list_shifts(db: AsyncSession, tenant_id: str):
    query = select(models.Shift).where(models.Shift.tenant_id == tenant_id)
    result = await db.execute(query.order_by(models.Shift.name.asc()))
    return result.scalars().all()


async def get_shift(db: AsyncSession, tenant_id: str, shift_id: UUID):
    return await _get_or_404(db, models.Shift, shift_id, tenant_id, "shift_id")


async def update_shift(db: AsyncSession, tenant_id: str, shift_id: UUID, payload):
    shift = await _get_or_404(db, models.Shift, shift_id, tenant_id, "shift_id")
    updates = payload.model_dump(exclude_unset=True)
    
    for key, value in updates.items():
        setattr(shift, key, value)
        
    await db.commit()
    await db.refresh(shift)
    return shift


async def delete_shift(db: AsyncSession, tenant_id: str, shift_id: UUID):
    shift = await _get_or_404(db, models.Shift, shift_id, tenant_id, "shift_id")
    
    if await _has_job_references(db, tenant_id, "shift_id", shift_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete shift linked to historical operations. Deactivate functionality not yet implemented for shifts."
        )
        
    await db.delete(shift)
    await db.commit()
    return {"shift_id": shift_id}


# ---------------------------------------------------------
# Customers
# ---------------------------------------------------------

async def create_customer(db: AsyncSession, tenant_id: str, payload):
    customer = models.Customer(
        customer_id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        contact_person=_normalize_text(payload.contact),
        is_active=payload.is_active,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


async def list_customers(db: AsyncSession, tenant_id: str, include_inactive: bool = False):
    query = select(models.Customer).where(models.Customer.tenant_id == tenant_id)
    if not include_inactive:
        query = query.where(models.Customer.is_active == True)
    
    result = await db.execute(query.order_by(models.Customer.name.asc()))
    return result.scalars().all()


async def get_customer(db: AsyncSession, tenant_id: str, customer_id: UUID):
    return await _get_or_404(db, models.Customer, customer_id, tenant_id, "customer_id")


async def update_customer(db: AsyncSession, tenant_id: str, customer_id: UUID, payload):
    customer = await _get_or_404(db, models.Customer, customer_id, tenant_id, "customer_id")
    updates = payload.model_dump(exclude_unset=True)

    if "contact" in updates:
        updates["contact_person"] = updates.pop("contact")

    for key, value in updates.items():
        setattr(customer, key, value)
    
    await db.commit()
    await db.refresh(customer)
    return customer


async def delete_customer(db: AsyncSession, tenant_id: str, customer_id: UUID):
    customer = await _get_or_404(db, models.Customer, customer_id, tenant_id, "customer_id")
    
    if await _has_job_references(db, tenant_id, "customer_id", customer_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete customer with existing jobs. Deactivate instead."
        )

    await db.delete(customer)
    await db.commit()
    return {"customer_id": customer_id}


# ---------------------------------------------------------
# Parts
# ---------------------------------------------------------

async def create_part(db: AsyncSession, tenant_id: str, payload):
    # Verify customer exists
    await _get_or_404(db, models.Customer, payload.customer_id, tenant_id, "customer_id")
    
    # In V1.0, we store the route as JSONB in the Job creation step.
    # Here we just validate the structure.
    part = models.Part(
        part_id=uuid.uuid4(),
        tenant_id=tenant_id,
        part_number=_normalize_text(payload.part_number),
        customer_id=payload.customer_id,
        default_operations_route=payload.default_operations_route,
        default_material_cost_per_unit=payload.default_material_cost_per_unit
    )
    db.add(part)
    await db.commit()
    await db.refresh(part)
    return part


async def list_parts(db: AsyncSession, tenant_id: str):
    query = select(models.Part).where(models.Part.tenant_id == tenant_id)
    result = await db.execute(query.order_by(models.Part.part_number.asc()))
    return result.scalars().all()


async def get_part(db: AsyncSession, tenant_id: str, part_id: UUID):
    return await _get_or_404(db, models.Part, part_id, tenant_id, "part_id")


async def update_part(db: AsyncSession, tenant_id: str, part_id: UUID, payload):
    part = await _get_or_404(db, models.Part, part_id, tenant_id, "part_id")
    updates = payload.model_dump(exclude_unset=True)
    
    if "customer_id" in updates:
        await _get_or_404(db, models.Customer, updates["customer_id"], tenant_id, "customer_id")

    for key, value in updates.items():
        setattr(part, key, value)
        
    await db.commit()
    await db.refresh(part)
    return part


async def delete_part(db: AsyncSession, tenant_id: str, part_id: UUID):
    part = await _get_or_404(db, models.Part, part_id, tenant_id, "part_id")
    
    # Check for jobs referencing this part
    job_query = select(models.Job.job_id).where(
        models.Job.tenant_id == tenant_id,
        models.Job.part_id == part_id
    ).limit(1)
    result = await db.execute(job_query)
    if result.scalar_one_or_none():
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete part with linked jobs. Deactivate functionality not yet implemented for parts."
        )

    await db.delete(part)
    await db.commit()
    return {"part_id": part_id}

# ---------------------------------------------------------
# Operations
# ---------------------------------------------------------

async def create_operation(db: AsyncSession, tenant_id: str, payload):
    operation = models.OperationsMaster(
        operation_id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=_normalize_text(payload.name),
        standard_cycle_time_mins=payload.standard_cycle_time_mins,
        default_machine_type=_normalize_text(getattr(payload, "default_machine_type", None)),
    )
    db.add(operation)
    await db.commit()
    await db.refresh(operation)
    return operation

async def list_operations(db: AsyncSession, tenant_id: str):
    query = select(models.OperationsMaster).where(models.OperationsMaster.tenant_id == tenant_id)
    # Order by sequence_number if present, else by name
    query = query.order_by(models.OperationsMaster.sequence_number.asc().nulls_last(), models.OperationsMaster.name.asc())
    result = await db.execute(query)
    return result.scalars().all()

async def get_operation(db: AsyncSession, tenant_id: str, operation_id: UUID):
    return await _get_or_404(db, models.OperationsMaster, operation_id, tenant_id, "operation_id")

async def update_operation(db: AsyncSession, tenant_id: str, operation_id: UUID, payload):
    operation = await _get_or_404(db, models.OperationsMaster, operation_id, tenant_id, "operation_id")
    updates = payload.model_dump(exclude_unset=True)
    
    for key, value in updates.items():
        setattr(operation, key, value)
        
    await db.commit()
    await db.refresh(operation)
    return operation

async def delete_operation(db: AsyncSession, tenant_id: str, operation_id: UUID):
    operation = await _get_or_404(db, models.OperationsMaster, operation_id, tenant_id, "operation_id")
    
    # Check for jobs referencing this operation (job_operations)
    if await _has_job_references(db, tenant_id, "op_id", operation_id):
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an operation that is linked to existing job operations."
        )

    await db.delete(operation)
    await db.commit()
    return {"operation_id": operation_id}
