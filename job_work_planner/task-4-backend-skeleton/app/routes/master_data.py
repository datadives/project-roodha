"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: master_data.py
 * 
 * 1) Purpose: Defines API endpoints for master_data.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
master_data.py
---------------
Asynchronous API routes for Master Data management.
"""

import logging
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import master_data_service as service
from app.database import get_async_db
from app.core.auth_middleware import role_required
from app.core.tenant_context import tenant_id_context
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    MachineCreate,
    MachineUpdate,
    MachineResponse,
    ShiftCreate,
    ShiftUpdate,
    ShiftResponse,
    WorkerCreate,
    WorkerUpdate,
    WorkerResponse,
    PartCreate,
    PartUpdate,
    PartResponse,
    OperationCreate,
    OperationUpdate,
    OperationResponse,
)
from app.core.response_models import ApiResponse

router = APIRouter(prefix="/master-data", tags=["Master Data"])
logger = logging.getLogger("jobwork-backend")


def _get_context(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User context missing")
    
    tenant_id = user["tenant_id"]
    role = str(user.get("role") or "").upper()
    if role not in {"OWNER", "SUPERVISOR"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Master Data is restricted to owners and supervisors.",
        )
    
    # Strictly enforce tenant isolation in contextvars
    tenant_id_context.set(tenant_id)
    
    return tenant_id, role


def _require_admin(role: str):
    if role not in {"OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Master data changes require Owner permissions."
        )


# ---------------------------------------------------------
# Customers
# ---------------------------------------------------------

@router.post("/customers", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[CustomerResponse])
@role_required(["OWNER"])
async def create_customer(payload: CustomerCreate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    customer = await service.create_customer(db, tenant_id, payload)
    return ApiResponse(data=CustomerResponse.model_validate(customer), message="Customer established.")

@router.get("/customers", response_model=ApiResponse[List[CustomerResponse]])
async def list_customers(request: Request, include_inactive: bool = Query(False), db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    customers = await service.list_customers(db, tenant_id, include_inactive=include_inactive)
    return ApiResponse(data=[CustomerResponse.model_validate(c) for c in customers])

@router.get("/customers/{customer_id}", response_model=ApiResponse[CustomerResponse])
async def get_customer(customer_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    customer = await service.get_customer(db, tenant_id, customer_id)
    return ApiResponse(data=CustomerResponse.model_validate(customer))

@router.patch("/customers/{customer_id}", response_model=ApiResponse[CustomerResponse])
@role_required(["OWNER"])
async def update_customer(customer_id: UUID, payload: CustomerUpdate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    customer = await service.update_customer(db, tenant_id, customer_id, payload)
    return ApiResponse(data=CustomerResponse.model_validate(customer))

@router.delete("/customers/{customer_id}")
@role_required(["OWNER"])
async def delete_customer(customer_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    result = await service.delete_customer(db, tenant_id, customer_id)
    return ApiResponse(data=result, message="Customer record removed.")


# ---------------------------------------------------------
# Machines
# ---------------------------------------------------------

@router.post("/machines", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[MachineResponse])
@role_required(["OWNER"])
async def create_machine(payload: MachineCreate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    machine = await service.create_machine(db, tenant_id, payload)
    return ApiResponse(data=MachineResponse.model_validate(machine), message="Machine successfully provisioned.")

@router.get("/machines", response_model=ApiResponse[List[MachineResponse]])
async def list_machines(request: Request, include_inactive: bool = Query(False), db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    machines = await service.list_machines(db, tenant_id, include_inactive=include_inactive)
    return ApiResponse(data=[MachineResponse.model_validate(m) for m in machines])

@router.get("/machines/{machine_id}", response_model=ApiResponse[MachineResponse])
async def get_machine(machine_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    machine = await service.get_machine(db, tenant_id, machine_id)
    return ApiResponse(data=MachineResponse.model_validate(machine))

@router.patch("/machines/{machine_id}", response_model=ApiResponse[MachineResponse])
@role_required(["OWNER"])
async def update_machine(machine_id: UUID, payload: MachineUpdate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    machine = await service.update_machine(db, tenant_id, machine_id, payload)
    return ApiResponse(data=MachineResponse.model_validate(machine))

@router.delete("/machines/{machine_id}")
@role_required(["OWNER"])
async def delete_machine(machine_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    result = await service.delete_machine(db, tenant_id, machine_id)
    return ApiResponse(data=result, message="Machine purged.")


# ---------------------------------------------------------
# Workers
# ---------------------------------------------------------

@router.post("/workers", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[WorkerResponse])
@role_required(["OWNER"])
async def create_worker(payload: WorkerCreate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    worker = await service.create_worker(db, tenant_id, payload)
    return ApiResponse(data=WorkerResponse.model_validate(worker))

@router.get("/workers", response_model=ApiResponse[List[WorkerResponse]])
async def list_workers(request: Request, include_inactive: bool = Query(False), db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    workers = await service.list_workers(db, tenant_id, include_inactive=include_inactive)
    return ApiResponse(data=[WorkerResponse.model_validate(w) for w in workers])

@router.get("/workers/{worker_id}", response_model=ApiResponse[WorkerResponse])
async def get_worker(worker_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    worker = await service.get_worker(db, tenant_id, worker_id)
    return ApiResponse(data=WorkerResponse.model_validate(worker))

@router.patch("/workers/{worker_id}", response_model=ApiResponse[WorkerResponse])
@role_required(["OWNER"])
async def update_worker(worker_id: UUID, payload: WorkerUpdate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    worker = await service.update_worker(db, tenant_id, worker_id, payload)
    return ApiResponse(data=WorkerResponse.model_validate(worker))

@router.delete("/workers/{worker_id}")
@role_required(["OWNER"])
async def delete_worker(worker_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    result = await service.delete_worker(db, tenant_id, worker_id)
    return ApiResponse(data=result)


# ---------------------------------------------------------
# Shifts
# ---------------------------------------------------------

@router.post("/shifts", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[ShiftResponse])
@role_required(["OWNER"])
async def create_shift(payload: ShiftCreate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    shift = await service.create_shift(db, tenant_id, payload)
    return ApiResponse(data=ShiftResponse.model_validate(shift))

@router.get("/shifts", response_model=ApiResponse[List[ShiftResponse]])
async def list_shifts(request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    shifts = await service.list_shifts(db, tenant_id)
    return ApiResponse(data=[ShiftResponse.model_validate(s) for s in shifts])

@router.get("/shifts/{shift_id}", response_model=ApiResponse[ShiftResponse])
async def get_shift(shift_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    shift = await service.get_shift(db, tenant_id, shift_id)
    return ApiResponse(data=ShiftResponse.model_validate(shift))

@router.patch("/shifts/{shift_id}", response_model=ApiResponse[ShiftResponse])
@role_required(["OWNER"])
async def update_shift(shift_id: UUID, payload: ShiftUpdate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    shift = await service.update_shift(db, tenant_id, shift_id, payload)
    return ApiResponse(data=ShiftResponse.model_validate(shift))

@router.delete("/shifts/{shift_id}")
@role_required(["OWNER"])
async def delete_shift(shift_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    result = await service.delete_shift(db, tenant_id, shift_id)
    return ApiResponse(data=result)


# ---------------------------------------------------------
# Parts
# ---------------------------------------------------------

@router.post("/parts", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[PartResponse])
@role_required(["OWNER"])
async def create_part(payload: PartCreate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    part = await service.create_part(db, tenant_id, payload)
    return ApiResponse(data=PartResponse.model_validate(part))

@router.get("/parts", response_model=ApiResponse[List[PartResponse]])
async def list_parts(request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    parts = await service.list_parts(db, tenant_id)
    return ApiResponse(data=[PartResponse.model_validate(p) for p in parts])

@router.get("/parts/{part_id}", response_model=ApiResponse[PartResponse])
async def get_part(part_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    part = await service.get_part(db, tenant_id, part_id)
    return ApiResponse(data=PartResponse.model_validate(part))

@router.patch("/parts/{part_id}", response_model=ApiResponse[PartResponse])
@role_required(["OWNER"])
async def update_part(part_id: UUID, payload: PartUpdate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    part = await service.update_part(db, tenant_id, part_id, payload)
    return ApiResponse(data=PartResponse.model_validate(part))

@router.delete("/parts/{part_id}")
@role_required(["OWNER"])
async def delete_part(part_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    result = await service.delete_part(db, tenant_id, part_id)
    return ApiResponse(data=result)


# ---------------------------------------------------------
# Operations
# ---------------------------------------------------------

@router.post("/operations", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[OperationResponse])
@role_required(["OWNER"])
async def create_operation(payload: OperationCreate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    operation = await service.create_operation(db, tenant_id, payload)
    return ApiResponse(data=OperationResponse.model_validate(operation), message="Operation created successfully.")

@router.get("/operations", response_model=ApiResponse[List[OperationResponse]])
async def list_operations(request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    operations = await service.list_operations(db, tenant_id)
    return ApiResponse(data=[OperationResponse.model_validate(o) for o in operations])

@router.get("/operations/{operation_id}", response_model=ApiResponse[OperationResponse])
async def get_operation(operation_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, _ = _get_context(request)
    operation = await service.get_operation(db, tenant_id, operation_id)
    return ApiResponse(data=OperationResponse.model_validate(operation))

@router.patch("/operations/{operation_id}", response_model=ApiResponse[OperationResponse])
@role_required(["OWNER"])
async def update_operation(operation_id: UUID, payload: OperationUpdate, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    operation = await service.update_operation(db, tenant_id, operation_id, payload)
    return ApiResponse(data=OperationResponse.model_validate(operation))

@router.delete("/operations/{operation_id}")
@role_required(["OWNER"])
async def delete_operation(operation_id: UUID, request: Request, db: AsyncSession = Depends(get_async_db)):
    tenant_id, role = _get_context(request)
    result = await service.delete_operation(db, tenant_id, operation_id)
    return ApiResponse(data=result, message="Operation removed.")
