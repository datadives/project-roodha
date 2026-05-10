"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: maintenance.py
 * 
 * 1) Purpose: Defines API endpoints for maintenance.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
maintenance.py
--------------
Maintenance routes for batch processing and reconciliations.
Authorized via IAM SigV4 for safe EventBridge/Lambda triggers.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.services.maintenance_service import run_batch_costing_service
from app.core.response_models import ApiResponse

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])
logger = logging.getLogger("jobwork-backend")

async def require_iam_auth(request: Request):
    """
    Dependency that enforces IAM-based authorization.
    Verifies that the request was signed via AWS SigV4 and passed by API Gateway.
    """
    # 1. Check for standard AWS Lambda/API Gateway authorizer context
    # Mangum usually populates 'aws.event' in the scope
    aws_event = request.scope.get("aws_event") or {}
    request_context = aws_event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    
    # Check for IAM context (populated when using AWS_IAM auth type)
    iam_context = authorizer.get("iam")
    
    if not iam_context:
        # Fallback: check if we are in development
        import os
        if os.getenv("ENV") == "development":
            logger.warning("MAINTENANCE | Bypassing IAM check in development.")
            return True
            
        logger.error(f"MAINTENANCE | Forbidden: Access attempt without valid IAM context. Scope: {authorizer}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Maintenance routes require IAM-based authorization."
        )
    
    logger.info(f"MAINTENANCE | Authorized via IAM: {iam_context.get('accessKey')}")
    return True

@router.post("/batch-costing", response_model=ApiResponse)
async def trigger_batch_costing(
    request: Request,
    is_authorized: bool = Depends(require_iam_auth),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Manually triggers the batch costing reconciliation.
    Designed for EventBridge invocation at 11:30 PM UTC.
    """
    result = await run_batch_costing_service(db)
    return ApiResponse(data=result, message="Batch costing reconciliation completed.")
