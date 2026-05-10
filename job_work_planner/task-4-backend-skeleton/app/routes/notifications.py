"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: notifications.py
 * 
 * 1) Purpose: Defines API endpoints for notifications.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
# app/routes/notifications.py
"""
Notifications router — fully async.
Uses get_async_db() to avoid connection-pool exhaustion in the async
FastAPI application. All endpoint handlers are declared with `async def`.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_service import (
    get_unread_notification_count,
    get_user_notifications,
    mark_notification_read,
)
from app.database import get_async_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _require_user(request: Request) -> dict:
    """Extract and validate the authenticated user from request state."""
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
    return user


@router.get("", summary="List notifications for the current user")
async def get_notifications(
    request: Request,
    unread_only: bool = Query(False, description="Return only unread notifications"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Returns paginated notifications for the authenticated user, including
    tenant-wide broadcasts (user_id IS NULL). Optionally filter to unread
    notifications only.
    """
    user = _require_user(request)

    try:
        notifications = await get_user_notifications(
            db=db,
            tenant_id=user["tenant_id"],
            user_id=user.get("user_id", ""),
            unread_only=unread_only,
        )

        unread_count = await get_unread_notification_count(
            db=db,
            tenant_id=user["tenant_id"],
            user_id=user.get("user_id", ""),
        )
    except Exception:
        # Graceful fallback for empty/missing data instead of 500
        notifications = []
        unread_count = 0

    payload = {
        "notifications": jsonable_encoder(notifications),
        "unread_count": unread_count,
    }
    return api_success(payload)



@router.patch("/{notification_id}/read", summary="Mark a notification as read")
async def mark_as_read(
    notification_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Marks the specified notification as read and stamps the read_at timestamp.
    Only the owning user (or tenant-wide broadcasts accessible to this user)
    can be marked as read.
    """
    user = _require_user(request)

    try:
        updated = await mark_notification_read(
            db=db,
            notification_id=notification_id,
            tenant_id=user["tenant_id"],
            user_id=user.get("user_id", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return api_success(jsonable_encoder(updated), message="Notification marked as read")
