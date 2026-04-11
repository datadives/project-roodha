from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_route_steps(value: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if value is None:
        return value

    if len(value) == 0:
        raise ValueError("default_operations_route cannot be empty")

    if any(not isinstance(step, dict) or len(step) == 0 for step in value):
        raise ValueError("Each route step must be a non-empty object")

    return value


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contact: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class CustomerResponse(BaseModel):
    customer_id: str
    tenant_id: str
    name: str
    contact: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MachineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)


class MachineResponse(BaseModel):
    machine_id: str
    tenant_id: str
    name: str
    type: str
    is_active: bool
    hourly_rate: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class ShiftCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    start_time: str = Field(..., min_length=1, max_length=32)
    end_time: str = Field(..., min_length=1, max_length=32)


class ShiftUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    start_time: str | None = Field(default=None, min_length=1, max_length=32)
    end_time: str | None = Field(default=None, min_length=1, max_length=32)


class ShiftResponse(BaseModel):
    shift_id: str
    tenant_id: str
    name: str
    start_time: str
    end_time: str

    model_config = ConfigDict(from_attributes=True)


class WorkerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)


class WorkerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    hourly_rate: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)


class WorkerResponse(BaseModel):
    worker_id: str
    tenant_id: str
    name: str
    role: str
    is_active: bool
    hourly_rate: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class PartCreate(BaseModel):
    part_number: str = Field(..., min_length=1, max_length=255)
    customer_id: str
    default_operations_route: list[dict[str, Any]] = Field(..., min_length=1)
    default_material_cost_per_unit: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)

    @field_validator("default_operations_route")
    @classmethod
    def validate_non_empty_route(cls, value: list[dict[str, Any]]):
        validated = _validate_route_steps(value)
        if validated is None:
            raise ValueError("default_operations_route must contain at least one operation")
        return validated


class PartUpdate(BaseModel):
    part_number: str | None = Field(default=None, min_length=1, max_length=255)
    customer_id: str | None = None
    default_operations_route: list[dict[str, Any]] | None = None
    default_material_cost_per_unit: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)

    @field_validator("default_operations_route")
    @classmethod
    def validate_route_if_provided(cls, value: list[dict[str, Any]] | None):
        return _validate_route_steps(value)


class PartResponse(BaseModel):
    part_id: str
    tenant_id: str
    part_number: str
    customer_id: str
    default_operations_route: list[dict[str, Any]]
    default_material_cost_per_unit: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class JobOperationResponse(BaseModel):
    job_operation_id: str
    tenant_id: str
    job_id: str
    operation_id: str
    machine_id: Optional[str] = None
    shift_id: Optional[str] = None
    sequence_number: int
    status: str
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    quantity_completed: int = 0
    quantity_rejected: int = 0

    model_config = ConfigDict(from_attributes=True)


class JobCostSummaryResponse(BaseModel):
    summary_id: str
    tenant_id: str
    job_id: str
    machine_cost: Optional[Decimal] = None
    labour_cost: Optional[Decimal] = None
    material_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    last_calculated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
