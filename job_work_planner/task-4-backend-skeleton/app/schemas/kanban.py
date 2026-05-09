"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: kanban.py
 * 
 * 1) Purpose: Pydantic models for request/response validation.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class KanbanJobCard(BaseModel):
    job_id: UUID
    job_number: str
    customer_name: str
    part_number: str
    quantity: int
    due_date: Optional[datetime]
    priority: str
    delayed: bool
    alert_priority: str = "NORMAL"

class KanbanStage(BaseModel):
    stage_id: UUID
    stage_name: str
    jobs: List[KanbanJobCard]
    counts: dict = Field(default_factory=lambda: {"total": 0, "delayed": 0})

class KanbanBoardResponse(BaseModel):
    stages: List[KanbanStage]
