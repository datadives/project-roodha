"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: notification_service.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
# app/core/notification_service.py
"""
Async notification service for Project Roodha.
All functions use AsyncSession (via get_async_db) to avoid connection pool
exhaustion in the async FastAPI application.
"""

import logging
import os
import uuid
import boto3
from datetime import datetime, timezone

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app import models

logger = logging.getLogger("jobwork-backend")


async def create_notification(
    db: AsyncSession,
    tenant_id: str,
    user_id: str | None,   # None → broadcast to all tenant users
    notif_type: str,       # e.g. 'READY', 'CONFLICT', 'DELAY'
    message: str,
    entity_ref: str | None = None,
) -> models.Notification:
    """
    Persists an in-app notification record to the database.

    Args:
        db:          Active async database session.
        tenant_id:   Owning tenant.
        user_id:     Target user, or None for a tenant-wide broadcast.
        notif_type:  Notification category string.
        message:     Human-readable notification body.
        entity_ref:  Optional reference token (e.g. 'JOB-042', 'OP-ABC').

    Returns:
        The persisted Notification ORM instance.
    """
    notification = models.Notification(
        notification_id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        type=notif_type,
        message=message,
        entity_reference=entity_ref,
        is_read=False,
        read_at=None,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    logger.info(
        "NOTIFICATION_CREATED | tenant=%s | user=%s | type=%s | ref=%s",
        tenant_id, user_id, notif_type, entity_ref,
    )
    return notification


async def get_user_notifications(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    unread_only: bool = False,
) -> list[models.Notification]:
    """
    Returns notifications for a user, including tenant-wide broadcasts
    (where user_id IS NULL), sorted newest-first.
    """
    stmt = (
        select(models.Notification)
        .where(
            models.Notification.tenant_id == tenant_id,
            or_(
                models.Notification.user_id == user_id,
                models.Notification.user_id.is_(None),
            ),
        )
    )

    if unread_only:
        stmt = stmt.where(models.Notification.is_read == False)  # noqa: E712

    stmt = stmt.order_by(models.Notification.created_at.desc())

    result = await db.execute(stmt)
    return result.scalars().all()


async def get_unread_notification_count(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
) -> int:
    """Returns the count of unread notifications for a user (incl. broadcasts)."""
    stmt = (
        select(func.count())
        .select_from(models.Notification)
        .where(
            models.Notification.tenant_id == tenant_id,
            or_(
                models.Notification.user_id == user_id,
                models.Notification.user_id.is_(None),
            ),
            models.Notification.is_read == False,  # noqa: E712
        )
    )

    result = await db.execute(stmt)
    return result.scalar() or 0


async def mark_notification_read(
    db: AsyncSession,
    notification_id: str,
    tenant_id: str,
    user_id: str,
) -> models.Notification:
    """
    Marks a notification as read and stamps the read_at timestamp.

    Raises:
        ValueError: If the notification is not found or does not belong
                    to the requesting user / tenant.
    """
    stmt = select(models.Notification).where(
        models.Notification.notification_id == notification_id,
        models.Notification.tenant_id == tenant_id,
        or_(
            models.Notification.user_id == user_id,
            models.Notification.user_id.is_(None),
        ),
    )

    result = await db.execute(stmt)
    notif = result.scalars().first()

    if not notif:
        raise ValueError("Notification not found or unauthorized access")

    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()
    await db.refresh(notif)
    return notif


async def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> bool:
    """
    Sends an email using AWS SES.
    Sender email is retrieved from the SES_SENDER_EMAIL environment variable.
    """
    sender = os.getenv("SES_SENDER_EMAIL")
    if not sender:
        logger.error("SES_SENDER_EMAIL environment variable not set. Cannot send email.")
        return False

    region = os.getenv("AWS_REGION", "ap-south-1")
    
    try:
        client = boto3.client('ses', region_name=region)
        
        message = {
            'Subject': {'Data': subject},
            'Body': {'Text': {'Data': body_text}}
        }
        
        if body_html:
            message['Body']['Html'] = {'Data': body_html}

        response = client.send_email(
            Source=sender,
            Destination={'ToAddresses': [to_email]},
            Message=message
        )
        
        logger.info("EMAIL_SENT | to=%s | msg_id=%s", to_email, response['MessageId'])
        return True
        
    except Exception as e:
        logger.error("EMAIL_FAILED | to=%s | error=%s", to_email, str(e))
        return False
