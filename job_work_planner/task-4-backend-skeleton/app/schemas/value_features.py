"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: value_features.py
 * 
 * 1) Purpose: Pydantic models for request/response validation.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from typing import List

class MachineLoadEntry(BaseModel):
    machine_id: UUID
    machine_name: str
    date: date
    total_hours: float
    is_overloaded: bool
    is_estimated: bool = False

class MachineLoadResponse(BaseModel):
    load_data: List[MachineLoadEntry]

class ExportResponse(BaseModel):
    download_url: str
    filename: str | None = None

class AutoSchedulePreviewRequest(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    job_ids: list[UUID] | None = None
    limit: int = 50

class AutoScheduleApplyItem(BaseModel):
    job_operation_id: UUID
    machine_id: UUID
    planned_start_date: datetime | None = None
    planned_end_date: datetime | None = None

class AutoScheduleApplyRequest(BaseModel):
    suggestions: list[AutoScheduleApplyItem]

class AutoScheduleSuggestion(BaseModel):
    job_operation_id: UUID
    job_id: UUID
    job_number: str | None = None
    operation_name: str | None = None
    sequence_number: int | None = None
    machine_id: UUID | None = None
    planned_machine_id: UUID | None = None
    machine_name: str | None = None
    planned_start_date: datetime | None = None
    planned_end_date: datetime | None = None
    due_date: datetime | None = None
    due_date_risk: bool = False
    estimated_hours: float
    reason: str
    conflict_reason: str | None = None

class AutoScheduleResponse(BaseModel):
    suggestions: List[AutoScheduleSuggestion]
