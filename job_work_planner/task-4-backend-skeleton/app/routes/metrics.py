"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: metrics.py
 * 
 * 1) Purpose: Defines API endpoints for metrics.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics_service import (
    get_estimated_cost_summary_service,
    get_bottleneck_metrics_service,
    get_late_jobs_service,
    get_wip_metrics_service,
)
from app.core.jobs_by_stage_service import get_jobs_by_stage_service
from app.database import get_async_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/metrics", tags=["Dashboard & Metrics"])
logger = logging.getLogger("jobwork-backend")


def _get_dashboard_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        logger.warning("Metrics access attempt without valid user state.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Unauthorized: User context missing from request."
        )

    role = user.get("role")
    if role not in {"SUPERVISOR", "OWNER"}:
        logger.warning(f"Metrics access denied for role: {role} (User: {user.get('user_id')})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Forbidden: Dashboard access restricted to planning/management roles."
        )

    return user


@router.get("/wip")
async def get_wip_metrics(
    request: Request,
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        user = _get_dashboard_user(request)
        tenant_id = user["tenant_id"]
        
        logger.info(f"Fetching WIP metrics for tenant: {tenant_id}")
        wip_data = await get_wip_metrics_service(db, tenant_id, from_date, to_date)
        stage_data = await get_jobs_by_stage_service(db, tenant_id)
        
        return api_success(
            {
                "wip_by_stage": wip_data,
                "stages": stage_data.get("stages", []),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"CRITICAL: 500 error in get_wip_metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error calculating WIP metrics. Error logged for investigation."
        )


@router.get("/bottlenecks")
async def get_bottleneck_metrics(
    request: Request,
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        user = _get_dashboard_user(request)
        tenant_id = user["tenant_id"]
        
        logger.info(f"Fetching Bottleneck metrics for tenant: {tenant_id}")
        metrics = await get_bottleneck_metrics_service(db, tenant_id, from_date, to_date)
        return api_success({"bottlenecks": metrics})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"CRITICAL: 500 error in get_bottleneck_metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error calculating machine bottlenecks."
        )


@router.get("/late-jobs")
async def get_late_jobs_metrics(request: Request, db: AsyncSession = Depends(get_async_db)):
    try:
        user = _get_dashboard_user(request)
        tenant_id = user["tenant_id"]
        
        logger.info(f"Fetching Late Jobs metrics for tenant: {tenant_id}")
        metrics = await get_late_jobs_service(db, tenant_id)
        return api_success(metrics)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"CRITICAL: 500 error in get_late_jobs_metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error identifying late jobs."
        )


@router.get("/costing-summary")
async def get_costing_summary(request: Request, db: AsyncSession = Depends(get_async_db)):
    try:
        user = _get_dashboard_user(request)
        if user.get("role") != "OWNER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Costing analytics are restricted to owners.",
            )
        tenant_id = user["tenant_id"]
        
        logger.info(f"Fetching Costing Summary for tenant: {tenant_id}")
        metrics = await get_estimated_cost_summary_service(db, tenant_id)
        return api_success(metrics)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"CRITICAL: 500 error in get_costing_summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error generating costing summary."
        )
