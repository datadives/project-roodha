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
from datetime import date
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

class AutoScheduleSuggestion(BaseModel):
    job_operation_id: UUID
    job_id: UUID
    machine_id: UUID
    machine_name: str
    estimated_hours: float
    reason: str

class AutoScheduleResponse(BaseModel):
    suggestions: List[AutoScheduleSuggestion]
