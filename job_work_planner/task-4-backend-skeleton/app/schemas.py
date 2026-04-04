from typing import Any

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


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class MachineResponse(BaseModel):
    machine_id: str
    tenant_id: str
    name: str
    type: str
    is_active: bool

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


class PartCreate(BaseModel):
    part_number: str = Field(..., min_length=1, max_length=255)
    customer_id: str
    default_operations_route: list[dict[str, Any]] = Field(..., min_length=1)

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

    model_config = ConfigDict(from_attributes=True)
