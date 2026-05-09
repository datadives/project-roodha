"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: system.py
 * 
 * 1) Purpose: Defines API endpoints for system.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import require_roles
from app.core.proactive_delay_guard import evaluate_tenant_delays
from app.database import get_async_db
from app.database import fetch_db_runtime_snapshot
from app.routes.response_utils import api_success

router = APIRouter(tags=["System"])


@router.get("/health")
def health_check():
    return api_success({"status": "ok", "service": "jobwork-backend"}, message="Health check passed")


@router.get("/ready")
def readiness_check():
    return api_success(
        {
            "status": "ready",
            "dependencies": {"database": "not_checked", "s3": "not_checked"},
        },
        message="Readiness check passed",
    )


@router.get("/tenant/current")
def get_current_tenant(request: Request):
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    tenant = {
        "tenant_id": user["tenant_id"],
        "tenant_name": "Demo Company Pvt Ltd",
        "plan": "trial",
    }

    return api_success({"user": user, "tenant": tenant}, message="Current tenant fetched")


@router.get("/debug/db-check")
async def debug_db_check():
    snapshot = await fetch_db_runtime_snapshot()
    return api_success(snapshot, message="Database runtime check passed")


@router.post("/system/delay-guard/evaluate")
async def trigger_delay_guard_evaluation(
    user: dict = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Manually evaluate V1.5 delay risk for the authenticated tenant and create
    tenant-wide delay notifications for overdue or near-due jobs.
    """
    result = await evaluate_tenant_delays(db, user["tenant_id"])
    return api_success(result, message="Delay guard evaluation completed")
