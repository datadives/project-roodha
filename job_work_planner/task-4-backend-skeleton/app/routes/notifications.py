# app/routes/notifications.py

<<<<<<< ours
<<<<<<< ours
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session
from app.database import get_db

=======
from fastapi import APIRouter, HTTPException, Request, Query
>>>>>>> theirs
=======
from fastapi import APIRouter, HTTPException, Request, Query
>>>>>>> theirs
from app.core.notification_service import get_user_notifications, mark_notification_read
from app.routes.response_utils import api_success

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.get("/")
def get_notifications(
    request: Request,
    unread_only: bool = Query(False),
<<<<<<< ours
<<<<<<< ours
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
    """
    Fetch in-app notifications for the logged-in user.
    """
    # Fallback to test user for local development if JWT is missing
    tenant_id = "tenant-123"
    user_id = "user-001"
    
    if hasattr(request.state, "user"):
        tenant_id = request.state.user.get("tenant_id", "tenant-123")
        user_id = request.state.user.get("user_id", "user-001")
        
    notifs = get_user_notifications(
        db=db,  # 👈 NEW: Pass database session to service layer
        tenant_id=tenant_id, 
        user_id=user_id,
        unread_only=unread_only
    )
    
    # Safely handle the unread count whether the service returns dictionaries or SQLAlchemy models
    unread_count = 0
    for n in notifs:
        is_read = n["is_read"] if isinstance(n, dict) else n.is_read
        if not is_read:
            unread_count += 1
            
    return {"notifications": notifs, "unread_count": unread_count}


@router.patch("/{notification_id}/read")
def mark_as_read(
    notification_id: str, 
    request: Request,
    db: Session = Depends(get_db)  # 👈 NEW: Get AWS Database session
):
    """
    Mark a notification as read.
    """
    tenant_id = "tenant-123"
    if hasattr(request.state, "user"):
        tenant_id = request.state.user.get("tenant_id", "tenant-123")
        
    try:
        updated = mark_notification_read(
            db=db,  # 👈 NEW: Pass database session to service layer
            notification_id=notification_id, 
            tenant_id=tenant_id
=======
):
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = request.state.user

    notifs = get_user_notifications(
        tenant_id=user["tenant_id"],
        user_id=user["user_id"],
        unread_only=unread_only,
    )

    payload = {
        "notifications": notifs,
        "unread_count": sum(1 for n in notifs if not n["is_read"]),
    }
    return api_success(payload)


@router.patch("/{notification_id}/read")
def mark_as_read(notification_id: str, request: Request):
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        updated = mark_notification_read(
            notification_id=notification_id,
            tenant_id=request.state.user["tenant_id"],
>>>>>>> theirs
=======
):
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = request.state.user

    notifs = get_user_notifications(
        tenant_id=user["tenant_id"],
        user_id=user["user_id"],
        unread_only=unread_only,
    )

    payload = {
        "notifications": notifs,
        "unread_count": sum(1 for n in notifs if not n["is_read"]),
    }
    return api_success(payload)


@router.patch("/{notification_id}/read")
def mark_as_read(notification_id: str, request: Request):
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        updated = mark_notification_read(
            notification_id=notification_id,
            tenant_id=request.state.user["tenant_id"],
>>>>>>> theirs
        )
        return api_success(updated, message="Notification marked as read")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
