# app/core/notification_service.py

import logging
import uuid
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger("jobwork-backend")

def create_notification(
    db: Session,          # 👈 NEW: Database session
    tenant_id: str, 
    user_id: str | None,  # If None, broadcasts to all in tenant
    notif_type: str,      # 'READY', 'CONFLICT', 'DELAY'
    message: str, 
    entity_ref: str
):
    """
    Creates an in-app notification record directly in AWS RDS.
    """
    notification = models.Notification(
        notification_id=f"NOT-{str(uuid.uuid4())[:8]}",
        tenant_id=tenant_id,
        user_id=user_id, 
        type=notif_type,
        message=message,
        is_read=False,
        created_at=datetime.utcnow().isoformat()
        
        # ⚠️ NOTE: 'entity_reference' was in your mock DB, but isn't in models.py yet.
        # Add it to models.py as a Column(String) and you can uncomment the line below!
        # entity_reference=entity_ref 
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    logger.info(f"NOTIFICATION_CREATED | Type: {notif_type} | Ref: {entity_ref}")
    return notification


def get_user_notifications(db: Session, tenant_id: str, user_id: str, unread_only: bool = False):
    """
    Fetches notifications for a user (and tenant-wide broadcasts) from AWS RDS.
    """
    # Base query: Matches the tenant AND (Matches the user OR is a broadcast where user_id is NULL)
    query = db.query(models.Notification).filter(
        models.Notification.tenant_id == tenant_id,
        or_(models.Notification.user_id == user_id, models.Notification.user_id.is_(None))
    )
    
    # Optional filter
    if unread_only:
        query = query.filter(models.Notification.is_read == False)
        
    # Sort newest first and execute
    return query.order_by(models.Notification.created_at.desc()).all()


def get_unread_notification_count(db: Session, tenant_id: str, user_id: str) -> int:
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.tenant_id == tenant_id,
            or_(models.Notification.user_id == user_id, models.Notification.user_id.is_(None)),
            models.Notification.is_read == False,
        )
        .count()
    )


def mark_notification_read(db: Session, notification_id: str, tenant_id: str, user_id: str):
    """
    Marks a specific notification as read in AWS RDS.
    """
    notif = db.query(models.Notification).filter(
        models.Notification.notification_id == notification_id,
        models.Notification.tenant_id == tenant_id,
        or_(models.Notification.user_id == user_id, models.Notification.user_id.is_(None)),
    ).first()
    
    if not notif:
        raise ValueError("Notification not found or unauthorized access")
        
    notif.is_read = True
    
    # ⚠️ NOTE: 'read_at' is another field that isn't in models.py yet!
    # notif.read_at = datetime.utcnow().isoformat() 
    
    db.commit()
    db.refresh(notif)
    return notif
