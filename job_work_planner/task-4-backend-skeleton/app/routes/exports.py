"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: exports.py
 * 
 * 1) Purpose: Defines API endpoints for exports.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.services.export_service import generate_jobs_csv_and_upload, generate_machine_load_csv
from app.schemas.value_features import ExportResponse
from app.core.auth_middleware import require_roles

router = APIRouter(prefix="/exports", tags=["Data Exports"])

@router.get("/jobs", response_model=ExportResponse)
async def export_jobs(
    user: dict = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    GET /api/exports/jobs
    Generates the tenant job CSV, stores it in S3, and returns a short-lived
    pre-signed download URL.
    """
    tenant_id = user["tenant_id"]
    
    try:
        result = await generate_jobs_csv_and_upload(db, tenant_id)
        return ExportResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/machine-load", response_model=ExportResponse)
async def export_machine_load(
    user: dict = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    POST /api/exports/machine-load
    Aggregates planned hours per machine for active operations and returns a CSV download URL.
    """
    tenant_id = user["tenant_id"]

    try:
        result = await generate_machine_load_csv(db, tenant_id)
        return ExportResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
