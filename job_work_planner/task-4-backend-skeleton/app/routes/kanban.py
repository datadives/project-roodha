"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: kanban.py
 * 
 * 1) Purpose: Defines API endpoints for kanban.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.core.jobs_by_stage_service import get_jobs_by_stage_service
from app.core.tenant_context import tenant_id_context
from app.schemas.kanban import KanbanBoardResponse
from app.core.response_models import ApiResponse

router = APIRouter(prefix="/kanban", tags=["Kanban"])
logger = logging.getLogger("jobwork-backend")

@router.get("", response_model=ApiResponse[KanbanBoardResponse])
async def get_kanban_board(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Unified Kanban Board: Metadata-enriched Single Source of Truth for supervisors.
    """
    # 1. Access user state from middleware
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User context missing")
    
    tenant_id = user["tenant_id"]
    role = str(user.get("role") or "").upper()
    assigned_machine_id = user.get("machine_id") if role == "OPERATOR" else None
    
    # Ensure context is set (redundant if middleware works perfectly, but safe)
    tenant_id_context.set(tenant_id)

    try:
        # 2. Fetch Board Data via Service
        board_data = await get_jobs_by_stage_service(db, tenant_id, machine_id=assigned_machine_id)
        
        return ApiResponse(
            data=KanbanBoardResponse(**board_data),
            message="Kanban board synchronized successfully"
        )
    except Exception as e:
        logger.exception("Failed to fetch kanban board")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Kanban board error: {str(e)}"
        )
