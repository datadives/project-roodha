"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: jobs.py
 * 
 * 1) Purpose: Pydantic models for request/response validation.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Any, Optional, List
from app.models import JobStatus, OperationStatus

class JobBase(BaseModel):
    customer_id: UUID
    part_id: UUID
    quantity: int = Field(..., gt=0)
    due_date: Optional[datetime] = None
    priority: str = Field(default="MEDIUM")

class JobCreate(JobBase):
    job_number: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[dict[str, str]] = None


class JobUpdate(BaseModel):
    """Schema for PATCH /api/jobs/{id}. All fields are optional."""
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    quantity: Optional[int] = Field(default=None, gt=0)
    remarks: Optional[str] = Field(default=None, max_length=1000)
    operation_ids: Optional[List[UUID]] = None
    route_operation_ids: Optional[List[UUID]] = None
    operations: Optional[List[Any]] = None


class JobOperationResponse(BaseModel):
    job_op_id: UUID
    tenant_id: str
    job_id: UUID
    op_id: UUID
    machine_id: Optional[UUID] = None
    worker_id: Optional[UUID] = None
    shift_id: Optional[UUID] = None
    sequence_number: int
    status: OperationStatus
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    quantity_completed: int = 0
    quantity_rejected: int = 0

    model_config = ConfigDict(from_attributes=True)

class JobResponse(JobBase):
    job_id: UUID
    tenant_id: str
    job_number: str
    status: JobStatus
    alert_priority: str = "NORMAL"
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str

    model_config = ConfigDict(from_attributes=True)


class JobWithOperations(JobResponse):
    operations: List[JobOperationResponse] = []
