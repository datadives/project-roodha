"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: base.py
 * 
 * 1) Purpose: Pydantic models for request/response validation.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from datetime import datetime, time
from decimal import Decimal
from typing import Any, Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, EmailStr


def _validate_route_steps(value: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if value is None:
        return value

    if len(value) == 0:
        raise ValueError("default_operations_route cannot be empty")

    if any(not isinstance(step, dict) or len(step) == 0 for step in value):
        raise ValueError("Each route step must be a non-empty object")

    return value


class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact: Optional[str] = Field(default=None, max_length=255, alias="contact_person", validation_alias="contact_person", serialization_alias="contact")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = True

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None

class CustomerResponse(CustomerBase):
    customer_id: UUID
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)


class MachineBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)

class MachineCreate(MachineBase):
    pass

class MachineUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    type: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)

class MachineResponse(MachineBase):
    machine_id: UUID
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)


class ShiftBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    start_time: time
    end_time: time

class ShiftCreate(ShiftBase):
    pass

class ShiftUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    start_time: Optional[time] = None
    end_time: Optional[time] = None

class ShiftResponse(ShiftBase):
    shift_id: UUID
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)


class WorkerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)

class WorkerCreate(WorkerBase):
    pass

class WorkerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)

class WorkerResponse(WorkerBase):
    worker_id: UUID
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)


class PartBase(BaseModel):
    part_number: str = Field(..., min_length=1, max_length=255)
    customer_id: UUID
    default_operations_route: list[dict[str, Any]] = Field(..., min_length=1)
    default_material_cost_per_unit: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)

class PartCreate(PartBase):
    @field_validator("default_operations_route")
    @classmethod
    def validate_non_empty_route(cls, value: list[dict[str, Any]]):
        validated = _validate_route_steps(value)
        if validated is None:
            raise ValueError("default_operations_route must contain at least one operation")
        return validated

class PartUpdate(BaseModel):
    part_number: Optional[str] = Field(default=None, min_length=1, max_length=255)
    customer_id: Optional[UUID] = None
    default_operations_route: Optional[list[dict[str, Any]]] = None
    default_material_cost_per_unit: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)

    @field_validator("default_operations_route")
    @classmethod
    def validate_route_if_provided(cls, value: Optional[list[dict[str, Any]]]):
        return _validate_route_steps(value)

class PartResponse(PartBase):
    default_operations_route: list[dict[str, Any]] = Field(default_factory=list)
    part_id: UUID
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)

    @field_validator("default_operations_route", mode="before")
    @classmethod
    def default_empty_route_for_legacy_rows(cls, value):
        return value or []


class JobOperationResponse(BaseModel):
    job_op_id: UUID
    tenant_id: str
    job_id: UUID
    op_id: UUID
    machine_id: Optional[UUID] = None
    worker_id: Optional[UUID] = None
    shift_id: Optional[UUID] = None
    sequence_number: int
    status: str
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    quantity_completed: int = 0
    quantity_rejected: int = 0

    model_config = ConfigDict(from_attributes=True)

class JobOperationUpdate(BaseModel):
    status: Optional[str] = None
    worker_id: Optional[UUID] = None
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    quantity_completed: Optional[int] = Field(default=None, ge=0)
    quantity_rejected: Optional[int] = Field(default=None, ge=0)


class JobCostSummaryResponse(BaseModel):
    summary_id: UUID
    tenant_id: str
    job_id: UUID
    machine_cost: Optional[Decimal] = None
    labour_cost: Optional[Decimal] = None
    material_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    last_calculated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class PlanPayload(BaseModel):
    machine_id: UUID
    shift_id: Optional[UUID] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    force: bool = False
    reason: Optional[str] = None
    ignore_conflicts: bool = False

class OperationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    standard_cycle_time_mins: int = Field(default=0, ge=0)

class OperationCreate(OperationBase):
    pass

class OperationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    standard_cycle_time_mins: Optional[int] = Field(default=None, ge=0)

class OperationResponse(OperationBase):
    operation_id: UUID
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)
