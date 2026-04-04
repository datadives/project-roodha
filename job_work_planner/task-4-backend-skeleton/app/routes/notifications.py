from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.notification_service import get_user_notifications, mark_notification_read
from app.database import get_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _require_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


@router.get("/")
def get_notifications(
    request: Request,
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    user = _require_user(request)

    notifications = get_user_notifications(
        db=db,
        tenant_id=user["tenant_id"],
        user_id=user.get("user_id", ""),
        unread_only=unread_only,
    )

    payload = {
        "notifications": jsonable_encoder(notifications),
        "unread_count": sum(1 for notification in notifications if not notification.is_read),
    }
    return api_success(payload)


@router.patch("/{notification_id}/read")
def mark_as_read(notification_id: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request)

    try:
        updated = mark_notification_read(
            db=db,
            notification_id=notification_id,
            tenant_id=user["tenant_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return api_success(jsonable_encoder(updated), message="Notification marked as read")
